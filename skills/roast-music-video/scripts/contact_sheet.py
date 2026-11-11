"""contact_sheet.py : labelled contact sheets, and one labelled frame per string for reviewers.
  python contact_sheet.py frames/                    every image in a folder, labelled with its file name
  python contact_sheet.py out/animatic_v1.mp4        a video, one frame per shot at the shot midpoint (shots from <out>/edl.json,
                                                     or from the configured shots csv, or evenly spaced with --every SECONDS)
  python contact_sheet.py out/animatic_v1.mp4 --strings
                                                     one full-size PNG per string in <out>/edl.json, taken at the first frame on which
                                                     that string is fully visible (fade, slam or wipe finished), labelled with the string id,
                                                     style, time, frame number and text -> <out>/string_frames/<id>_<style>_t<seconds>.png
                                                     plus string_frames/index.json. Use these as reviewer evidence.
Options: --out PATH (sheet: default <out>/contact.png; --strings: a folder, default <out>/string_frames)
         --cols 4  --tile 480 (tile width px)  --rows 3 (rows per sheet; more sheets are written)  --every SECONDS (video without an edl)
Paths: the project folder is ROAST_PROJECT_DIR if set, else the current folder; <out>, the shots csv and project.json settings are read from it.
Works standalone: needs only Pillow (and OpenCV for video). Reads project.json only if present."""
import os, sys, csv, json, glob, math, argparse
from PIL import Image, ImageDraw, ImageFont
from roots import project_root, raw_project, under_root, out_dir, read_json, write_json

IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')

def label_font(sz):
    for n in ('arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf', 'Helvetica.ttc', 'NotoSans-Regular.ttf'):
        try: return ImageFont.truetype(n, sz)
        except OSError: pass
    try: return ImageFont.load_default(sz)
    except TypeError: return ImageFont.load_default()

def shots_for_video(fps, nframes, root):
    """[(label, frame_index)] from <out>/edl.json, else the configured shots csv, else None"""
    p = os.path.join(out_dir(root), 'edl.json')
    if os.path.exists(p):
        e = read_json(p)
        return [('%s  %.1fs' % (s['id'], s['start']), min((s['f0'] + s['f1']) // 2, nframes - 1)) for s in e['shots']]
    c = under_root(raw_project(root).get('shots_csv') or 'shots.csv', root)
    if os.path.exists(c):
        with open(c, encoding='utf-8-sig', newline='') as fh: rows = list(csv.DictReader(fh))
        return [('%s  %.1fs' % (r['id'], float(r['start'])), min(int(round((float(r['start']) + float(r['end'])) / 2 * fps)), nframes - 1)) for r in rows]
    return None

def export_strings(video, outdir, root):
    import cv2
    p = os.path.join(out_dir(root), 'edl.json')
    if not os.path.exists(p): raise SystemExit('no %s: run plan.py first (--strings needs the string list)' % p)
    edl = read_json(p); fps = float(edl.get('fps') or 24)
    cap = cv2.VideoCapture(video)
    if not cap.isOpened(): raise SystemExit('cannot open video ' + video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); os.makedirs(outdir, exist_ok=True)
    index = []
    for s in edl['strings']:
        k = s.get('visible_frame')
        if k is None: k = int(math.ceil((s['start'] + 0.3) * fps))
        k = max(0, min(int(k), n - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, im = cap.read()
        if not ok: print('skip %s: cannot read frame %d' % (s['id'], k), file=sys.stderr); continue
        img = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)); w, h = img.size
        bar = max(int(h * 0.06), 22); fnt = label_font(max(int(bar * 0.6), 11))
        out = Image.new('RGB', (w, h + bar), (16, 16, 22)); out.paste(img, (0, bar)); d = ImageDraw.Draw(out)
        d.text((8, 4), '%s  %s  t=%.2fs  frame %d  "%s"' % (s['id'], s['style'], k / fps, k, s['text'].replace('\n', ' ')[:90]), font=fnt, fill=(255, 220, 90))
        name = '%s_%s_t%.2f.png' % (s['id'], s['style'], k / fps)
        out.save(os.path.join(outdir, name))
        index.append({'id': s['id'], 'style': s['style'], 'frame': k, 'time': round(k / fps, 3), 'file': name, 'text': s['text']})
    cap.release()
    write_json(os.path.join(outdir, 'index.json'), index)
    print('%d string frames -> %s' % (len(index), outdir))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', help='folder of images, or a video file')
    ap.add_argument('--out', default=None); ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--tile', type=int, default=480); ap.add_argument('--rows', type=int, default=3)
    ap.add_argument('--every', type=float, default=None)
    ap.add_argument('--strings', action='store_true', help='export one labelled frame per string (first fully visible frame) instead of a sheet')
    a = ap.parse_args()
    if a.cols < 1 or a.rows < 1: ap.error('--cols and --rows must be 1 or more')
    if a.tile < 16: ap.error('--tile must be at least 16 pixels')
    if a.every is not None and not (a.every > 0 and math.isfinite(a.every)): ap.error('--every must be a positive number of seconds')
    root = project_root()
    src = under_root(a.source, root)                    # relative paths are under the project folder; absolute ones are kept
    if a.strings:
        if not os.path.isfile(src): raise SystemExit('--strings needs a video file: ' + a.source)
        export_strings(src, under_root(a.out, root) if a.out else os.path.join(out_dir(root), 'string_frames'), root); return
    items = []                                           # (label, PIL image)
    if os.path.isdir(src):
        files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.lower().endswith(IMG_EXT))
        if not files: raise SystemExit('no images in ' + a.source)
        for f in files:
            try: items.append((os.path.basename(f), Image.open(f).convert('RGB')))
            except Exception as e: print('skip', f, e, file=sys.stderr)
    elif os.path.isfile(src):
        import cv2
        cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS) or 24.0; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n < 1: raise SystemExit('cannot read frames from ' + a.source)
        picks = None if a.every else shots_for_video(fps, n, root)
        if not picks:
            step = a.every or max(n / fps / 12, 0.5)
            picks = [('%.1fs' % (k * step), min(int(round(k * step * fps)), n - 1)) for k in range(int(n / fps / step) + 1)]
        for label, k in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, im = cap.read()
            if ok: items.append((label, Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))))
        cap.release()
    else:
        raise SystemExit('not a folder or file: ' + a.source)
    if not items: raise SystemExit('nothing to draw')
    tw = a.tile; ar = items[0][1].height / items[0][1].width; th = int(round(tw * ar)); lab_h = max(int(tw * 0.06), 18)
    fnt = label_font(max(int(lab_h * 0.7), 10)); per = a.cols * a.rows
    out = under_root(a.out, root) if a.out else os.path.join(out_dir(root), 'contact.png'); os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    base, ext = os.path.splitext(out); written = []
    for n0 in range(0, len(items), per):
        chunk = items[n0:n0 + per]; rows = (len(chunk) + a.cols - 1) // a.cols
        sheet = Image.new('RGB', (a.cols * tw, rows * (th + lab_h)), (16, 16, 22)); d = ImageDraw.Draw(sheet)
        for k, (lab, im) in enumerate(chunk):
            x, y = (k % a.cols) * tw, (k // a.cols) * (th + lab_h)
            sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + lab_h))
            d.text((x + 6, y + 3), lab, font=fnt, fill=(255, 220, 90))
        p = out if len(items) <= per else '%s_%d%s' % (base, n0 // per + 1, ext)
        sheet.save(p); written.append(p)
    print('%d tiles -> %s' % (len(items), ', '.join(written)))

if __name__ == '__main__':
    main()
