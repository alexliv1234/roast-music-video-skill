"""common.py : shared project settings, fonts, text helpers, process helpers and the Frame registry.

Every project-specific value comes from project.json in the project root: the folder named by the ROAST_PROJECT_DIR environment
variable if set, otherwise the current working directory (see roots.py). The scripts themselves live in the installed skill folder;
run them with the project folder as the working directory.
Everything drawn is a pure function of song time. All type is drawn with Pillow (no ffmpeg drawtext)."""
import os, sys, json, glob, re, math, functools, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from roots import project_root, read_json, write_json   # noqa: F401  (re-exported for the other scripts)

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = project_root()
PROJECT_FILE = os.path.join(ROOT, 'project.json')

STYLES = ('caption', 'hook', 'namecard', 'bubble', 'card', 'tag', 'end')
PROVIDER_MODES = ('mcp', 'cli', 'manual', 'none')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')

DEFAULTS = {
    'name': 'film',
    'subject': '',                         # who or what the film is about (agent gates read this; no script uses it)
    'consent': {'given': False, 'evidence': ''},
    'audience': '',
    'off_limits': [],
    'budget': {'total': 0, 'currency': 'credits', 'reserve': 0, 'retake_cap': 0},
    'duration': 30.0,
    'allow_trim': False,                   # True: a song longer than `duration` may be cut to `duration` on purpose
    'fps': 24,
    'size': [1280, 720],
    'song': 'audio/song_master',          # a file, or a stem: audio/song_master.* is searched
    'dirs': {'footage': 'footage/final', 'frames': 'frames', 'out': 'out', 'audio': 'audio'},
    'shots_csv': 'shots.csv',
    'strings_csv': 'strings.csv',
    'palette': {'ink': '#14141A', 'paper': '#F5F1E8', 'accent': '#FFC845', 'accent2': '#E8486B', 'panel': '#1F4E79'},
    'fonts': {'display': '', 'body': '', 'mono': ''},
    'retime': 0.98,                        # speed for shots whose notes contain "retime"
    'safe_margin': 0.05,                   # title safe area as a fraction of each side
    'min_cap_px': None,                    # default 28 px at 720p, scaled to the frame height
    'min_hold': 1.0,                       # seconds on screen for any string over 3 words
    'loudness': {'target_lufs': -14.0, 'true_peak': -1.5, 'lra': 11},
    'text': {                              # reference values at 720p high, scaled by height / 720
        'caption_size': 46, 'caption_bottom': 0.922, 'caption_max_width': 0.81,
        'tag_size': 40, 'namecard_bottom': 0.72, 'namecard_name_size': 46, 'namecard_role_size': 40,
        'hook_size': 150, 'hook_center': [0.5, 0.44], 'hook_angle': 3.0,
        'bubble_size': 40, 'bubble_max_width': 0.42, 'title_size': 110, 'card_size': 80, 'end_size': 110,
    },
    'banned_terms': [],
    'providers': {},
}

def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out

def load_project(required=True):
    if not os.path.exists(PROJECT_FILE):
        if required:
            raise SystemExit('project.json not found in %s\nRun from the project folder (copy project.example.json to project.json first), '
                             'or set ROAST_PROJECT_DIR.' % ROOT)
        return json.loads(json.dumps(DEFAULTS))
    try:
        raw = read_json(PROJECT_FILE)
    except ValueError as e:
        raise SystemExit('project.json is not valid JSON: %s' % e)
    if not isinstance(raw, dict): raise SystemExit('project.json must hold one JSON object')
    return _merge(DEFAULTS, {k: v for k, v in raw.items() if not k.startswith('_')})

