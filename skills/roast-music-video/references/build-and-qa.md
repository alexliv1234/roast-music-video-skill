# Build and QA

All type is drawn in Python; ffmpeg only concatenates and muxes. The song file is never modified. Flags and script names: `scripts/README.md`, `scripts/INTERFACE.md`.

## Measuring the song (stage 7)

One command per take, each with its own output folder (the script takes exactly one song):

```
python "$SKILL_SCRIPTS/analyze_song.py" audio/take1.mp3 --out analysis/take1
python "$SKILL_SCRIPTS/analyze_song.py" audio/take2.mp3 --out analysis/take2
```

It needs `requirements-analysis.txt` (librosa). Optional flags: `--bpb N` (beats per bar, 1 to 16, default 4), `--sections N` (section guesses, default 6), `--words` (word times with faster-whisper or openai-whisper, if installed), `--model NAME` (whisper size, default `base`), `--lang CODE` (for example `en`).

What it measures: length, tempo, first downbeat, bar length, bar lines and section guesses, written to `grid.json`; with `--words`, word times in `words.json`. It prints the real duration. **It does not measure** loudness, ending quality, diction or lyric mismatches: listen for those, and compare sung words with `lyrics.md` by ear.

Pick the master by ear and by the grid, copy it to `audio/song_master.<ext>`, rerun with `--words` on it if you want word times, and copy that folder's files to `analysis/`. Then set `duration` in `project.json` to the song's real length. The build refuses a song that differs from `duration` by more than 0.25 s, or has no audio stream. `allow_trim: true` permits only a song **longer** than the plan and only when the user agreed to cut it; a shorter song always fails.

No librosa, or no whisper? Write the files by hand. The build scripts do not read `analysis/`, so it is your timing sheet: `analysis/grid.json` with `duration`, `bar_length` (seconds: 60 / BPM x beats per bar), `first_downbeat` and `bars` (start time of each bar); tap the tempo by ear. `analysis/words.json` is optional: a list of `{"word": "...", "start": 0.0, "end": 0.4}`. Without it, set string times by ear from the bars. Speech-to-text mishears sung words, especially letters, numbers and short words; correct `words.json` where the lyric is known.

## Rebuild sequence

Run from the project folder (see `scripts/README.md` for `SKILL_SCRIPTS`).

```
python "$SKILL_SCRIPTS/validate_assets.py"   # READY / KEYFRAME-ONLY / MISSING / WRONG per shot; checks the song
python "$SKILL_SCRIPTS/plan.py"              # validate the sheets; clip, else keyframe, else grey; writes out/edl.json
python "$SKILL_SCRIPTS/base.py"              # text-free base video, new version number each time
python "$SKILL_SCRIPTS/burn.py" --qa         # layout and source check; exits 1 on any failure
python "$SKILL_SCRIPTS/burn.py"              # draw the text layer over the newest base
python "$SKILL_SCRIPTS/burn.py" --mux        # add the song, two-pass loudness normalisation
python "$SKILL_SCRIPTS/qa.py"                # final checks, contact sheet, report; exits 1 on failure
```

Find the final and its sheet in `out/last_build.json` (`final`) and `out/qa_report.json`, not by guessing a name: the file is `out/animatic_vN.mp4` while any shot has no real clip, otherwise `out/<name>_vN.mp4`, with `<final>_sheet.png` beside it.

- **Swap a clip:** drop `footage/final/<clip_id>_v<N+1>.mp4`, then rerun from `plan.py`.
- **Change a string:** edit `strings.csv`, then run `plan.py`, `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`. No new base, so truth fixes are free.
- **Replace the song:** analyse the new master, set `duration`, adjust shot and string times, then `plan.py`, `base.py` if shot timing changed, `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`.
- **Clip too short for its shot:** the planned `clip_in` is kept, the last frame is held, and the shortfall is printed and written to `out/base_vN_report.json` (`clip_shortfalls`). Shots marked "retime" play at the project `retime` speed (default 98 percent).
- **Stale builds:** `qa.py` fails if the final was built from an older plan or if `out/qa_layout.json` is missing or stale. Rerun the sequence from `plan.py`.

## Layout rules (`burn.py --qa`, exits 1 on failure)

- Safe area: 5% margin on every side.
- Minimum cap height about 28 px at 720p, so text survives phone screens (the default text sizes pass with the fallback fonts).
- Anything over three words stays on screen at least 1.0 s; aim for no more than about 4 words per second.
- No two strings overlap in space and time.
- Every string with a number or a quote has a `source`.
- No string is defined but never drawn.

After the first render with real clips, look at frames: text on faces is the most common failure and the layout check cannot see faces. Move tags away from the subject's eyes; check counters against heads.

## Final QA (`qa.py`)

| Check | Pass |
|---|---|
| Streams | one video (target size and fps), one audio |
| Length | frames equal duration times fps; matches the song |
| Loudness | about -14 LUFS integrated, true peak at or below -1 dBTP (web targets; change in `project.json`) |
| Black spans | none over a fraction of a second, except a deliberate fade |
| Frozen spans | none over about 0.5 s; list any |
| Banned words | none from `project.json` (employer, products, colleagues, customers) in strings |
| Claims | every number and quote has a source |
| Layout | `qa_layout.json` present and current, no overlaps, nothing outside the safe area, nothing too small or on screen too briefly |
| Plan | the final was built from the current plan |
| Sheet | one labelled frame per shot midpoint written beside the final |

A failing check can be accepted only with a logged decision, a reason, and the cost to fix (for example "frozen moments are pauses inside animated clips; fixing means six retakes").

## Contact sheets

`contact_sheet.py SOURCE` makes a labelled grid from a video, a folder of images or a clip, sampled at shot midpoints (`--out`, `--cols`, `--tile`, `--rows`, `--every SECONDS`). With `--strings` it writes one labelled PNG per string, at the string's first fully visible frame, to `<out>/string_frames/<id>_<style>_t<seconds>.png` plus `index.json`. Use the sheet at every visual gate and `--strings` for the cut review; reviewers judge sheets far faster than videos.
