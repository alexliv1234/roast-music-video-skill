"""plan.py -> out/edl.json and out/placeholders.json
Reads shots.csv and strings.csv, VALIDATES them, and fails with a list of every problem instead of repairing anything silently.
For every shot it then resolves the picture source in this order:
  gen shot : footage/final/<clip_id>_vN.mp4 (highest N)  ->  frames/k_<clip_id>.png (slow push-in)  ->  labelled grey placeholder
  code shot: frames/<plate>.png (slow push-in, text drawn by burn.py)                                ->  labelled grey placeholder
So with no video clips at all, a stills-only animatic still builds: every shot falls back to its keyframe with a slow push-in.

shots.csv columns:  id,start,end,type,clip_id,reuse_of,clip_in,plate,onscreen_text_ids,notes  (+ any extra columns, carried along or ignored)
  Timeline rules (checked, never repaired): ids unique and made of letters, digits, . _ - ; start of the first shot 0; each shot ends where
  the next starts (within half a frame); every end after its start; the last end equals project.json duration (within half a frame).
  type is gen or code. reuse_of names another gen shot: this shot takes its clip (clip_id is inherited, or must match if repeated) from clip_in seconds.
  onscreen_text_ids is metadata for reviewers: it is checked against strings.csv but does not control drawing.
strings.csv columns: id,start,end,text,style,where,shot_id,source
  style is one of: caption, hook, namecard, bubble, card, tag, end (anything else is rejected). shot_id is metadata, checked against shots.csv.
  Every string is drawn only by its own start/end times. Strings that cross a shot cut are listed under review_flags in out/edl.json.
Run:  python plan.py        (from the project folder; see README for the script path)"""
import os, sys, json, math, hashlib
from common import *

END_HOLD = 1.5          # a string may run this long past the song end; only the part before the end is drawn (warned)

class PlanError(Exception):
    def __init__(self, errors): Exception.__init__(self, '\n'.join(errors)); self.errors = errors

def _flt(r, key, label, errs, default=None):
    raw = (r.get(key) or '').strip()
    if raw == '':
        if default is not None: return default
        errs.append('%s: %s is empty' % (label, key)); return None
    try: v = float(raw)
    except ValueError: errs.append('%s: %s "%s" is not a number' % (label, key, raw)); return None
    if not math.isfinite(v): errs.append('%s: %s "%s" is not finite' % (label, key, raw)); return None
    return v

def _missing_cols(rows, cols, name):
    if not rows: return ['%s has no rows' % name]
    have = set(rows[0].keys())
    return ['%s is missing the column "%s"' % (name, c) for c in cols if c not in have]

