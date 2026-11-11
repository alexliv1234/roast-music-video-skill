# roast-music-video scripts

A small, provider-free pipeline: a song plus `shots.csv` and `strings.csv` become a text-free base video, a text layer drawn in Python, and a final mp4 muxed with the song at the loudness target, then checked. Nothing here calls an AI provider; `providers` in `project.json` is read only to print hints. Transcription (`analyze_song.py --words`) runs locally; first use may download model weights. Audio is not uploaded. The exact names of settings, styles and flags are listed in `INTERFACE.md`.

**Requirements:** Python **3.10+**, the packages in `requirements.txt` (numpy, Pillow, opencv-python), and **both** `ffmpeg` and `ffprobe` on PATH. The beat-grid helper `analyze_song.py` needs `requirements-analysis.txt` (librosa, soundfile); without it, write `analysis/grid.json` by hand (see below). All type is drawn with Pillow; ffmpeg only encodes and muxes.

## Where things live: the two folders
- **The installed scripts folder** (this folder). Point a variable at it once per terminal session. Adjust the path to where the skill is installed.
- **Your project folder**: a separate, private working folder that holds `project.json`, the CSVs, audio, frames, footage and `out/`. Always make it the working directory when you run a script.

POSIX shell (macOS, Linux, Git Bash):
```
export SKILL_SCRIPTS="$HOME/.claude/skills/roast-music-video/scripts"
cd ~/my-roast                                   # your project folder
python -m pip install -r "$SKILL_SCRIPTS/requirements.txt"
python "$SKILL_SCRIPTS/plan.py"
```
PowerShell:
```
$env:SKILL_SCRIPTS = "$HOME\.claude\skills\roast-music-video\scripts"
cd ~\my-roast                                   # your project folder
python -m pip install -r "$env:SKILL_SCRIPTS\requirements.txt"
python "$env:SKILL_SCRIPTS\plan.py"
```
(Command Prompt: `set SKILL_SCRIPTS=...` then `python "%SKILL_SCRIPTS%\plan.py"`.) Every command below is written as `python "$SKILL_SCRIPTS/<script>.py"`; in PowerShell read it as `python "$env:SKILL_SCRIPTS\<script>.py"`.

### One rule for the project folder
Every script finds the project the same way: the folder named by the **`ROAST_PROJECT_DIR`** environment variable if it is set, otherwise the **current working directory** (`roots.py`). `project.json`, the CSVs, `audio/`, `frames/`, `footage/`, `analysis/`, `research/` and `out/` are all looked up there; relative `--out` paths and relative song paths are resolved there too. Set `ROAST_PROJECT_DIR` (`export ROAST_PROJECT_DIR=~/my-roast`, or `$env:ROAST_PROJECT_DIR = "$HOME\my-roast"`) if you want to run commands from elsewhere.

## Setup
1. Make a private project folder and put a `.gitignore` in it containing `*` and `!.gitignore`, so nothing in it can be committed by accident. Copy `project.example.json` there as `project.json` and edit it.
2. Fonts: set `fonts.display`, `fonts.body` and `fonts.mono` to `.ttf` files you are licensed to use. If a path is empty or missing, the scripts search the common system font folders on Windows, macOS and Linux (Arial, Helvetica, DejaVu, Liberation, Noto, FreeSans), print which file they chose, and warn. No fonts ship with these scripts.
3. Folders: `audio/song_master.<ext>`, `frames/` (keyframes and plates), `footage/final/` (clips), `out/` (everything built; created for you).
4. Set `duration` in `project.json` to the song's **real** length. `burn.py --mux`, `validate_assets.py` and `qa.py` stop if the song's duration differs from `duration` by more than 0.25 s, or if the file has no audio stream. Set `"allow_trim": true` only if you decided to cut a longer song on purpose (a shorter song is always refused).

## project.json
Every key is optional; missing keys take the defaults in `common.py`. Numbers are validated at start-up (positive finite duration, whole fps 1 to 240, even width and height, retime 0.25 to 4, safe margin below 0.25, text sizes above 0, widths and bottoms above 0 and at most 1) and an invalid value stops the script with a message.
- Metadata for the agent gates and reviewers (no script uses them): `subject`, `consent` `{given: false, evidence: ""}`, `audience`, `off_limits` `[]`, `budget` `{total: 0, currency: "credits", reserve: 0, retake_cap: 0}`. Leave `consent.given` false until the subject has agreed.
- Build settings: `name`, `duration`, `allow_trim`, `fps`, `size`, `song`, `dirs`, `shots_csv`, `strings_csv`, `palette`, `fonts`, `retime`, `safe_margin`, `min_cap_px`, `min_hold`, `loudness`, `text`, `banned_terms`.
- `providers`: roles `song`, `transcription`, `images`, `video`; each has `name`, `mode` (`mcp`, `cli`, `manual` or `none`) and `notes`. `transcription` was called `stt` in older notes; `stt` still loads with a warning.
- `text.*` sizes are reference values at 720p high, scaled by height/720. The defaults (caption 46, tag 40, namecard name 46 and role 40, bubble 40) pass the 28 px minimum cap height with the Arial and DejaVu fallback fonts.

