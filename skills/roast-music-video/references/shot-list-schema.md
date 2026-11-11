# Shot list and strings schema

Two CSV files drive the build (plus `plates.csv`, a catalogue only). Save as UTF-8 (the scripts read UTF-8 with or without a BOM). Times are seconds from the start of the song (`audio/song_master.<ext>`), to three decimals. Exact column and style names are in `scripts/INTERFACE.md`; `plan.py` checks them.

## shots.csv

One row per shot, in edit order, covering the song end to end. `plan.py` validates and never repairs: unique ids (letters, digits, `. _ -`), the first `start` is 0, every `end` is after its `start`, each `start` equals the previous `end` (half-frame tolerance), the last `end` equals `duration` in `project.json`. Every problem is listed and nothing is written until the sheet is fixed.

Columns the scripts read: `id,start,end,type,clip_id,reuse_of,clip_in,plate,onscreen_text_ids,notes`. All others are for you and the reviewers and are ignored.

| Column | Meaning |
|---|---|
| `id` | `S001`, `S002`, ... in edit order |
| `start`, `end`, `dur` | seconds; `start` of each row equals `end` of the previous; cut on bar lines from `analysis/grid.json` |
| `section` | `intro`, `verse1`, `chorus1`, ..., `outro` |
| `type` | `gen` (a clip, else its keyframe, else grey) or `code` (a still plate with code-drawn text). Reuse is expressed through `reuse_of`, not a type |
| `setup` | the setting key from the treatment (`stage`, `bedroom`, `card`, ...) |
| `lyric` | the words sung during the shot (from `analysis/words.json`) |
| `picture` | one sentence: what we see and the one action |
| `cast` | comma-separated cast names in the shot |
| `gen_seconds` | seconds to generate (the video model's clip length, e.g. `4`); empty for code and reuse shots |
| `keyframe_prompt` | full image prompt: style block, setting, shot description, cast descriptions, framing, "no text" line |
| `motion_prompt` | full image-to-video prompt: keep-the-design line, the action per half, camera, "no new characters, no text" |
| `onscreen_text_ids` | space-separated `strings.csv` ids meant for this shot. **Metadata only**: checked against `strings.csv`, never used to draw |
| `refs` | `;`-separated reference files (character refs, style baseline) |
| `clip_id` | `G01`, `G02`, ... for generated clips; files land as `footage/final/<clip_id>_v<N>.mp4` |
| `reuse_of` | the shot id whose clip this shot reuses (the other half of the same clip). The shot **inherits that clip**; repeat `clip_id` only if you want to state it (a different one is an error). Missing references and cycles are errors |
| `clip_in` | seconds into the clip where this shot starts (`0.0` for the first half, `2.0` for the second half of a 4 s clip) |
| `plate` | for `code` shots, the plate id (`K_CURTAIN`, `K_PHONE`); the file is `frames/<plate>.png`, so `K_CURTAIN` is `frames/K_CURTAIN.png` |
| `subject_reaction` | `Y` if the subject visibly reacts in this shot; used to check the gap between reactions |
| `notes` | retime instructions ("2 bars = 4.07 s: retime the 4 s clip to 98%"), unused halves, warnings |

Rules:
- A generated shot is never longer than the clip length plus a small retime (about 2%); longer moments become two shots or a code shot.
- One clip serves at most two shots, each half used once, placed apart in the edit, so reuse does not read as a loop.
- Every `gen` shot names its cast and its refs; every cast member in `cast` has a description in `keyframe_prompt`.

Example row (fictional, shortened prompts):

```
id,start,end,dur,section,type,setup,lyric,picture,cast,gen_seconds,keyframe_prompt,motion_prompt,onscreen_text_ids,refs,clip_id,reuse_of,clip_in,plate,subject_reaction,notes
S007,14.20,16.27,2.07,verse1,gen,office,She sent us off for slides,"The Drafts line up on the desk, each smaller than the last; Sam waves them down with a grin.","Sam, The Drafts",4,"Bold 2D cartoon ... No text, letters, numbers or logos anywhere; every sign, card and screen is blank.","Animate this 2D cartoon illustration ... First two seconds: ... Last two seconds: ... Camera locked. No new characters, no text.",T012 T013,refs/sam.png; refs/drafts.png; refs/baseline.txt,G05,,0.0,,Y,
```

## plates.csv

A catalogue of the still plates for `code` shots: `id,prompt,file,notes`. The scripts do not read it; they load `frames/<plate>.png` by the `plate` id. Plates are generated blank (no numerals on clocks, no words on screens).

## strings.csv

One row per piece of on-screen text. Every word in the film is a row here, because text is drawn in code over a text-free base.

| Column | Meaning |
|---|---|
| `id` | `T001`, ... stable ids; never reuse a deleted id |
| `start`, `end` | seconds on screen |
| `text` | the exact text; quotes copied character for character from the dossier, typos included |
| `style` | only these are implemented, and `plan.py` rejects anything else: `caption` (sung words), `hook` (the big shouted word), `namecard` (`NAME: role` or `NAME, role`), `bubble` (chat message), `card` (quote or fact card), `tag` (small context label in a top corner), `end` (end card) |
| `where` | bubble: `left` or `right`; card: `title` (title card), `end` (larger, upper), `end2` (larger, lower), any other value or empty a normal centred card; tag: `left` or `right`; end: `low` places it lower, any other value is default. Empty is fine for the rest |
| `shot_id` | the shot it first appears over. **Metadata only** (checked, not used): a string is drawn by its own `start` and `end`. Strings that cross a shot cut are listed in `review_flags` in `out/edl.json`; review them |
| `source` | where the words or number come from: `lyrics.md, sung line`, `dossier 4, 2026-02-11`, `rulings.md row 3`. Required for every number and every quote |

Conventions:
- There are no date chips, counters or receipts. Put the date in the quote card's own text (for example a second line "11 Feb", started with a newline inside the quoted CSV cell) or in a `tag`.
- Sung captions follow what is sung (from `words.json`), not what was written.
- Quotes keep the subject's own spelling. Never "improve" a quote, and never apply a stylistic rule (like writing "u" for "you") to a real quote that did not use it.

Example rows (fictional):

```
id,start,end,text,style,where,shot_id,source
T012,14.30,16.10,She sent us off for slides,caption,,S007,"lyrics.md, sung line"
T013,14.60,17.40,"ok make it punchier. no, punchier",bubble,left,S007,"dossier 3, 2026-02-11"
T014,14.60,17.40,11 Feb,tag,right,S007,"dossier 3, 2026-02-11"
T015,40.10,44.00,"x137 ""punchier"" (one computer only)",card,,S019,"dossier 2, top short messages"
```