def parse_shots(rows):
    """validated shot dicts (frames assigned, reuse_of resolved, sources not yet resolved). Raises PlanError listing every problem."""
    errs = _missing_cols(rows, ('id', 'start', 'end'), P['shots_csv'])
    if errs: raise PlanError(errs)
    shots, seen, tol = [], set(), 0.5 / FPS + 1e-6
    for i, r in enumerate(rows):
        g = lambda k, d='': (r.get(k) or d).strip()
        sid = g('id'); label = sid or 'shots row %d' % (i + 2)
        if not ID_RE.match(sid): errs.append('%s: id must be letters, digits, . _ - (max 64 characters, not empty)' % label)
        elif sid in seen: errs.append('%s: duplicate shot id' % label)
        seen.add(sid)
        s, e = _flt(r, 'start', label, errs), _flt(r, 'end', label, errs)
        if s is not None and e is not None and e <= s: errs.append('%s: end %.3f is not after start %.3f' % (label, e, s))
        typ = g('type', 'gen')
        if typ not in ('gen', 'code'): errs.append('%s: type "%s" must be gen or code' % (label, typ)); typ = 'gen'
        ci = _flt(r, 'clip_in', label, errs, default=0.0)
        if ci is not None and ci < 0: errs.append('%s: clip_in %.3f is negative' % (label, ci))
        notes = g('notes')
        shots.append({'i': i, 'id': sid, 'section': g('section'), 'start': s, 'end': e, 'type': typ, 'setup': g('setup'), 'lyric': g('lyric'),
                      'clip_id': g('clip_id'), 'reuse_of': g('reuse_of'), 'clip_in': ci or 0.0, 'plate': g('plate'),
                      'text_ids': g('onscreen_text_ids').split(), 'notes': notes, 'speed': RETIME if 'retime' in notes.lower() else 1.0})
    if errs: raise PlanError(errs)
    # timeline: validate, do not repair
    if abs(shots[0]['start']) > tol: errs.append('%s: the first shot starts at %.3f, it must start at 0' % (shots[0]['id'], shots[0]['start']))
    for a, b in zip(shots, shots[1:]):
        if abs(b['start'] - a['end']) > tol:
            errs.append('%s starts at %.3f but %s ends at %.3f (%s of %.3f s): shots must be contiguous' % (
                b['id'], b['start'], a['id'], a['end'], 'gap' if b['start'] > a['end'] else 'overlap', abs(b['start'] - a['end'])))
    if abs(shots[-1]['end'] - DUR) > tol:
        errs.append('%s ends at %.3f but project.json duration is %.3f: the last shot must end at the song end' % (shots[-1]['id'], shots[-1]['end'], DUR))
    # frames: boundaries snap to frames; the first is 0 and the last is NF (both already checked to be within half a frame)
    for k, sh in enumerate(shots):
        sh['f0'] = 0 if k == 0 else fr(sh['start'])
        sh['f1'] = NF if k == len(shots) - 1 else fr(shots[k + 1]['start'])
        if sh['f1'] <= sh['f0']: errs.append('%s: shorter than one frame at %d fps' % (sh['id'], FPS))
    # reuse_of: resolve to the referenced shot's clip
    byid = {sh['id']: sh for sh in shots}
    def effective(sh, chain):
        ref = sh['reuse_of']
        if not ref: return sh['clip_id']
        if sh['id'] in chain: errs.append('%s: reuse_of forms a cycle (%s)' % (sh['id'], ' -> '.join(chain + [sh['id']]))); return ''
        if ref not in byid: errs.append('%s: reuse_of "%s" is not a shot id' % (sh['id'], ref)); return sh['clip_id']
        if ref == sh['id']: errs.append('%s: reuse_of points at itself' % sh['id']); return sh['clip_id']
        if byid[ref]['type'] != 'gen': errs.append('%s: reuse_of "%s" is not a gen shot' % (sh['id'], ref)); return sh['clip_id']
        inherited = effective(byid[ref], chain + [sh['id']])
        if sh['clip_id'] and inherited and sh['clip_id'] != inherited:
            errs.append('%s: clip_id "%s" conflicts with reuse_of %s, which uses "%s"' % (sh['id'], sh['clip_id'], ref, inherited))
        return sh['clip_id'] or inherited
    for sh in shots:
        if sh['type'] == 'gen' or sh['reuse_of']:
            cid = effective(sh, [])
            if sh['reuse_of'] and not cid: errs.append('%s: reuse_of %s has no clip_id to inherit' % (sh['id'], sh['reuse_of']))
            sh['clip_id'] = cid
    if errs: raise PlanError(errs)
    return shots

def parse_strings(rows, shot_ids):
    """validated string dicts. Raises PlanError listing every problem."""
    errs = _missing_cols(rows, ('id', 'start', 'end', 'text'), P['strings_csv'])
    if errs: raise PlanError(errs)
    out, seen, warns = [], set(), []
    for i, r in enumerate(rows):
        g = lambda k, d='': (r.get(k) or d).strip()
        sid = g('id'); label = sid or 'strings row %d' % (i + 2)
        if not ID_RE.match(sid): errs.append('%s: id must be letters, digits, . _ - (max 64 characters, not empty)' % label)
        elif sid in seen: errs.append('%s: duplicate string id' % label)
        seen.add(sid)
        s, e = _flt(r, 'start', label, errs), _flt(r, 'end', label, errs)
        if s is not None and e is not None:
            if e <= s: errs.append('%s: end %.3f is not after start %.3f' % (label, e, s))
            if s < 0: errs.append('%s: start %.3f is before the song start' % (label, s))
            if s >= DUR: errs.append('%s: starts at %.3f, at or after the song end %.3f' % (label, s, DUR))
            elif e > DUR + 1e-6: warns.append('%s: ends at %.3f, after the song end %.3f; only the part before the end is drawn' % (label, e, DUR))
        text = r.get('text') or ''
        if not text.strip(): errs.append('%s: text is empty' % label)
        style, where = (g('style') or 'caption').lower(), g('where').lower()
        if style == 'caption' and where == 'tag': style, where = 'tag', ''        # older sheets: caption + where tag
        if style not in STYLES: errs.append('%s: unknown style "%s" (supported: %s)' % (label, style, ', '.join(STYLES)))
        shot = g('shot_id')
        if shot and shot not in shot_ids: errs.append('%s: shot_id "%s" is not a shot id' % (label, shot))
        if s is not None and e is not None and style in STYLES:
            out.append({'id': sid, 'start': s, 'end': e, 'text': text, 'style': style, 'where': where, 'shot_id': shot, 'source': g('source'),
                        'draw': True, 'words': len(text.split()), 'visible_frame': first_full_frame(style, s, e)})
    if errs: raise PlanError(errs)
    return out, warns