# ----------------------------------------------------------------------------- settings validation
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def validate_settings(p):
    """list of human-readable problems with the numeric and structural settings (empty list = fine)"""
    bad = []
    def need(cond, msg):
        if not cond: bad.append(msg)
    need(_num(p['duration']) and p['duration'] > 0, 'duration must be a positive number of seconds')
    need(_num(p['fps']) and 0 < p['fps'] <= 240 and float(p['fps']).is_integer(), 'fps must be a whole number from 1 to 240')
    sz = p['size']
    ok_sz = isinstance(sz, list) and len(sz) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in sz)
    need(ok_sz, 'size must be [width, height] in whole pixels, both above 0')
    if ok_sz: need(sz[0] % 2 == 0 and sz[1] % 2 == 0, 'size %s must have even width and height (yuv420p needs it)' % sz)
    need(_num(p['retime']) and 0.25 <= p['retime'] <= 4, 'retime must be a number from 0.25 to 4 (0.98 = play at 98 percent)')
    need(_num(p['safe_margin']) and 0 <= p['safe_margin'] < 0.25, 'safe_margin must be from 0 up to (not including) 0.25')
    need(p['min_cap_px'] is None or (_num(p['min_cap_px']) and p['min_cap_px'] > 0), 'min_cap_px must be null or a positive number')
    need(_num(p['min_hold']) and p['min_hold'] >= 0, 'min_hold must be 0 or more seconds')
    need(isinstance(p['allow_trim'], bool), 'allow_trim must be true or false')
    ld = p['loudness']
    need(isinstance(ld, dict) and all(_num(ld.get(k)) for k in ('target_lufs', 'true_peak', 'lra')), 'loudness needs numeric target_lufs, true_peak and lra')
    tx = p['text']
    for k, v in tx.items():
        if k.endswith('_size'): need(_num(v) and v > 0, 'text.%s must be a positive number' % k)
        elif k.endswith('_max_width') or k.endswith('_bottom'): need(_num(v) and 0 < v <= 1, 'text.%s must be above 0 and at most 1' % k)
    hc = tx.get('hook_center')
    need(isinstance(hc, list) and len(hc) == 2 and all(_num(x) and 0 <= x <= 1 for x in hc), 'text.hook_center must be [x, y], each from 0 to 1')
    need(_num(tx.get('hook_angle')), 'text.hook_angle must be a number of degrees')
    b = p['budget']
    need(isinstance(b, dict) and all(_num(b.get(k)) and b[k] >= 0 for k in ('total', 'reserve', 'retake_cap')),
         'budget.total, budget.reserve and budget.retake_cap must be numbers of 0 or more')
    need(isinstance(p['consent'], dict) and isinstance(p['consent'].get('given'), bool), 'consent.given must be true or false')
    need(isinstance(p['off_limits'], list), 'off_limits must be a list')
    need(isinstance(p['banned_terms'], list), 'banned_terms must be a list')
    for role, cfg in (p['providers'] or {}).items():
        if isinstance(cfg, dict) and 'mode' in cfg:
            need(cfg['mode'] in PROVIDER_MODES, 'providers.%s.mode "%s" must be one of %s' % (role, cfg['mode'], ', '.join(PROVIDER_MODES)))
    return bad

P = load_project(required=not any(a in ('-h', '--help') for a in sys.argv[1:]))
_problems = validate_settings(P)
if _problems:
    raise SystemExit('project.json has invalid settings:\n  - ' + '\n  - '.join(_problems))
if 'stt' in (P['providers'] or {}):
    print('WARNING: providers.stt is the old name; rename it to providers.transcription', file=sys.stderr)

W, H = int(P['size'][0]), int(P['size'][1])
FPS = int(P['fps'])
DUR = float(P['duration'])
NF = int(round(DUR * FPS))
S = H / 720.0                                # scale for reference sizes
SAFE_M = float(P['safe_margin'])
SAFE = (int(W * SAFE_M), int(H * SAFE_M), int(W * (1 - SAFE_M)), int(H * (1 - SAFE_M)))
MIN_CAP = P['min_cap_px'] if P['min_cap_px'] is not None else 28 * S
MIN_HOLD = float(P['min_hold'])
RETIME = float(P['retime'])
ALLOW_TRIM = bool(P['allow_trim'])
TX = P['text']

