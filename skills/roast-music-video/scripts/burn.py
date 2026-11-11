"""burn.py : the text layer. All type is drawn with Pillow; every element is a pure function of time t = frame / fps.
Styles (strings.csv `style`, with `where` choosing the slot). These seven are the only ones; anything else is rejected by plan.py:
  caption  low caption strip, centred
  hook     big slam-in word or phrase, slightly rotated, centre
  namecard lower-third; text "NAME: role" or "NAME, role" splits into a name line and a role line
  bubble   chat-style bubble; where 'left' or 'right' (default right); simultaneous bubbles stack downwards
  card     where 'title' : title card; anything else : centred card ('end' / 'end2' are accepted as closing-card positions)
  tag      small label in a top corner; where 'left' or 'right' (default right)
  end      end card (large, centred); where 'low' places it lower
All sizes, positions and colours come from project.json (text.*, palette.*, fonts.*).
Usage (run from the project folder):
  python burn.py           render the text layer over the newest out/base_vN_nofx.mp4 -> out/_textlayer_vN_silent.mp4 (no audio yet)
  python burn.py --qa      layout + source check, no video: writes out/qa_layout.json (overlaps, outside safe area, too small, too short,
                           never drawn, strings with a number or quote but no source). EXITS 1 if anything fails.
  python burn.py --mux     mux the song (two-pass loudnorm to the project target, AAC, then re-measure and correct gain if the true peak is high)
                           -> out/<name>_vN.mp4 where name = animatic (any shot not on a real clip) or the project name.
                           Stops if the song's real duration differs from project.json duration by more than 0.25 s (unless allow_trim
                           is true and the song is longer) or if it has no audio stream.
  python burn.py --base N  use base_vN instead of the newest base
Build records (last_build.json) are written only after the encode succeeded; a failed encode leaves no partial file."""
import sys, os, re, json, time, functools
import numpy as np, cv2
from PIL import Image, ImageDraw
from common import *
import plan

_HELP = any(a in ('-h', '--help') for a in sys.argv[1:])
EDL = plan.load_edl() if not _HELP else {'shots': [], 'strings': [], 'fingerprint': ''}
SHOTS, STR = EDL['shots'], EDL['strings']
SX0, SY0, SX1, SY1 = SAFE
BYID = {s['id']: s for s in STR}
CX = W / 2

def active(t, style=None, where=None):
    return [s for s in STR if s['draw'] and s['start'] <= t < s['end'] and (style is None or s['style'] == style) and (where is None or s['where'] == where)]

def fade_io(t, s, tin=0.12, tout=0.15):
    return clamp((t - s['start']) / tin) * clamp((s['end'] - t) / tout)

def sz(key): return int(round(TX[key] * S))

# ----------------------------------------------------------------------------- hook
def draw_hook(t, f, s):
    size = sz('hook_size'); ang = float(TX['hook_angle'])
    k = int((t - s['start']) * FPS + 1e-6)
    sc = (1.55, 1.2, 1.0)[k] if k < 3 else 1.0 + 0.015 * clamp((t - s['start'] - 0.125) / 1.0)
    base = T(s['text'], 'display', size, ACCENT2, stroke=max(int(10 * S), 2), stroke_fill=INK, shadow=(int(8 * S), int(8 * S)))
    im = base
    if abs(sc - 1) > 0.002: im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
    im = rotate_layer(im, ang)
    a = clamp((s['end'] - t) / 0.1)
    cx, cy = TX['hook_center'][0] * W, TX['hook_center'][1] * H
    f.put(im, cx - im.width / 2, cy - im.height / 2, alpha=a)
    nom = rotate_layer(base, ang)                           # settled size, for QA (the 3-frame slam overshoots on purpose)
    bb = nom.getchannel('A').getbbox(); nx, ny = cx - nom.width / 2, cy - nom.height / 2
    f.reg('hook', s['id'], (nx + bb[0], ny + bb[1], nx + bb[2], ny + bb[3]), [s['id']], cap_height('display', size), s['text'])