def apply_holds(strings):
    """anything over 3 words stays at least MIN_HOLD s where the next string in its slot allows. This is a reported repair of text timing only."""
    rep = []
    for d in strings:
        dur = d['end'] - d['start']
        if d['words'] > 3 and dur < MIN_HOLD - 1e-6:
            nxt = [o['start'] for o in strings if o is not d and o['style'] == d['style'] and o['where'] == d['where'] and o['start'] > d['start']]
            lim = min([DUR] + nxt)
            new = min(d['start'] + MIN_HOLD, lim)
            rep.append({'id': d['id'], 'text': d['text'], 'was': round(dur, 3), 'now': round(new - d['start'], 3), 'ok': new - d['start'] >= MIN_HOLD - 1e-6})
            d['end'] = new; d['visible_frame'] = first_full_frame(d['style'], d['start'], d['end'])
    return rep

def resolve_sources(shots):
    for i, ent in enumerate(shots):
        if ent['type'] == 'gen':
            clip = find_clip(ent['clip_id']) if ent['clip_id'] else None
            kf = find_still('k_' + ent['clip_id']) if ent['clip_id'] else None
            if clip: ent.update(source='clip', path=clip)
            elif kf: ent.update(source='keyframe', path=kf)
            else: ent.update(source='grey', path=None, label=ent['clip_id'] or ent['id'])
            ent['push'] = {'z0': 1.10, 'z1': 1.14, 'cx': 0.56 if i % 2 else 0.44, 'cy': 0.46} if ent['reuse_of'] else \
                          {'z0': 1.0, 'z1': 1.04, 'cx': 0.5 + (0.03 if i % 2 else -0.03), 'cy': 0.5}
        else:
            pl = find_still(ent['plate']) if ent['plate'] else None
            if pl: ent.update(source='plate', path=pl)
            else: ent.update(source='grey', path=None, label=ent['plate'] or ent['id'])
            ent['push'] = {'z0': 1.0, 'z1': 1.05, 'cx': 0.5, 'cy': 0.5}
    return shots

def cross_check(shots, strings):
    """errors (unknown ids) and review flags (strings that cross a shot cut)"""
    errs, flags = [], []
    sid = {s['id'] for s in strings}
    for sh in shots:
        for t in sh['text_ids']:
            if t not in sid: errs.append('%s: onscreen_text_ids lists "%s", which is not a string id' % (sh['id'], t))
    for s in strings:
        a, b = fr(s['start']), min(int(math.ceil(s['end'] * FPS - 1e-6)), NF)
        hit = [sh['id'] for sh in shots if sh['f0'] < b and a < sh['f1']]
        if len(hit) > 1: flags.append({'id': s['id'], 'issue': 'string crosses a shot cut', 'shots': hit})
        if s['shot_id'] and hit and s['shot_id'] not in hit: flags.append({'id': s['id'], 'issue': 'shot_id is not a shot the string is on screen in', 'shot_id': s['shot_id'], 'shots': hit})
    if errs: raise PlanError(errs)
    return flags

