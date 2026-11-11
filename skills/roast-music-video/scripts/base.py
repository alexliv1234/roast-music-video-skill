"""base.py -> out/base_vN_nofx.mp4 : size and fps from project.json, hard cuts on the edl times, NO text layer, NO audio, exactly NF frames.
Per shot: the generated clip if present (from clip_in, retimed where the shot notes say "retime"), else the keyframe still with a slow
push-in (so a zero-budget, stills-only animatic builds), else a labelled grey placeholder (stripes drift so it never reads as a frozen frame).
Code shots: the plate still with a slow push-in; burn.py draws their text. Never overwrites a version: always writes the next free N.
A clip that is too short keeps the planned clip_in: the last frame is held and the shortfall is reported (console and base_vN_report.json).
If ffmpeg fails, the partial file is removed and no report is written.
Usage: python base.py [--version N]   (refuses if base_vN_nofx.mp4 already exists)"""
import sys, os, json, subprocess, time
import numpy as np, cv2
from PIL import Image, ImageDraw
from common import *
import plan

def next_version():
    return max(versions('base_v', '_nofx.mp4'), default=0) + 1

def cover(img, w=W, h=H):
    """resize + centre-crop to w x h (clips and stills that are not exactly the project aspect)"""
    ih, iw = img.shape[:2]
    if (iw, ih) == (w, h): return img
    s = max(w / iw, h / ih); nw, nh = int(round(iw * s)), int(round(ih * s))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return r[y0:y0 + h, x0:x0 + w]

class Still:
    """a still with a slow push-in done in code: crop-zoom about (cx,cy), zoom z0 -> z1 over the shot"""
    def __init__(self, img_bgr, push):
        sw, sh = max(W * 3 // 2, 2), max(H * 3 // 2, 2)
        self.src = cover(img_bgr, sw, sh); self.p = push
    def frame(self, u):
        p = self.p; z = p['z0'] + (p['z1'] - p['z0']) * u
        sw, sh = self.src.shape[1], self.src.shape[0]
        vw, vh = sw / z, sh / z
        x0 = min(max(p['cx'] * sw - vw / 2, 0), sw - vw); y0 = min(max(p['cy'] * sh - vh / 2, 0), sh - vh)
        sc = W / vw
        M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
        return cv2.warpAffine(self.src, M, (W, H), flags=cv2.INTER_CUBIC)

def grey_frames(e, n):
    """labelled grey placeholder with drifting stripes"""
    base = np.zeros((H, W, 3), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    base[:] = (62 + 18 * (yy / H))[..., None].astype(np.uint8)
    stripes = (((xx + yy) // max(int(48 * S), 8)) % 2 == 0)
    lab = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lab)
    big, mid, small = font('display', 120 * S), font('display', 36 * S), font('body', 30 * S)
    sub = '%s  |  %s  |  %.2f to %.2f s' % (e.get('label') or e['clip_id'] or e['plate'], e['setup'], e['start'], e['end'])
    d.text((W // 2, int(250 * S)), e['id'], font=big, fill=(225, 225, 230, 255), anchor='mm')
    d.text((W // 2, int(345 * S)), 'PLACEHOLDER  (no clip or keyframe yet)', font=mid, fill=(255, 200, 80, 255), anchor='mm')
    d.text((W // 2, int(392 * S)), sub, font=small, fill=(200, 200, 205, 255), anchor='mm')
    ly = e['lyric'].strip()
    if ly: d.text((W // 2, int(440 * S)), '"' + ly[:60] + '"', font=small, fill=(170, 175, 185, 255), anchor='mm')
    lab_a = np.asarray(lab)
    a = lab_a[..., 3:4].astype(np.float32) / 255
    for k in range(n):
        fr_ = base.astype(np.float32)
        st = np.roll(stripes, k * 2, 1)
        fr_[st] += 7
        fr_ = fr_ * (1 - a) + lab_a[..., :3][..., ::-1] * a        # label is RGB, frame is BGR
        yield np.clip(fr_, 0, 255).astype(np.uint8)

def clip_frames(path_, in_point, n, speed, report):
    """n BGR frames from in_point (s of clip time), stepping `speed` clip-seconds per output second. The requested in_point is kept as
    planned: if the clip runs out, the last frame is held for the rest of the shot and the shortfall is reported."""
    cap = cv2.VideoCapture(path_); fps = cap.get(cv2.CAP_PROP_FPS) or float(FPS)
    skip = int(round(in_point * fps)); idx = 0; last = None; held = 0
    for k in range(n):
        want = skip + int(round(k * speed * fps / FPS))
        im = True
        while idx <= want:
            ok, im = cap.read()
            if not ok: im = None; break
            last = im; idx += 1
        if im is None: held += 1
        yield cover(last) if last is not None else np.zeros((H, W, 3), np.uint8)
    cap.release()
    if held: report.append({'clip': os.path.basename(path_), 'requested_clip_in_s': in_point, 'held_last_frames': held, 'shortfall_s': round(held / FPS, 3)})

def shot_frames(e, report):
    n = e['f1'] - e['f0']
    if e['source'] == 'grey':
        yield from grey_frames(e, n); return
    if e['source'] == 'clip':
        r = []
        yield from clip_frames(e['path'], e['clip_in'], n, e['speed'], r)
        for x in r: x['shot'] = e['id']; report.append(x)
        return
    img = cv2.imread(e['path'])
    if img is None: raise SystemExit('cannot read image ' + e['path'])
    still = Still(img, e['push'])                      # keyframe or plate
    for k in range(n):
        yield still.frame(k / max(n - 1, 1))

def main():
    ffmpeg_ok(); ensure_out()
    ver = next_version()
    if '--version' in sys.argv: ver = int(sys.argv[sys.argv.index('--version') + 1])
    path_ = os.path.join(OUT, 'base_v%d_nofx.mp4' % ver)
    if os.path.exists(path_): raise SystemExit('refusing to overwrite ' + path_)
    t0 = time.time(); edl, ph = plan.build(); report = []
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
           '-color_trc', 'bt709', '-an', '-movflags', '+faststart', path_]
    total = 0
    with Encoder(cmd, path_, 'base encode') as enc:           # removes the partial file and stops with ffmpeg's message on failure
        for e in edl['shots']:
            for img in shot_frames(e, report):
                enc.write(img); total += 1
    if total != NF:
        try: os.remove(path_)
        except OSError: pass
        raise SystemExit('base wrote %d frames but the project needs %d; nothing recorded' % (total, NF))
    write_json(os.path.join(OUT, 'base_v%d_report.json' % ver),       # the manifest is written only after the encode succeeded
               {'base': os.path.basename(path_), 'frames': total, 'placeholders': len(ph), 'clip_shortfalls': report, 'fingerprint': edl['fingerprint'],
                'visual_fingerprint': edl['visual_fingerprint']})
    print('base v%d: %d frames (expect %d = %.2f s), %d shots not on a real clip, %d clip shortfalls, %.1f s' % (ver, total, NF, NF / FPS, len(ph), len(report), time.time() - t0))
    for r in report: print('  SHORT CLIP %s: requested clip_in %.2f s, last frame held for %d frames (%.2f s)' % (r['shot'], r['requested_clip_in_s'], r['held_last_frames'], r['shortfall_s']))

if __name__ == '__main__':
    if any(a in ('-h', '--help') for a in sys.argv[1:]): print(__doc__); raise SystemExit(0)
    main()