def path(*parts): return os.path.join(ROOT, *parts)
OUT = path(P['dirs']['out'])
FOOT = path(P['dirs']['footage'])
FRAMES = path(P['dirs']['frames'])
AUDIO_DIR = path(P['dirs']['audio'])
LOUD = P['loudness']

def ensure_out(): os.makedirs(OUT, exist_ok=True)

def find_song():
    """the song file: project.json `song` if it is a file, else <song>.* (mp3, wav, m4a, flac ...), else None"""
    s = path(P['song'])
    if os.path.isfile(s): return s
    hits = sorted(g for g in glob.glob(s + '.*') if os.path.isfile(g))
    return hits[0] if hits else None

def rgb(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
PAL = {k: rgb(v) for k, v in P['palette'].items()}
INK, PAPER, ACCENT, ACCENT2, PANEL = (PAL.get(k, d) for k, d in
    (('ink', (27, 27, 31)), ('paper', (255, 244, 220)), ('accent', (242, 182, 50)), ('accent2', (255, 61, 127)), ('panel', (15, 76, 92))))

def fr(t): return int(round(t * FPS))

# seconds a style needs to become fully visible after its start (used by burn.py fades and by the "first fully visible frame")
IN_SECONDS = {'caption': 0.12, 'tag': 0.12, 'namecard': 0.3, 'bubble': 0.18, 'card': 0.25, 'end': 0.25}

def first_full_frame(style, start, end):
    """index of the first frame on which a string is fully drawn (fade, slam or wipe finished), kept inside its own on-screen frames"""
    inn = 3.0 / FPS if style == 'hook' else IN_SECONDS.get(style, 0.2)
    k = int(math.ceil((start + inn) * FPS - 1e-6))
    last = int(math.ceil(end * FPS - 1e-6)) - 1
    return max(0, min(k, last, NF - 1))

def needs_source(text):
    """a string with a digit or a quotation mark is a claim: it must carry a `source`"""
    return bool(re.search(r'\d', text) or re.search(r'["\u201c\u201d]', text))

# ----------------------------------------------------------------------------- fonts
_SYSTEM_FONTS = {   # lower-case file names, best first
    'display': ['arialbd.ttf', 'arial bold.ttf', 'helveticaneue.ttc', 'helvetica.ttc', 'dejavusans-bold.ttf', 'liberationsans-bold.ttf',
                'notosans-bold.ttf', 'freesansbold.ttf', 'segoeuib.ttf'],
    'body': ['arial.ttf', 'helveticaneue.ttc', 'helvetica.ttc', 'dejavusans.ttf', 'liberationsans-regular.ttf', 'notosans-regular.ttf',
             'freesans.ttf', 'segoeui.ttf'],
    'mono': ['consola.ttf', 'courier new.ttf', 'menlo.ttc', 'dejavusansmono.ttf', 'liberationmono-regular.ttf', 'notosansmono-regular.ttf', 'cour.ttf'],
}

def system_font_dirs():
    """common font folders on Windows, macOS and Linux (only existing ones are searched)"""
    home = os.path.expanduser('~'); win = os.environ.get('WINDIR') or os.environ.get('SystemRoot') or 'C:/Windows'
    local = os.environ.get('LOCALAPPDATA') or os.path.join(home, 'AppData', 'Local')
    cands = [os.path.join(win, 'Fonts'), os.path.join(local, 'Microsoft', 'Windows', 'Fonts'),
             '/System/Library/Fonts', '/System/Library/Fonts/Supplemental', '/Library/Fonts', os.path.join(home, 'Library', 'Fonts'),
             '/usr/share/fonts', '/usr/local/share/fonts', os.path.join(home, '.fonts'), os.path.join(home, '.local', 'share', 'fonts')]
    return [d for d in cands if os.path.isdir(d)]

@functools.lru_cache(maxsize=None)
def _font_index():
    idx = {}
    for d in system_font_dirs():
        for root, _, files in os.walk(d):
            for f in files:
                idx.setdefault(f.lower(), os.path.join(root, f))
    return idx

_warned = set()
def _warn_once(key, msg):
    if key not in _warned: _warned.add(key); print('WARNING: ' + msg, file=sys.stderr)

@functools.lru_cache(maxsize=None)
def _font_path(role):
    want = (P['fonts'].get(role) or '').strip()
    if want:
        p = want if os.path.isabs(want) else path(want)
        if os.path.isfile(p): return p
        _warn_once(role + 'missing', 'font for role "%s" not found at %s; falling back to a system font' % (role, want))
    else:
        _warn_once(role + 'unset', 'project.json fonts.%s is not set; using a system font. Set a path to a .ttf you are licensed to use.' % role)
    idx = _font_index()
    for name in _SYSTEM_FONTS.get(role, _SYSTEM_FONTS['body']):
        if name in idx:
            _warn_once(role + 'used', 'fonts.%s fallback is %s' % (role, idx[name])); return idx[name]
    return None

@functools.lru_cache(maxsize=None)
def font(role, size):
    p = _font_path(role)
    if p:
        try: return ImageFont.truetype(p, int(size))
        except OSError: _warn_once(role + 'bad', 'could not open font %s' % p)
    _warn_once('nofont', 'no TrueType font found; using the Pillow default font (small and plain)')
    try: return ImageFont.load_default(int(size))
    except TypeError: return ImageFont.load_default()

@functools.lru_cache(maxsize=None)
def cap_height(role, size):
    b = font(role, size).getbbox('H'); return b[3] - b[1]

def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def ease_out(p): p = clamp(p); return 1 - (1 - p) ** 3
def ease_io(p): p = clamp(p); return p * p * (3 - 2 * p)

@functools.lru_cache(maxsize=None)
def text_img(s, role, size, fill, stroke, stroke_fill, shadow, track):
    """tight RGBA image of one line; stroke = outline px, shadow = (dx,dy) hard drop shadow, track = letter spacing px"""
    f = font(role, size)
    pad = stroke + (max(abs(shadow[0]), abs(shadow[1])) if shadow else 0) + 3
    w = (sum(f.getlength(c) + track for c in s) - track) if track else f.getlength(s)
    asc, desc = f.getmetrics()
    im = Image.new('RGBA', (int(w) + 2 * pad + 2, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def put(ox, oy, col, sw):
        sf = tuple(stroke_fill) + (255,) if sw else None
        if not track:
            d.text((pad + ox, pad + oy), s, font=f, fill=tuple(col) + (255,), stroke_width=sw, stroke_fill=sf)
        else:
            x = pad + ox
            for c in s:
                d.text((x, pad + oy), c, font=f, fill=tuple(col) + (255,), stroke_width=sw, stroke_fill=sf)
                x += f.getlength(c) + track
    if shadow: put(shadow[0], shadow[1], stroke_fill if stroke else INK, stroke)
    put(0, 0, fill, stroke)
    return im

def T(s, role='body', size=30, fill=None, stroke=0, stroke_fill=None, shadow=None, track=0):
    return text_img(s, role, int(size), tuple(fill or PAPER), int(stroke), tuple(stroke_fill or INK), tuple(shadow) if shadow else None, track)

def twidth(s, role, size, track=0):
    f = font(role, size)
    return sum(f.getlength(c) + track for c in s) - track if track else f.getlength(s)

def _greedy(words, role, size, maxw, track):
    lines = []; cur = ''
    for w in words:
        t = (cur + ' ' + w) if cur else w
        if twidth(t, role, size, track) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines

def wrap(s, role, size, maxw, track=0):
    """greedy word wrap, then balanced: shrink the target width while the line count holds. An explicit newline always starts a new line
    (each piece is wrapped on its own), so callers draw every returned line separately."""
    if '\n' in s:
        return [ln for part in s.split('\n') for ln in wrap(part, role, size, maxw, track)]
    words = s.split(' ')
    lines = _greedy(words, role, size, maxw, track)
    if len(lines) > 1:
        n = len(lines); lo, hi = maxw * 0.4, maxw; best = lines
        for _ in range(12):
            mid = (lo + hi) / 2; ls = _greedy(words, role, size, mid, track)
            if len(ls) <= n: hi = mid; best = ls
            else: lo = mid
        lines = best
    return lines

class Frame:
    """a PIL RGB canvas plus a registry of every text element drawn (for the overlap / safe-area / size QA)."""
    def __init__(self, arr_rgb, qa=False):
        self.im = Image.fromarray(arr_rgb) if arr_rgb is not None else Image.new('RGB', (W, H), (0, 0, 0))
        self.qa = qa
        self.rects = []

    def put(self, layer, x, y, alpha=1.0, clip=None):
        if alpha <= 0.003 or self.qa: return      # qa frames only collect rects, nothing is composited
        x, y = int(round(x)), int(round(y))
        cx0, cy0, cx1, cy1 = [int(round(v)) for v in clip] if clip is not None else (0, 0, W, H)
        cx0, cy0, cx1, cy1 = max(cx0, 0), max(cy0, 0), min(cx1, W), min(cy1, H)
        l, t = max(x, cx0), max(y, cy0)
        r, b = min(x + layer.width, cx1), min(y + layer.height, cy1)
        if r <= l or b <= t: return
        if (l, t, r, b) != (x, y, x + layer.width, y + layer.height):
            layer = layer.crop((l - x, t - y, r - x, b - y)); x, y = l, t
        a = layer.getchannel('A')
        if alpha < 0.999: a = a.point(lambda v, k=alpha: int(v * k))
        self.im.paste(layer.convert('RGB'), (x, y), a)

    def reg(self, kind, name, rect, ids=(), cap=None, text=None):
        """register an element for QA (rect = visible box that carries the text, in frame coords)"""
        if self.qa:
            self.rects.append({'kind': kind, 'name': name, 'rect': [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])],
                               'ids': list(ids), 'cap': cap, 'text': text})

    def arr(self): return np.asarray(self.im)

def rotate_layer(im, deg):
    return im.rotate(deg, resample=Image.BICUBIC, expand=True)

def with_shadow(layer, dx=7, dy=9, alpha=130, blur=5):
    pad = blur * 2 + 6
    base = Image.new('RGBA', (layer.width + abs(dx) + 2 * pad, layer.height + abs(dy) + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', layer.size, (0, 0, 0, 0)); sh.putalpha(layer.getchannel('A').point(lambda v: int(v * alpha / 255)))
    base.alpha_composite(sh, (pad + max(dx, 0), pad + max(dy, 0)))
    if blur: base = base.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(layer, (pad, pad))
    return base, pad

# ----------------------------------------------------------------------------- shared helpers
def read_csv(rel):
    import csv
    p = path(rel)
    if not os.path.exists(p): raise SystemExit('missing %s (see project.example.json and the README for the columns)' % rel)
    with open(p, encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))

def find_clip(cid):
    """highest <id>_vN.mp4 in the footage folder, or None"""
    best, bv = None, -1
    for p in glob.glob(os.path.join(FOOT, cid + '_v*.mp4')):
        m = re.search(r'_v(\d+)\.mp4$', p)
        if m and int(m.group(1)) > bv: best, bv = p, int(m.group(1))
    return best

def find_still(stem):
    for ext in ('.png', '.jpg', '.jpeg', '.webp'):
        p = os.path.join(FRAMES, stem + ext)
        if os.path.exists(p) and os.path.getsize(p) > 200: return p
    return None

def versions(prefix, suffix):
    out = []
    for p in glob.glob(os.path.join(OUT, prefix + '*' + suffix)):
        m = re.search(re.escape(prefix) + r'(\d+)' + re.escape(suffix) + '$', os.path.basename(p))
        if m: out.append(int(m.group(1)))
    return sorted(out)

def ffmpeg_ok():
    import shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise SystemExit('ffmpeg and ffprobe must be on PATH')

# ----------------------------------------------------------------------------- subprocess helpers
def _tail(text, n=1500):
    text = (text or '').strip()
    return text[-n:]

def run_cmd(cmd, what):
    """run a command, capture text output, and stop with an actionable message (including its stderr) if it fails"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except OSError as e:
        raise SystemExit('%s: could not start %s (%s)' % (what, cmd[0], e))
    if p.returncode != 0:
        raise SystemExit('%s failed (exit %d):\n%s' % (what, p.returncode, _tail(p.stderr)))
    return p

class Encoder:
    """feeds raw frames to ffmpeg. As a context manager it removes a partial output file and stops with ffmpeg's own error text if the encode fails."""
    def __init__(self, cmd, out_path, what='ffmpeg encode'):
        self.cmd, self.out, self.what = cmd, out_path, what
    def __enter__(self):
        self.err = tempfile.TemporaryFile()
        try: self.p = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stderr=self.err)
        except OSError as e: raise SystemExit('%s: could not start ffmpeg (%s)' % (self.what, e))
        return self
    def write(self, arr):
        try: self.p.stdin.write(np.ascontiguousarray(arr).tobytes())
        except (BrokenPipeError, OSError): pass              # the real reason is in ffmpeg's stderr; reported on exit
    def _stderr(self):
        self.err.seek(0); return self.err.read().decode('utf-8', 'replace')
    def _drop(self):
        try: os.remove(self.out)
        except OSError: pass
    def __exit__(self, et, ev, tb):
        try: self.p.stdin.close()
        except OSError: pass
        if et is not None:
            self.p.kill(); self.p.wait(); self._drop(); self.err.close(); return False
        rc = self.p.wait(); msg = _tail(self._stderr()); self.err.close()
        if rc != 0:
            self._drop(); raise SystemExit('%s failed (exit %d); partial output removed.\n%s' % (self.what, rc, msg))
        return False

def probe_media(p):
    """{'dur','w','h','fps','has_audio','has_video'} for a media file via ffprobe, or None if it cannot be read"""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,r_frame_rate,duration',
                            '-show_entries', 'format=duration', '-of', 'json', p], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0: return None
        j = json.loads(r.stdout)
    except (OSError, ValueError):
        return None
    v = [s for s in j.get('streams', []) if s.get('codec_type') == 'video']
    a = [s for s in j.get('streams', []) if s.get('codec_type') == 'audio']
    fps = None
    if v and v[0].get('r_frame_rate', '0/0') not in ('0/0', ''):
        n, d = v[0]['r_frame_rate'].split('/')
        fps = float(n) / float(d) if float(d) else None
    try: dur = float(j.get('format', {}).get('duration') or (v[0].get('duration') if v else 0) or 0)
    except (TypeError, ValueError): dur = 0.0
    return {'dur': dur, 'w': v[0].get('width') if v else None, 'h': v[0].get('height') if v else None, 'fps': fps,
            'has_audio': bool(a), 'has_video': bool(v)}

SONG_TOLERANCE = 0.25

def song_problems(info):
    """why the song cannot be used for this project, as a list of strings (empty = fine). Uses the real duration of the file."""
    if not info: return ['song file is unreadable by ffprobe']
    bad = []
    if not info['has_audio']: bad.append('song file has no audio stream')
    diff = info['dur'] - DUR
    if abs(diff) > SONG_TOLERANCE:
        if diff > 0 and ALLOW_TRIM: pass                      # explicit, recorded decision to cut the song
        elif diff > 0: bad.append('song is %.2f s but project.json duration is %.2f s (%.2f s too long): set duration to the real length, or set "allow_trim": true to cut it on purpose' % (info['dur'], DUR, diff))
        else: bad.append('song is %.2f s but project.json duration is %.2f s (%.2f s too short; allow_trim does not cover a short song): set duration to the real length' % (info['dur'], DUR, -diff))
    return bad
