"""qa.py : checks the newest muxed film (out/last_build.json -> final) and writes out/<name>_vN_sheet.png and out/qa_report.json.
  1. frames read vs duration x fps (FAIL if they differ), size, frame rate (must equal project fps within 0.01), streams, container length
  2. black or frozen spans over 0.6 s outside code shots and title/end cards (ffmpeg blackdetect + freezedetect)
  3. loudness and true peak of the final mp4 against project.json loudness
  4. contact sheet: one frame per shot, labelled with the shot id and its source
  5. claims check: every string with a number or a quote must have a non-empty `source` (FAIL if any is missing)
  6. banned terms: project.json banned_terms (names that must never be drawn) checked against every string and every drawn text
  7. layout: out/qa_layout.json from  python burn.py --qa  MUST exist and be current (made from the same strings, shots and settings as
     this build); a missing or stale report FAILS. Overlaps, text outside the safe area, text too small, text on screen too briefly
     (too_short) and strings never drawn all FAIL.
  8. song: the song file's real duration matches project.json duration (0.25 s) or allow_trim covers it; it has an audio stream.
  9. the final was built from the current plan (strings, shots, settings); otherwise FAIL (rebuild with burn.py, burn.py --mux).
Exits 0 on PASS, 1 on FAIL. A failed ffprobe/ffmpeg call stops with its own message instead of reporting.
Usage: python qa.py [--final path]"""
import os, sys, re, json
import numpy as np, cv2
from PIL import Image, ImageDraw
from common import *
from roots import under_root
import plan

if any(a in ('-h', '--help') for a in sys.argv[1:]):
    print(__doc__); raise SystemExit(0)
ffmpeg_ok()
EDL = plan.load_edl()

def word_hit(term, text):
    return re.search(r'(?<![A-Za-z0-9])' + re.escape(term) + r'(?![A-Za-z0-9])', text, re.I) is not None

def last_build():
    p = os.path.join(OUT, 'last_build.json')
    return read_json(p) if os.path.exists(p) else None

def find_final():
    if '--final' in sys.argv: return under_root(sys.argv[sys.argv.index('--final') + 1], ROOT)     # relative paths are under the project folder
    j = last_build()
    if j is None: raise SystemExit('no out/last_build.json: run burn.py and burn.py --mux first, or pass --final path')
    if 'final' not in j: raise SystemExit('last build has no final yet: run burn.py --mux')
    return j['final']

def probe(final, rep):
    r = run_cmd(['ffprobe', '-v', 'error', '-count_frames', '-show_entries', 'stream=codec_name,codec_type,width,height,r_frame_rate,nb_read_frames,duration,pix_fmt',
                 '-show_entries', 'format=duration', '-of', 'json', final], 'ffprobe of the final')
    j = json.loads(r.stdout)
    vs = [s for s in j['streams'] if s['codec_type'] == 'video']
    if not vs: raise SystemExit('the final has no video stream')
    v = vs[0]
    aud = [s for s in j['streams'] if s['codec_type'] == 'audio']
    n = int(v['nb_read_frames']); fdur = float(j['format']['duration']); exp = NF
    try: a_, b_ = v['r_frame_rate'].split('/'); got_fps = float(a_) / float(b_)
    except (ValueError, ZeroDivisionError): got_fps = 0.0
    fps_ok = abs(got_fps - FPS) <= 0.01                                  # the project fps, to within 0.01 fps
    ok = (n == exp) and abs(fdur - DUR) < 0.06 and (v['width'], v['height']) == (W, H) and bool(aud) and fps_ok
    rep['frames'] = {'read': n, 'expected_from_project': exp, 'container_dur_x_fps': round(fdur * FPS, 2), 'duration_s': fdur, 'size': '%sx%s' % (v['width'], v['height']),
                     'fps': v['r_frame_rate'], 'fps_expected': FPS, 'audio': aud[0]['codec_name'] if aud else None, 'pass': bool(ok)}
    print('video %sx%s %s frames=%d expected=%d (%g x %d) container %.3f s audio %s -> %s' % (v['width'], v['height'], v['r_frame_rate'], n, exp, DUR, FPS, fdur,
          aud[0]['codec_name'] if aud else 'MISSING', 'OK' if ok else 'FAIL'))