def fingerprint(edl):
    """short hash of everything that changes how the text layer looks or where it sits; qa_layout.json and the build record it so stale results are caught"""
    keys = ('size', 'fps', 'duration', 'palette', 'fonts', 'safe_margin', 'min_cap_px', 'min_hold', 'text')
    blob = {'settings': {k: P[k] for k in keys},
            'strings': [[s['id'], s['start'], s['end'], s['text'], s['style'], s['where'], s['source']] for s in edl['strings']],
            'shots': [[s['id'], s['f0'], s['f1']] for s in edl['shots']]}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]

def _asset_id(p):
    """identity of a resolved picture file: name, size and modified time (None for a grey placeholder)"""
    if not p: return None
    try: st = os.stat(p)
    except OSError: return [os.path.basename(p), None, None]
    return [os.path.basename(p), st.st_size, st.st_mtime_ns]

def visual_fingerprint(shots):
    """short hash of everything that decides the PICTURE of the base video (no text): frame boundaries, resolved source and file identity,
    clip_in, speed, push-in, size and fps. base.py records it in base_vN_report.json; burn.py refuses a base whose value differs from the
    current plan, so stale pictures never get a current build record. Text edits do not change it."""
    blob = {'size': P['size'], 'fps': P['fps'],
            'shots': [[s['id'], s['f0'], s['f1'], s['type'], s['source'], _asset_id(s.get('path')), s.get('label'), s['clip_in'], s['speed'], s['push']] for s in shots]}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]

def build():
    ensure_out()
    try:
        shots = parse_shots(read_csv(P['shots_csv']))
        strings, warns = parse_strings(read_csv(P['strings_csv']), {s['id'] for s in shots})
        flags = cross_check(shots, strings)
    except PlanError as e:
        raise SystemExit('plan.py: %d problem(s) in the shot or string sheets, nothing was written:\n  - %s' % (len(e.errors), '\n  - '.join(e.errors)))
    hold = apply_holds(strings)
    resolve_sources(shots)
    last_end = max([s['end'] for s in strings] or [0])
    end_hold = max(0.0, min(END_HOLD, last_end - DUR)) if last_end > DUR else 0.0
    ph = [{'id': e['id'], 'type': e['type'], 'clip_id': e['clip_id'] or e['plate'], 'using': e['source']}
          for e in shots if e['source'] in ('keyframe', 'grey')]
    edl = {'duration': DUR, 'fps': FPS, 'nf': NF, 'end_hold_s': end_hold, 'shots': shots, 'strings': strings, 'hold_extensions': hold,
           'warnings': warns, 'review_flags': flags}
    edl['fingerprint'] = fingerprint(edl)
    edl['visual_fingerprint'] = visual_fingerprint(shots)
    write_json(os.path.join(OUT, 'edl.json'), edl)
    write_json(os.path.join(OUT, 'placeholders.json'), ph)
    return edl, ph

def load_edl():
    p = os.path.join(OUT, 'edl.json')
    if not os.path.exists(p): raise SystemExit('no out/edl.json yet: run plan.py')
    return read_json(p)

if __name__ == '__main__':
    if any(a in ('-h', '--help') for a in sys.argv[1:]): print(__doc__); raise SystemExit(0)
    edl, ph = build()
    cnt = {}
    for e in edl['shots']: cnt[e['source']] = cnt.get(e['source'], 0) + 1
    print('%d shots, %d frames (%.3f s), sources: %s' % (len(edl['shots']), edl['shots'][-1]['f1'], edl['shots'][-1]['f1'] / FPS, cnt))
    print('%d shots not on a real clip (keyframe push-in or grey) -> out/placeholders.json' % len(ph))
    print('%d strings, styles: %s' % (len(edl['strings']), dict((st, sum(1 for s in edl['strings'] if s['style'] == st)) for st in STYLES if any(s['style'] == st for s in edl['strings']))))
    print('end hold: %.2f s (last string ends %.2f, song %.2f)' % (edl['end_hold_s'], max([s['end'] for s in edl['strings']] or [0]), DUR))
    for h in edl['hold_extensions']: print('hold extended', h)
    for w in edl['warnings']: print('WARNING', w)
    for f in edl['review_flags']: print('REVIEW', f)
    for e in edl['shots']:
        if e['source'] == 'grey': print('  GREY', e['id'], e['label'])
