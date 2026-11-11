"""validate_assets.py : what is ready, what is missing, what is wrong.
Checks the song (audio/song_master.* or project.json `song`): readable, has an audio stream, and its real duration matches project.json
`duration` within 0.25 s (a longer song is accepted only with "allow_trim": true). Then the shot sheet is validated like plan.py does
(contiguous timeline, unique ids, reuse_of resolved to the referenced shot's clip) and for every shot:
  gen shots  : footage/final/<clip_id>_vN.mp4 (highest N)  -> exists, long enough for the shot (from clip_in), size, fps
               frames/k_<clip_id>.png|jpg|webp (keyframe)  -> exists, size, aspect (a wrong aspect is WRONG: it would be centre-cropped)
  code shots : frames/<plate>.png|jpg|webp                  -> exists, size, aspect
Status per row:  READY (a real clip, or a plate)   KEYFRAME-ONLY (no clip: the animatic uses a slow push-in on the still, which is fine)
                 MISSING (neither clip nor keyframe: grey placeholder)   WRONG (file exists but too short / wrong size / unreadable)
Use it after generating files by hand in a web app: drop each file into place, run this, and see what is left.
Usage: python validate_assets.py [--strict]     (--strict: exit 1 if any row is MISSING or WRONG; a missing or bad song, or a bad shot sheet, always exits 1)"""
import os, sys
from PIL import Image
from common import *
import plan

if any(a in ('-h', '--help') for a in sys.argv[1:]):
    print(__doc__); raise SystemExit(0)

def img_size(p):
    try:
        with Image.open(p) as im: return im.size
    except Exception: return None

def check_clip(p, need_s):
    info = probe_media(p)
    if not info or not info['w']: return 'WRONG', 'unreadable video'
    issues = []
    if info['dur'] + 0.05 < need_s: issues.append('%.2f s long, shot needs %.2f s (from its clip_in)' % (info['dur'], need_s))
    if info['w'] < W or info['h'] < H: issues.append('%dx%d is smaller than %dx%d' % (info['w'], info['h'], W, H))
    elif abs(info['w'] / info['h'] - W / H) > 0.02: issues.append('%dx%d is not %d:%d (will be centre-cropped)' % (info['w'], info['h'], W, H))
    if info['fps'] and abs(info['fps'] - FPS) > 0.5: issues.append('%.2f fps (project %d, frames are resampled)' % (info['fps'], FPS))
    detail = '%dx%d %.2f s %.0f fps' % (info['w'], info['h'], info['dur'], info['fps'] or 0)
    bad = [i for i in issues if 'long' in i or 'smaller' in i]
    return ('WRONG' if bad else 'READY'), (detail + ('; ' + '; '.join(issues) if issues else ''))

def check_still(p):
    sz_ = img_size(p)
    if not sz_: return 'WRONG', 'unreadable image'
    if sz_[0] < W or sz_[1] < H: return 'WRONG', '%dx%d is smaller than %dx%d' % (sz_[0], sz_[1], W, H)
    if abs(sz_[0] / sz_[1] - W / H) > 0.02:
        return 'WRONG', '%dx%d is not %d:%d: it would be centre-cropped; regenerate or re-export it in the project aspect' % (sz_[0], sz_[1], W, H)
    return 'READY', '%dx%d' % sz_

def main():
    ffmpeg_ok()
    rows = []
    song = find_song()
    if not song: rows.append(('song', '-', 'MISSING', 'expected %s.* (mp3, wav, m4a, flac)' % P['song']))
    else:
        info = probe_media(song); bad = song_problems(info)
        if bad: rows.append(('song', os.path.basename(song), 'WRONG', '; '.join(bad)))
        else: rows.append(('song', os.path.basename(song), 'READY', '%.2f s (project %.2f s)%s' % (info['dur'], DUR, ', will be trimmed (allow_trim)' if info['dur'] - DUR > SONG_TOLERANCE else '')))
    try: shots = plan.parse_shots(read_csv(P['shots_csv']))
    except plan.PlanError as e:
        print('shot sheet problems (fix these first; plan.py will refuse to run):')
        for m in e.errors: print('  -', m)
        sys.exit(1)
    for sh in shots:
        sid, typ = sh['id'], sh['type']
        need = sh['end'] - sh['start']
        if typ == 'gen':
            cid = sh['clip_id']
            if not cid: rows.append((sid, '-', 'WRONG', 'gen shot has no clip_id (and no reuse_of)')); continue
            need_c = sh['clip_in'] + need * sh['speed']
            clip, kf = find_clip(cid), find_still('k_' + cid)
            if clip:
                st, d = check_clip(clip, need_c); rows.append((sid, os.path.basename(clip), st, d))
            elif kf:
                st, d = check_still(kf)
                rows.append((sid, os.path.basename(kf), 'KEYFRAME-ONLY' if st == 'READY' else st, ('no clip yet, slow push-in on the still; ' if st == 'READY' else '') + d))
            else:
                rows.append((sid, 'k_%s.* / %s_vN.mp4' % (cid, cid), 'MISSING', 'neither a clip nor a keyframe: grey placeholder'))
        else:
            pl = sh['plate']; p = find_still(pl) if pl else None
            if p:
                st, d = check_still(p); rows.append((sid, os.path.basename(p), st, d))
            else: rows.append((sid, (pl or '(no plate)') + '.*', 'MISSING', 'code shot needs a plate still in %s' % P['dirs']['frames']))
    w = [max(len(str(x[i])) for x in rows + [('shot', 'file', 'status', 'detail')]) for i in range(3)]
    print('%-*s  %-*s  %-*s  %s' % (w[0], 'shot', w[1], 'file', w[2], 'status', 'detail'))
    for r in rows: print('%-*s  %-*s  %-*s  %s' % (w[0], r[0], w[1], r[1], w[2], r[2], r[3]))
    cnt = {}
    for r in rows: cnt[r[2]] = cnt.get(r[2], 0) + 1
    print('\nsummary:', ', '.join('%s %d' % (k, v) for k, v in sorted(cnt.items())))
    if cnt.get('KEYFRAME-ONLY'): print('KEYFRAME-ONLY shots build fine as a stills animatic; add <clip_id>_vN.mp4 later to upgrade them.')
    prov = P.get('providers') or {}
    if cnt.get('MISSING') and prov:
        for role, cfg in prov.items():
            if isinstance(cfg, dict) and cfg.get('mode') == 'manual' and cfg.get('notes'): print('note (%s, manual): %s' % (role, cfg['notes']))
    song_bad = rows[0][2] in ('WRONG', 'MISSING') and rows[0][0] == 'song'
    if song_bad: print('The song row must be fixed before building.')
    if song_bad or ('--strict' in sys.argv and (cnt.get('MISSING') or cnt.get('WRONG'))): sys.exit(1)

if __name__ == '__main__':
    main()
