# Script interface (exact names)

Python 3.10+. ffmpeg and ffprobe on PATH. Run every script with the project folder as working directory (or set `ROAST_PROJECT_DIR`), calling it by path: `python "$SKILL_SCRIPTS/<script>.py"` (PowerShell: `"$env:SKILL_SCRIPTS\<script>.py"`).

## Styles (strings.csv `style`)
`caption`, `hook`, `namecard`, `bubble`, `card`, `tag`, `end`. Anything else is rejected by `plan.py`. (`caption` with `where=tag` in old sheets is read as `tag`.)
`where`: bubble `left`|`right`; card `title` | `end` | `end2` | other (default centred card); tag `left`|`right`; end `low`|other. Not implemented: receipt, counter, date, automatic date chips.

## CSV columns
- shots.csv: `id,start,end,type,clip_id,reuse_of,clip_in,plate,onscreen_text_ids,notes` (+ `section,setup,lyric` and any extras, ignored). `type` = `gen`|`code`. `reuse_of` inherits the referenced shot's clip. `onscreen_text_ids` = metadata (validated, not drawn from).
- strings.csv: `id,start,end,text,style,where,shot_id,source`. `shot_id` = metadata (validated). Strings with a digit or quote need `source`.
- Timeline checks in plan.py: unique ids matching `[A-Za-z0-9][A-Za-z0-9_.-]*`, first start 0, contiguous (half-frame tolerance), end > start, last end = `duration`.

## project.json keys
`name, subject, consent{given,evidence}, audience, off_limits[], budget{total,currency,reserve,retake_cap}, duration, allow_trim, fps, size[w,h], song, dirs{footage,frames,out,audio}, shots_csv, strings_csv, palette{ink,paper,accent,accent2,panel}, fonts{display,body,mono}, retime, safe_margin, min_cap_px, min_hold, loudness{target_lufs,true_peak,lra}, text{caption_size,caption_bottom,caption_max_width,tag_size,namecard_bottom,namecard_name_size,namecard_role_size,hook_size,hook_center,hook_angle,bubble_size,bubble_max_width,title_size,card_size,end_size}, banned_terms[], providers{song,transcription,images,video each {name,mode,notes}}`.
Provider `mode`: `mcp | cli | manual | none`. Role is `transcription` (`stt` is accepted with a warning). Keys starting with `_` are ignored.
Defaults that matter: namecard_role_size 40, tag_size 40, bubble_size 40, consent.given false, budget all zero, allow_trim false. Duration rule: real song length within 0.25 s of `duration`; `allow_trim: true` permits only a longer song, and an audio stream is required.

## Scripts and flags
- `plan.py` (no flags). Writes `out/edl.json` (adds `warnings`, `review_flags`, `fingerprint` (text layer), `visual_fingerprint` (picture: shot frames, resolved clip or still and file identity, clip_in, speed, push-in, size, fps), per-string `visible_frame`) and `out/placeholders.json`. Exit 1 listing every sheet problem.
- `base.py [--version N]`. Writes `out/base_vN_nofx.mp4`, `out/base_vN_report.json` (`clip_shortfalls`: shot, requested_clip_in_s, held_last_frames, shortfall_s; `fingerprint`; `visual_fingerprint`). Keeps the requested `clip_in`, holds the last frame.
- `burn.py` (render text layer) | `--qa` (layout + source check, exit 1 on failure, writes `out/qa_layout.json`) | `--mux` | `--base N`. Rendering (and `--base N`) exits 1 if the chosen base's `visual_fingerprint` differs from the current plan's (run `plan.py` and `base.py` again); text-only edits pass.
- `qa.py [--final path]` (relative path: under the project folder). Exit 1 on failure (also when the final's frame rate is not the project fps); writes `out/qa_report.json` and `<final>_sheet.png`. Fails on missing or stale `qa_layout.json`, `too_short`, stale build, song mismatch.
- `validate_assets.py [--strict]`. Exit 1 on a missing or bad song or a bad shot sheet; with `--strict` also on any MISSING or WRONG row. A still not in the project aspect is WRONG.
- `contact_sheet.py SOURCE [--out PATH] [--cols N] [--tile PX] [--rows N] [--every SECONDS] [--strings]`. `--strings` exports one labelled PNG per string (first fully visible frame) to `<out>/string_frames/<id>_<style>_t<seconds>.png` plus `index.json`; `--out` is then a folder.
- `analyze_song.py SONG [--out DIR] [--bpb N (1-16)] [--sections N] [--words] [--model NAME] [--lang CODE]`. Writes `grid.json` (and `words.json`) under `--out` (default `analysis`). The song path is resolved under the project folder. Transcription runs locally; first use may download model weights. Audio is not uploaded.
- `collect_sessions.py [--root PATH]... [--no-default] [--out DIR] [--since YYYY-MM-DD] [--max-chars N] [--samples N] [--top N] [--seed N]`. Writes `research/digest.json`, `digest.md`, `messages.jsonl` (project, source_file, line, timestamp, chars, text). Redaction is best-effort: whole message dropped on any credential; inspect locally before sharing.
- Tests: `python "$SKILL_SCRIPTS/tests/test_redaction.py"`, `python "$SKILL_SCRIPTS/tests/test_defaults.py"`. Example: `bash "$SKILL_SCRIPTS/example/run.sh"` (it sets `ROAST_PROJECT_DIR` to the example itself).
- Install: `python -m pip install -r "$SKILL_SCRIPTS/requirements.txt"`; analysis extras in `requirements-analysis.txt`.

## Files written
`out/edl.json, placeholders.json, base_vN_nofx.mp4, base_vN_report.json, qa_layout.json, _textlayer_vN_silent.mp4, last_build.json (base_version, silent, name, placeholders, fingerprint, final), <animatic|name>_vN.mp4, <...>_sheet.png, qa_report.json, contact.png, string_frames/`. `analysis/grid.json, words.json`. `research/digest.json, digest.md, messages.jsonl`. Manifests are written only after a successful encode.