def spans(final, rep):
    code_iv = [(e['start'], e['end']) for e in EDL['shots'] if e['type'] == 'code']
    card_iv = [(s['start'], s['end']) for s in EDL['strings'] if (s['style'] == 'card' and s['where'] in ('title', 'end', 'end2')) or s['style'] == 'end']
    def in_card(a, b):
        return any(a >= c0 - 0.05 and b <= c1 + 0.05 for c0, c1 in code_iv + card_iv)
    p = run_cmd(['ffmpeg', '-hide_banner', '-nostats', '-i', final, '-an', '-vf', 'blackdetect=d=0.6:pix_th=0.10,freezedetect=n=-55dB:d=0.6', '-f', 'null', '-'], 'black and freeze detection')
    bl = [(float(a), float(b)) for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', p.stderr)]
    fs = re.findall(r'freeze_start: ([\d.]+)', p.stderr); fe = re.findall(r'freeze_end: ([\d.]+)', p.stderr)
    fz = [(float(a), float(b)) for a, b in zip(fs, fe)]
    if len(fs) > len(fe): fz.append((float(fs[-1]), DUR))
    bad_b = [x for x in bl if not in_card(*x)]; bad_f = [x for x in fz if not in_card(*x)]
    rep['black'] = {'all': bl, 'outside_cards': bad_b}; rep['frozen'] = {'all': fz, 'outside_cards': bad_f}
    print('black spans >0.6 s: %d (outside cards: %d) %s' % (len(bl), len(bad_b), bad_b)); print('frozen spans >0.6 s: %d (outside cards: %d) %s' % (len(fz), len(bad_f), bad_f))

def loudness(final, rep):
    tgt, tp_lim = float(LOUD['target_lufs']), float(LOUD['true_peak'])
    p = run_cmd(['ffmpeg', '-hide_banner', '-nostats', '-i', final, '-vn', '-af', 'loudnorm=I=%g:TP=%g:LRA=%g:print_format=json' % (tgt, tp_lim, LOUD['lra']), '-f', 'null', '-'], 'loudness measurement')
    try: r = json.loads(p.stderr[p.stderr.rindex('{'):p.stderr.rindex('}') + 1])
    except ValueError: raise SystemExit('loudness measurement: no numbers in ffmpeg output (does the final have audio?)')
    ok = abs(float(r['input_i']) - tgt) < 1.0 and float(r['input_tp']) <= tp_lim + 0.5
    rep['loudness'] = {'integrated_lufs': r['input_i'], 'true_peak_dbtp': r['input_tp'], 'lra': r['input_lra'], 'target_lufs': tgt, 'pass': bool(ok)}
    print('loudness: I=%s LUFS (target %g)  TP=%s dBTP  LRA=%s -> %s' % (r['input_i'], tgt, r['input_tp'], r['input_lra'], 'OK' if ok else 'FAIL'))

def sheet(final, out_png):
    cap = cv2.VideoCapture(final); shots = EDL['shots']; tw = 256; th = int(round(tw * H / W)); cols = 6; rows = (len(shots) + cols - 1) // cols
    Sh = Image.new('RGB', (cols * tw, rows * (th + 20)), (20, 20, 30)); d = ImageDraw.Draw(Sh)
    for i, e in enumerate(shots):
        k = min((e['f0'] + e['f1']) // 2, NF - 1); cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, im = cap.read()
        if not ok: continue
        x, y = (i % cols) * tw, (i // cols) * (th + 20)
        Sh.paste(Image.fromarray(cv2.cvtColor(cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x, y + 20))
        col = (255, 220, 90) if e['source'] == 'clip' else (150, 220, 255) if e['source'] == 'plate' else (255, 150, 120)
        d.text((x + 5, y + 4), '%s  %s  %.1fs' % (e['id'], e['source'], e['start']), fill=col)
    cap.release()
    Sh.save(out_png); print('sheet', Sh.size, os.path.basename(out_png))

def claims(rep):
    rows = EDL['strings']
    need = [s['id'] for s in rows if needs_source(s['text']) and not s['source'].strip()]
    nosrc = [s['id'] for s in rows if not s['source'].strip()]
    checked = len([s for s in rows if needs_source(s['text'])])
    rep['claims'] = {'checked': checked, 'missing_source': need, 'any_string_without_source': nosrc, 'pass': not need}
    print('claims: %d strings with a number or quote, %d missing a source -> %s' % (checked, len(need), 'OK' if not need else 'FAIL ' + str(need)))

def banned(rep):
    terms = [t for t in P['banned_terms'] if t]
    texts = [(s['id'], s['text']) for s in EDL['strings']]
    lay = os.path.join(OUT, 'qa_layout.json')
    if os.path.exists(lay):
        texts += [('drawn', t) for t in read_json(lay).get('drawn_text', [])]
    hits = [{'id': i, 'term': t, 'text': x} for i, x in texts for t in terms if word_hit(t, x)]
    rep['banned'] = {'terms_checked': len(terms), 'strings_checked': len(texts), 'hits': hits}
    print('banned terms: %d terms, %d strings, %d hits %s' % (len(terms), len(texts), len(hits), hits))

def layout_summary(rep):
    p = os.path.join(OUT, 'qa_layout.json')
    if not os.path.exists(p):
        print('layout: FAIL, no out/qa_layout.json (run  python burn.py --qa)'); rep['layout'] = None; rep['layout_pass'] = False; rep['layout_problem'] = 'missing'; return
    L = read_json(p)
    stale = L.get('fingerprint') != EDL.get('fingerprint')
    keys = ('overlaps', 'outside_safe_area', 'too_small', 'too_short', 'never_drawn', 'missing_source')
    rep['layout'] = {k: L.get(k) for k in keys + ('min_cap_px', 'hold_extensions')}
    print('layout: %d overlaps, %d outside safe, %d too small, %d too short, %d never drawn, %d missing source, min cap %s px' % (
        len(L.get('overlaps') or {}), len(L.get('outside_safe_area') or {}), len(L.get('too_small') or {}), len(L.get('too_short') or {}),
        len(L.get('never_drawn') or []), len(L.get('missing_source') or []), L.get('min_cap_px')))
    for k, v in (L.get('overlaps') or {}).items(): print('   overlap', k, v['from'], v['to'])
    if stale: print('layout: FAIL, qa_layout.json is stale (made from other strings, shots or settings): run  python burn.py --qa'); rep['layout_problem'] = 'stale'
    rep['layout_pass'] = (not stale) and not any(L.get(k) for k in keys)

def song_check(rep):
    song = find_song()
    if not song: rep['song'] = {'pass': False, 'problems': ['no song file found']}
    else: rep['song'] = {'file': os.path.basename(song), 'problems': song_problems(probe_media(song))}; rep['song']['pass'] = not rep['song']['problems']
    print('song: %s' % ('OK' if rep['song']['pass'] else 'FAIL ' + '; '.join(rep['song']['problems'])))

def build_current(rep):
    lb = last_build()
    if lb is None or lb.get('fingerprint') is None or '--final' in sys.argv:
        rep['build_current'] = None; return                    # a final passed by hand has no build record to compare
    rep['build_current'] = lb['fingerprint'] == EDL.get('fingerprint')
    if not rep['build_current']: print('build: FAIL, the final was built from an older plan (strings, shots or settings changed): run burn.py and burn.py --mux')

if __name__ == '__main__':
    final = find_final()
    if not os.path.isfile(final): raise SystemExit('final not found: ' + final)
    rep = {'final': final}
    print('QA of', final)
    probe(final, rep); spans(final, rep); loudness(final, rep)
    sheet(final, re.sub(r'\.mp4$', '_sheet.png', final))
    claims(rep); banned(rep); layout_summary(rep); song_check(rep); build_current(rep)
    ph = os.path.join(OUT, 'placeholders.json')
    rep['placeholders'] = len(read_json(ph)) if os.path.exists(ph) else None
    print('shots not yet on a real clip:', rep['placeholders'])
    rep['pass'] = all([rep['frames']['pass'], not rep['black']['outside_cards'], not rep['frozen']['outside_cards'], rep['loudness']['pass'],
                       rep['claims']['pass'], not rep['banned']['hits'], rep['layout_pass'], rep['song']['pass'], rep['build_current'] is not False])
    write_json(os.path.join(OUT, 'qa_report.json'), rep)
    print('QA', 'PASS' if rep['pass'] else 'FAIL (see out/qa_report.json)')
    sys.exit(0 if rep['pass'] else 1)