# ----------------------------------------------------------------------------- caption and tag
def draw_tag(t, f, s):
    size = sz('tag_size')
    a = fade_io(t, s, IN_SECONDS['tag'])
    im = T(s['text'], 'display', size, PAPER)
    w, h = im.width + int(36 * S), im.height + int(14 * S)
    L = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle((0, 0, w - 1, h - 1), int(10 * S), fill=INK + (215,), outline=ACCENT + (255,), width=max(int(3 * S), 1))
    L.alpha_composite(im, (int(18 * S), int(6 * S)))
    x, y = (SX0 if s['where'] == 'left' else SX1 - w), SY0 + int(8 * S)
    f.put(L, x, y, alpha=a)
    f.reg('tag', s['id'], (x, y, x + w, y + h), [s['id']], cap_height('display', size), s['text'])

def draw_caption(t, f, s):
    a = fade_io(t, s, IN_SECONDS['caption'])
    size = sz('caption_size')
    lines = wrap(s['text'], 'display', size, TX['caption_max_width'] * W)
    ims = [T(l, 'display', size, PAPER, shadow=(2, 2)) for l in lines]
    lh = int(size * 1.22); pad = int(26 * S)
    tw = max(i.width for i in ims); w = tw + 2 * pad; h = lh * len(lines) + int(20 * S)
    strip = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(strip).rounded_rectangle((0, 0, w - 1, h - 1), int(16 * S), fill=INK + (158,))
    for i, im in enumerate(ims): strip.alpha_composite(im, ((w - im.width) // 2, int(6 * S) + i * lh))
    x, y = CX - w / 2, TX['caption_bottom'] * H - h
    f.put(strip, x, y, alpha=a)
    f.reg('caption', s['id'], (x, y, x + w, y + h), [s['id']], cap_height('display', size), s['text'])

# ----------------------------------------------------------------------------- namecard
def split_name(txt):
    for sep in (': ', ', '):
        if sep in txt:
            a, b = txt.split(sep, 1); return a.upper(), b
    return txt.upper(), ''

def draw_namecard(t, f, s):
    name, role = split_name(s['text'])
    ns, rs = sz('namecard_name_size'), sz('namecard_role_size')
    nm = T(name, 'display', ns, ACCENT)
    rl = T(role, 'body', rs, PAPER) if role else None
    w = max(nm.width, rl.width if rl else 0) + int(64 * S)
    h1, h2 = nm.height + int(8 * S), (rl.height + int(6 * S) if rl else 0)
    L = Image.new('RGBA', (w, h1 + h2), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    bar = max(int(14 * S), 3)
    d.rectangle((0, 0, w, h1), fill=PANEL + (240,)); d.rectangle((0, 0, bar, h1 + h2), fill=ACCENT + (255,))
    if rl: d.rectangle((0, h1, w, h1 + h2), fill=INK + (232,))
    d.rectangle((0, h1 + h2 - 3, w, h1 + h2), fill=ACCENT + (255,))
    L.alpha_composite(nm, (int(34 * S), int(4 * S)))
    if rl: L.alpha_composite(rl, (int(34 * S), h1 + int(2 * S)))
    pin = ease_out((t - s['start']) / IN_SECONDS['namecard']); q = clamp((s['end'] - t) / 0.2)
    x, y = SX0, TX['namecard_bottom'] * H - L.height
    f.put(L, x, y, alpha=q, clip=(x, y, x + int(w * pin) + 1, y + L.height))
    caps = [cap_height('display', ns)] + ([cap_height('body', rs)] if rl else [])
    f.reg('namecard', s['id'], (x, y, x + w * pin, y + L.height), [s['id']], min(caps), s['text'])

# ----------------------------------------------------------------------------- bubbles
@functools.lru_cache(maxsize=None)
def bubble_layer(text, size, maxw, fill):
    lines = wrap(text, 'body', size, maxw)
    ims = [T(l, 'body', size, (255, 255, 255)) for l in lines]
    lh = int(size * 1.3); pw = max(i.width for i in ims) + int(size * 1.1); ph = lh * len(lines) + int(size * 0.55)
    rad = int(min(ph / 2, size * 0.85))
    L = Image.new('RGBA', (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), rad, fill=tuple(fill) + (255,))
    for i, im in enumerate(ims): L.alpha_composite(im, (int(size * 0.55) - 3, int(size * 0.28) + i * lh - 2))
    return L

def draw_bubble(t, f, s, order):
    size = sz('bubble_size')
    right = s['where'] != 'left'
    L = bubble_layer(s['text'], size, int(TX['bubble_max_width'] * W), tuple(ACCENT2 if right else PANEL))
    gap = int(14 * S)
    y = SY0 + int(24 * S) + sum(b.height + gap for b in order)     # stack below earlier simultaneous bubbles on the same side
    x = (SX1 - L.width) if right else SX0
    p = ease_out((t - s['start']) / IN_SECONDS['bubble'])
    f.put(L, x, y + (1 - p) * 18 * S, alpha=p * clamp((s['end'] - t) / 0.15))
    f.reg('bubble', s['id'], (x, y, x + L.width, y + L.height), [s['id']], cap_height('body', size), s['text'])
    order.append(L)

# ----------------------------------------------------------------------------- cards (card and end)
def _draw_card_like(t, f, s, kind, size, big, y_frac):
    lines = wrap(s['text'], 'display', size, (SX1 - SX0) * 0.86)
    ims = [T(l, 'display', size, ACCENT if big else PAPER, stroke=max(int(6 * S), 1), stroke_fill=INK, shadow=(int(5 * S), int(5 * S))) for l in lines]
    lh = int(size * 1.15); w = max(i.width for i in ims) + int(60 * S); h = lh * len(ims) + int(36 * S)
    L = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(L).rounded_rectangle((0, 0, w - 1, h - 1), int(18 * S), fill=INK + (150,))
    for i, im in enumerate(ims): L.alpha_composite(im, ((w - im.width) // 2, int(14 * S) + i * lh))
    x = CX - w / 2; y = H * y_frac - h / 2
    f.put(L, x, y, alpha=fade_io(t, s, IN_SECONDS[kind], 0.25))
    f.reg(kind, s['id'], (x, y, x + w, y + h), [s['id']], cap_height('display', size), s['text'])

def draw_card(t, f, s):
    where = s['where']
    big = where in ('title', 'end', 'end2')
    y = {'title': 0.34, 'end': 0.40, 'end2': 0.62}.get(where, 0.45)
    _draw_card_like(t, f, s, 'card', sz('title_size') if big else sz('card_size'), big, y)

def draw_end(t, f, s):
    _draw_card_like(t, f, s, 'end', sz('end_size'), True, 0.62 if s['where'] == 'low' else 0.45)

# ----------------------------------------------------------------------------- compose
def overlay(k, f):
    t = k / FPS
    for s in active(t, 'card'): draw_card(t, f, s)
    for s in active(t, 'end'): draw_end(t, f, s)
    order = {'left': [], 'right': []}
    for s in sorted(active(t, 'bubble'), key=lambda s: s['start']):
        draw_bubble(t, f, s, order['left' if s['where'] == 'left' else 'right'])
    for s in active(t, 'tag'): draw_tag(t, f, s)
    for s in active(t, 'namecard'): draw_namecard(t, f, s)
    for s in active(t, 'hook'): draw_hook(t, f, s)
    for s in active(t, 'caption'): draw_caption(t, f, s)

# ----------------------------------------------------------------------------- stages
def pick_base():
    if '--base' in sys.argv: n = int(sys.argv[sys.argv.index('--base') + 1])
    else:
        vs = versions('base_v', '_nofx.mp4')
        if not vs: raise SystemExit('no out/base_vN_nofx.mp4 yet: run base.py')
        n = vs[-1]
    p = os.path.join(OUT, 'base_v%d_nofx.mp4' % n)
    if not os.path.isfile(p) or not os.path.isfile(os.path.join(OUT, 'base_v%d_report.json' % n)):
        raise SystemExit('base v%d is missing or incomplete (no video or no report): run base.py again' % n)
    return n, p

def run_qa():
    """layout and source check. Returns True if everything passed; always writes out/qa_layout.json."""
    t0 = time.time(); per = []; drawn = {}
    for k in range(NF):
        f = Frame(None, qa=True); overlay(k, f); per.append(f.rects)
    pairs, outside = {}, {}
    cap_min, frames_on = {}, {}
    for k, rs in enumerate(per):
        t = k / FPS
        for r in rs:
            x0, y0, x1, y1 = r['rect']; key = r['kind'] + ':' + r['name']
            if x0 < SX0 - 0.5 or y0 < SY0 - 0.5 or x1 > SX1 + 0.5 or y1 > SY1 + 0.5:
                o = outside.setdefault(key, [t, t, r['rect']]); o[1] = t
            if r['text']: drawn[r['text']] = drawn.get(r['text'], 0) + 1
            for i in r['ids']:
                frames_on[i] = frames_on.get(i, 0) + 1
                if r['cap'] is not None: cap_min[i] = min(cap_min.get(i, 999), r['cap'])
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]; A, B = a['rect'], b['rect']
                if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                    kk = ' x '.join(sorted([a['kind'] + ':' + a['name'], b['kind'] + ':' + b['name']]))
                    o = pairs.setdefault(kk, [t, t, A, B]); o[1] = t
    small = {i: c for i, c in cap_min.items() if c < MIN_CAP}
    short = {}
    for s in STR:
        if not s['draw']: continue
        on = frames_on.get(s['id'], 0) / FPS
        if s['words'] > 3 and on < MIN_HOLD - 1e-6: short[s['id']] = {'text': s['text'], 'seconds_on_screen': round(on, 3), 'words': s['words']}
    missing = [s['id'] for s in STR if s['draw'] and s['id'] not in frames_on]
    no_source = [s['id'] for s in STR if s['draw'] and needs_source(s['text']) and not s['source'].strip()]
    res = {'fingerprint': EDL['fingerprint'], 'safe': list(SAFE), 'overlaps': {k: {'from': round(v[0], 2), 'to': round(v[1], 2), 'rects': [v[2], v[3]]} for k, v in pairs.items()},
           'outside_safe_area': {k: {'from': round(v[0], 2), 'to': round(v[1], 2), 'rect': v[2]} for k, v in outside.items()},
           'too_small': {i: {'cap_px': c, 'text': BYID[i]['text']} for i, c in small.items()},
           'too_short': short, 'never_drawn': missing, 'missing_source': no_source, 'min_cap_px': min(cap_min.values()) if cap_min else None,
           'drawn_text': sorted(drawn), 'hold_extensions': EDL.get('hold_extensions', [])}
    res['pass'] = not (pairs or outside or small or short or missing or no_source)
    ensure_out()
    write_json(os.path.join(OUT, 'qa_layout.json'), res)
    print('qa layout: %d overlaps, %d outside-safe, %d too small, %d too short, %d never drawn, %d missing source (min cap %s px), %.1f s' %
          (len(pairs), len(outside), len(small), len(short), len(missing), len(no_source), res['min_cap_px'], time.time() - t0))
    for k, v in res['overlaps'].items(): print('  OVERLAP', k, v['from'], v['to'])
    for k, v in res['outside_safe_area'].items(): print('  OUTSIDE', k, v['from'], v['to'], v['rect'])
    for k, v in res['too_small'].items(): print('  SMALL', k, v)
    for k, v in res['too_short'].items(): print('  SHORT', k, v)
    for k in missing: print('  NEVER DRAWN', k, BYID[k]['text'])
    for k in no_source: print('  NO SOURCE', k, BYID[k]['text'])
    print('LAYOUT', 'PASS' if res['pass'] else 'FAIL')
    return res['pass']

def run_burn():
    ffmpeg_ok()
    n, base = pick_base(); t0 = time.time()
    rep = read_json(os.path.join(OUT, 'base_v%d_report.json' % n))
    # the base must show the pictures the current plan resolves to (clips, stills, offsets, speed, push-ins, size, fps); text-only edits pass
    import copy
    now = plan.visual_fingerprint(plan.resolve_sources(copy.deepcopy(SHOTS)))
    if rep.get('visual_fingerprint') != now or EDL.get('visual_fingerprint') != now:
        raise SystemExit('base v%d does not match the current pictures (shots, clips, keyframes, plates, clip_in, speed, size or fps changed, or the base is '
                         'from an older version of the scripts, or out/edl.json is stale): run plan.py and base.py again, then burn.py. '
                         'Text-only edits (strings.csv) do not need a new base.' % n)
    silent = os.path.join(OUT, '_textlayer_v%d_silent.mp4' % n)
    rd = cv2.VideoCapture(base)
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
           '-color_trc', 'bt709', '-an', silent]
    with Encoder(cmd, silent, 'text layer encode') as enc:
        for k in range(NF):
            ok, bgr = rd.read()
            if not ok: raise SystemExit('base ended early at frame %d' % k)
            f = Frame(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)); overlay(k, f)
            enc.write(f.arr())
    rd.release()
    name = 'animatic' if rep.get('placeholders', 0) > 0 else re.sub(r'[^A-Za-z0-9_-]+', '_', P['name']) or 'film'
    write_json(os.path.join(OUT, 'last_build.json'),          # only after the encode succeeded
               {'base_version': n, 'silent': silent, 'name': name, 'placeholders': rep.get('placeholders', 0), 'fingerprint': EDL['fingerprint']})
    print('text layer: %.1f s -> %s (will mux as %s)' % (time.time() - t0, os.path.basename(silent), name))

def _json_from(stderr, what):
    try: return json.loads(stderr[stderr.rindex('{'):stderr.rindex('}') + 1])
    except ValueError: raise SystemExit('%s: could not read the loudness numbers from ffmpeg output:\n%s' % (what, (stderr or '')[-1000:]))

def run_mux():
    ffmpeg_ok()
    song = find_song()
    if not song: raise SystemExit('no song found: put it at %s.* (or set "song" in project.json)' % P['song'])
    bad = song_problems(probe_media(song))
    if bad: raise SystemExit('cannot mux the song:\n  - ' + '\n  - '.join(bad))
    lbp = os.path.join(OUT, 'last_build.json')
    if not os.path.exists(lbp): raise SystemExit('no out/last_build.json: run burn.py first')
    lb = read_json(lbp); silent, name = lb['silent'], lb['name']
    if not os.path.isfile(silent): raise SystemExit('text layer %s is missing: run burn.py again' % silent)
    vs = versions(name + '_v', '.mp4'); ver = (vs[-1] + 1) if vs else 1
    final = os.path.join(OUT, '%s_v%d.mp4' % (name, ver)); tmp = os.path.join(OUT, '_mux_tmp_%s_v%d.mp4' % (name, ver)); t0 = time.time()
    tgt, tp_target0, lra = float(LOUD['target_lufs']), float(LOUD['true_peak']), LOUD['lra']
    ln = 'loudnorm=I=%g:TP=%g:LRA=%g' % (tgt, tp_target0, lra)
    try:
        p1 = run_cmd(['ffmpeg', '-hide_banner', '-nostats', '-i', song, '-af', ln + ':print_format=json', '-f', 'null', '-'], 'loudness measurement of the song')
        m = _json_from(p1.stderr, 'loudness measurement of the song'); print('pass1:', {k: m[k] for k in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')})
        tp_target = tp_target0
        for attempt in range(4):
            af = 'loudnorm=I=%g:TP=%.2f:LRA=%g:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true' % (
                tgt, tp_target, lra, m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset'])
            run_cmd(['ffmpeg', '-y', '-v', 'error', '-i', silent, '-i', song, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', af,
                     '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-t', str(DUR), '-movflags', '+faststart', '-f', 'mp4', tmp], 'mux')
            p = run_cmd(['ffmpeg', '-hide_banner', '-nostats', '-i', tmp, '-vn', '-af', ln + ':print_format=json', '-f', 'null', '-'], 'loudness check of the muxed file')
            r = _json_from(p.stderr, 'loudness check of the muxed file'); tp = float(r['input_tp'])
            print('final mp4: I=%s LUFS  true peak=%.2f dBTP  LRA=%s' % (r['input_i'], tp, r['input_lra']))
            if tp <= tp_target0 + 0.5: break
            tp_target -= (tp - (tp_target0 + 0.5)) + 0.3; print('true peak too high after AAC, retry with TP target %.2f' % tp_target)
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass
    lb['final'] = final
    write_json(lbp, lb)                                        # only after the mux succeeded
    print('mux: %.1f s -> %s' % (time.time() - t0, final))

if __name__ == '__main__':
    if _HELP: print(__doc__)
    elif '--qa' in sys.argv: sys.exit(0 if run_qa() else 1)
    elif '--mux' in sys.argv: run_mux()
    else: run_burn()
