"""make_assets.py : builds the synthetic inputs for the example (no network, no providers).
  audio/song_master.wav   10 s sine tone with a slow tremolo (ffmpeg)
  frames/K_TITLE.png      plate for the code shot (solid colour with simple shapes, Pillow)
  frames/k_C01..C03.png   keyframes (solid colour with simple shapes)
  footage/final/C01_v1.mp4, C03_v1.mp4   3 s clips (ffmpeg solid colour with moving noise). C02 has NO clip on purpose:
                          that shot falls back to its keyframe with a slow push-in, the zero-budget path.
Run from the example folder."""
import os, subprocess
from PIL import Image, ImageDraw

for d in ('audio', 'frames', 'footage/final'): os.makedirs(d, exist_ok=True)

def ff(*args): subprocess.check_call(['ffmpeg', '-y', '-v', 'error'] + list(args))

ff('-f', 'lavfi', '-i', 'sine=frequency=220:duration=10:sample_rate=48000', '-af', 'tremolo=f=2:d=0.5,volume=0.6', 'audio/song_master.wav')

def still(name, bg, fg):
    im = Image.new('RGB', (1920, 1080), bg); d = ImageDraw.Draw(im)
    for x in range(-1080, 1920, 160): d.polygon([(x, 0), (x + 60, 0), (x + 60 + 1080, 1080), (x + 1080, 1080)], fill=tuple(int(c * 0.9) for c in bg))
    d.ellipse((660, 240, 1260, 840), fill=fg); d.rectangle((120, 780, 560, 960), fill=fg)
    im.save('frames/%s.png' % name)

still('K_TITLE', (40, 60, 110), (240, 200, 90))
still('k_C01', (150, 60, 70), (250, 225, 200))
still('k_C02', (40, 120, 110), (255, 240, 180))
still('k_C03', (110, 70, 140), (240, 240, 140))

for cid, col in (('C01', '0x963c46'), ('C03', '0x6e468c')):
    ff('-f', 'lavfi', '-i', 'color=c=%s:s=640x360:r=24:d=3,noise=alls=25:allf=t' % col, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', 'footage/final/%s_v1.mp4' % cid)
print('example assets written')
