#!/usr/bin/env bash
# Builds the tiny example end to end: assets -> validate -> plan -> base -> burn --qa -> burn -> mux -> qa -> contact sheet -> string frames.
# Then three negative checks (a broken timeline and an unknown style must be refused; the synthetic session log must be redacted).
# Run from anywhere:  bash run.sh      Needs python 3.10+ (numpy, Pillow, opencv-python) and ffmpeg/ffprobe on PATH.
set -euo pipefail
cd "$(dirname "$0")"
export ROAST_PROJECT_DIR="$PWD"            # the example is its own project, whatever ROAST_PROJECT_DIR was before
S=..
rm -rf out audio frames footage            # start clean so every run is the same
python make_assets.py
python $S/validate_assets.py
python $S/plan.py
python $S/base.py
python $S/burn.py --qa
python $S/burn.py
python $S/burn.py --mux
python $S/qa.py
python $S/contact_sheet.py "$(python -c "import json;print(json.load(open('out/last_build.json'))['final'])")" --out out/contact.png --cols 4 --tile 320
python $S/contact_sheet.py "$(python -c "import json;print(json.load(open('out/last_build.json'))['final'])")" --strings

# negative checks: each of these MUST fail
BAD="$(mktemp -d)"
cp project.json strings.csv "$BAD/"
sed 's/^S003,5.0/S003,5.4/' shots.csv > "$BAD/shots.csv"            # a 0.4 s gap after S002
if (cd "$BAD" && ROAST_PROJECT_DIR="$BAD" python "$OLDPWD/$S/plan.py" > "$BAD/plan.log" 2>&1); then echo "FAIL: gap in the timeline was accepted"; exit 1; fi
grep -q "contiguous" "$BAD/plan.log" || { echo "FAIL: timeline error not reported"; exit 1; }
cp shots.csv "$BAD/shots.csv"
sed 's/,tag,left,/,receipt,left,/' strings.csv > "$BAD/strings.csv"  # a style that does not exist
if (cd "$BAD" && ROAST_PROJECT_DIR="$BAD" python "$OLDPWD/$S/plan.py" > "$BAD/plan.log" 2>&1); then echo "FAIL: unknown style was accepted"; exit 1; fi
grep -q "unknown style" "$BAD/plan.log" || { echo "FAIL: style error not reported"; exit 1; }
rm -rf "$BAD"
echo "negative checks ok (broken timeline and unknown style are refused)"

# synthetic session log (no real data): the key-bearing message must be dropped whole
python $S/collect_sessions.py --no-default --root scratch --out out/research
if grep -q "sk-abcdefghijklmnop" out/research/*; then echo "FAIL: synthetic key leaked into the digest"; exit 1; fi
echo "done: see out/ (the final mp4 is out/animatic_v1.mp4 because one shot has no clip yet)"