## Inputs
`shots.csv` columns: `id,start,end,type,clip_id,reuse_of,clip_in,plate,onscreen_text_ids,notes` (extras such as `section,setup,lyric,subject_reaction,keyframe_prompt,motion_prompt` are allowed and carried along or ignored).
- `plan.py` **validates, it does not repair**: ids unique (letters, digits, `. _ -`), the first shot starts at 0, each shot ends where the next starts (within half a frame), every end is after its start, the last end equals `duration`. Problems are listed together and nothing is written.
- `type` is `gen` (picture from a clip or keyframe) or `code` (a plate still; its text is drawn by `burn.py`).
- `reuse_of` names another `gen` shot: this shot **inherits that shot's clip** (repeat `clip_id` only if you want to state it; a different one is an error) and plays from `clip_in` seconds. Missing references, cycles and conflicting clip ids are errors.
- A note containing `retime` plays the clip at the project `retime` speed (default 98 percent) so a 4.00 s clip fills a 4.07 s shot.
- `onscreen_text_ids` is **metadata for reviewers**: checked against `strings.csv`, but it does not control drawing.

`strings.csv` columns: `id,start,end,text,style,where,shot_id,source`. A string is drawn only by its own `start` and `end`; `shot_id` is metadata (checked, not used). Strings that cross a shot cut are listed under `review_flags` in `out/edl.json`.
- Styles (only these; an unknown style is rejected): `caption`, `hook`, `namecard` (`NAME: role` or `NAME, role`), `bubble` (`where` `left` or `right`), `card` (`where` `title` = title card, `end` = larger card in the upper half, `end2` = larger card in the lower half, anything else or empty = normal centred card; a newline inside the cell starts a new line), `tag` (small label in a top corner; `where` `left` or `right`), `end` (end card; `where` `low` places it lower).
- Every string with a digit or a quotation mark needs a `source`.

## Zero-budget path (stills only, or manual hand-off)
You do not need any video provider. A `gen` shot resolves in this order: clip `footage/final/<clip_id>_vN.mp4` (highest N), else keyframe `frames/k_<clip_id>.png` with a slow code-drawn push-in, else a labelled grey placeholder. So a full animatic builds from stills alone; the final is then named `animatic_vN.mp4`. Make files anywhere, drop them into the folders above with those names, and run `validate_assets.py` for a table of READY / KEYFRAME-ONLY / MISSING / WRONG. The example exercises this: shot S003 has no clip. Set the `video` provider to `mode: "none"`. Word timings are optional too: set string times by ear from the beat grid.

## Build order
```
python "$SKILL_SCRIPTS/validate_assets.py"   # what is ready, missing or wrong (exits 1 on a missing or bad song, or a bad shot sheet; stills must be the project aspect)
python "$SKILL_SCRIPTS/plan.py"              # validates the sheets, writes out/edl.json and out/placeholders.json
python "$SKILL_SCRIPTS/base.py"              # text-free out/base_vN_nofx.mp4, exactly duration x fps frames; always a new N
python "$SKILL_SCRIPTS/burn.py" --qa         # layout and source check -> out/qa_layout.json; EXITS 1 on any failure
python "$SKILL_SCRIPTS/burn.py"              # text layer over the newest base -> out/_textlayer_vN_silent.mp4
python "$SKILL_SCRIPTS/burn.py" --mux        # song + two-pass loudnorm (default -14 LUFS, TP -1.5) -> out/animatic_vN.mp4 or out/<name>_vN.mp4
python "$SKILL_SCRIPTS/qa.py"                # exits 1 on any failure
python "$SKILL_SCRIPTS/contact_sheet.py" out/animatic_v1.mp4            # labelled sheet at shot midpoints (also works on a folder of images)
python "$SKILL_SCRIPTS/contact_sheet.py" out/animatic_v1.mp4 --strings   # one labelled frame per string, at its first fully visible frame
```
`qa.py` fails if `out/qa_layout.json` is missing or stale (made from other strings, shots or settings), if the layout has overlaps, text outside the safe margin, text too small, text on screen too briefly (`too_short`) or never drawn, if the final was built from an older plan, or if the song check fails. Build records (`base_vN_report.json`, `last_build.json`) are written only after the encode succeeded; if ffmpeg fails the partial file is removed and the script stops with ffmpeg's message. `burn.py --base N` renders over an older base. `qa.py --final path` checks any file (it also fails if the frame rate is not the project fps). `base_vN_report.json` and `out/edl.json` carry a `visual_fingerprint` (shot timing, resolved clip or still and its file identity, `clip_in`, speed, push-in, size, fps); `burn.py` refuses a base whose picture no longer matches the current plan and tells you to run `plan.py` and `base.py` again. Text-only edits do not change it. Relative paths given to `qa.py --final`, `contact_sheet.py` and `analyze_song.py` are resolved under the project folder; absolute paths are kept.

