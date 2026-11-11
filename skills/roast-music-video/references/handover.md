# Hand-over report and decisions log

The skill ends with a report. It never uploads, posts, or shares the video, because only the subject can decide that the jokes about them go public.

## Report template (`out/HANDOVER.md`)

```markdown
# <Title>: hand-over, <date>

## Needs your yes before publishing
1. <line or card> at <time>: <why it is flagged> (review row, ruling).
2. Sung third-party name "<word>": keep, or re-record that line.
3. Upload title, description and tags: no employer, products, customers,
   colleagues or tool brand names. Suggested title: "<title>".
4. <anything about another person, a public claim, or a photo>.

## The film
- File: the `final` path in out/last_build.json (<length>, <resolution>, <fps>)
- Contact sheet: the same path ending `_sheet.png`
- QA: pass / accepted failures (see decisions <#>)

## Spend
| Role | Provider | Mode | Jobs | Spend | Cap |
|---|---|---|---|---|---|
| song | <name> | manual | 2 takes | on your account | |
| keyframes | <name> | cli | <n> | <cost> | |
| clips | <name> | mcp | <n> incl. <r> retakes | <cost> | <cap> |
| Total | | | | <cost> | <cap> |

## What changed from the plan
Short list: rulings applied, cut-review rows applied or skipped.

## Decisions taken without you
See DECISIONS.md (<n> rows). The ones you may want to reverse: <#>, <#>.

## How to change things
- A word on screen: edit strings.csv, rerun from plan.py (free).
- A clip: retake <clip_id> (one clip at the provider's price).
- The song take: swap audio/song_master.<ext>, run analyze_song.py, set `duration` in project.json, adjust shot and string times, then plan.py, base.py (if shot timing changed), burn.py --qa, burn.py, burn.py --mux, qa.py.

## Not done
Anything left open, and why.
```

Put the "needs your yes" list first, because it is the part the subject must act on and the part most likely to be skipped.

## Decisions log template (`DECISIONS.md`)

```markdown
# Decisions taken while <first name> was away (<date>)

Standing order: <what the user said, e.g. "finish it; decide as I would;
cap X; publish nothing">.

| # | Time | Decision | Why | How to undo |
|---|---|---|---|---|
| 1 | 21:40 | Look: cut-paper TV game show | suits the premise; one roaster per round | edit treatment.md; keyframes are cheap to redo |
| 2 | 23:05 | Song: take 2 | steadier beat grid, ring-out ending | swap in take 1, rerun the song-replacement steps in build-and-qa.md |
| 3 | 01:30 | Motion test passed; released the batch at 720p | likeness held, no new characters or text | none; spend is final |
| 4 | 04:50 | Accepted QA's frozen-frame warning | pauses inside clips, captions move over them | retake the listed clips at the clip price |
```

Rules for the log:
- One row per decision the user did not make themselves.
- "Why" cites a measurement, a review row or a rule, not a feeling.
- "How to undo" names the action and its cost. "None needed" is fine when true.
- Never log as decided: publishing, raising the cap, using handle-with-care material, or a "needs subject's yes" line. Those wait.