## Swap one clip
Put `footage/final/<clip_id>_vN.mp4` in place (the highest N wins). Then `plan.py`, `base.py`, `burn.py`, `burn.py --mux`, `qa.py`. A clip too short for its shot **keeps the planned `clip_in`**: its last frame is held for the rest of the shot and the shortfall is printed and written to `out/base_vN_report.json` as `clip_shortfalls`. A clip that is not the project aspect is centre-cropped.

## Change one string
Edit its row in `strings.csv`. Then `plan.py`, `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`. The base video does not need rebuilding for a text change. `plan.py` extends a hold shorter than `min_hold` (strings over 3 words) where the next string in the same slot allows, and reports it.

## Replace the song
Copy the new master to `audio/`, run `analyze_song.py` on it, set `duration` to the real length, adjust shot and string times, then `plan.py`, `base.py` (needed when shot timing changed), `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`.

## Research and song helpers
- `analyze_song.py <song>` writes `analysis/grid.json` (length, tempo, first downbeat, bar length, bar lines, section guesses; needs librosa; 4/4 assumed, check by ear) and prints the song's real duration for `project.json`. `--words` writes `analysis/words.json` with faster-whisper or openai-whisper if installed. For two takes run it twice with separate folders: `--out analysis/take1`, `--out analysis/take2`. It measures length, tempo, downbeat and sections only; loudness, endings and diction are for your ears and `qa.py`.
- `collect_sessions.py` reads local AI-assistant session logs (`~/.claude/projects` by default, plus `--root` folders or `.jsonl` files), counts only what the human typed, and writes `research/digest.json`, `research/digest.md` and `research/messages.jsonl` (one record per message with project, source file, line and full timestamp). It makes no network calls and prints totals only.
  - **Redaction is best-effort.** A message containing a credential anywhere (quoted or unquoted password, secret, token, api key or authorization fields, `scheme://user:pass@host`, HTTP Basic or Bearer values, PEM or SSH key blocks, known provider token shapes) is dropped whole and counted; emails are masked. Some secrets will still get through. **Inspect `research/` locally before sharing, pasting or committing anything from it**, and get the subject's consent first.
  - Skipped and counted: tool results, injected reminders, sub-agent prompts, "This session is being continued" summaries, pasted blocks, duplicates. Only `*.jsonl` is read; `.json` exports (Gemini, desktop apps, web) are counted as unsupported, not read.
  - Example: `python "$SKILL_SCRIPTS/collect_sessions.py" --no-default --root D:/exports/claude-logs --since 2025-01-01`
- `tests/test_redaction.py` (synthetic credentials and false-positive words) and `tests/test_defaults.py` (default text sizes pass the cap-height minimum; bad numbers are rejected): `python "$SKILL_SCRIPTS/tests/test_redaction.py"`.

## Try it
`bash "$SKILL_SCRIPTS/example/run.sh"` builds a 10 second synthetic project (a fictional "Sam", solid-colour stills, a sine-tone song) through every stage, exports the per-string frames, checks that a broken timeline and an unknown style are refused, runs the collector on a synthetic log, and finishes with `QA PASS`.

## Files
`common.py` settings, validation, fonts, text and process helpers. `roots.py` project-root resolution. `plan.py`, `base.py`, `burn.py`, `qa.py`, `validate_assets.py`, `contact_sheet.py`, `analyze_song.py`, `collect_sessions.py`, `project.example.json`, `requirements.txt`, `requirements-analysis.txt`, `INTERFACE.md`, `tests/`, `example/`.
