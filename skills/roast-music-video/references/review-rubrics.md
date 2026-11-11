# Adversarial reviews and rulings

Three review gates. **Lyrics gate** (SKILL.md stage 5, before any paid call): the truth and privacy reviewers on lyrics, cited dossier excerpts and the song prompt. **Plan gate** (stage 10, before paid images or clips): all three reviewers. **Cut gate** (stage 14, before hand-over): all three, with frames. Each reviewer is independent. Give each reviewer the files and the dossier, not your reasoning, so they do not inherit your blind spots. If a second-vendor model is available (a Codex or Gemini CLI, for example), run it as an extra pass on all three briefs and mark its rows. That is a disclosure: get the user's approval before sending it anything, and exclude handle-with-care details from what it receives.

## Row format (all reviewers)

```
| # | Sev | Where | Problem | Evidence | Exact fix |
```

- **Sev:** `BLOCK` (must change before spend or publish), `FIX` (should change), `NICE` (optional).
- **Where:** file and line, string id, shot id, or time range.
- **Evidence:** a dossier line, a source file and line, or a frame path. No evidence, no row.
- **Exact fix:** the replacement text or the specific change, ready to apply.

## Reviewer prompts

### Truth reviewer

```
You are the truth reviewer for a comedy roast music video about a real person
who has consented to it. Files: lyrics.md, treatment.md, shots.csv,
strings.csv, research/*/DOSSIER.md.
Check every on-screen quote, number, date and claim against the dossier.
Flag: misquotes (any changed word, fixed typo or dropped clause), two quotes
merged into one message, numbers worded stronger than their source (one repo
shown as all repos, a raw count shown as "they wrote"), invented details that
have no source, events from different days shown as one night, claims in the
end card that are not literally true, and anything marked (inferred) presented
as fact. Sung lines may round; on-screen text may not.
Return rows: # | Sev | Where | Problem | Evidence | Exact fix.
Then list what you checked and found clean.
```

### Privacy and employer reviewer

```
You are the privacy and employer reviewer for a roast music video about a real
person. Files: as above, plus project.json (consent, audience, off-limits).
Flag anything that names or identifies the employer, its products, customers
or colleagues (including by combination of clues), any other real person,
anything from the dossier's handle-with-care section, any home, money, health,
security or legal detail, any real logo, and any line a stranger could clip
out to embarrass the subject professionally. Consider the upload title,
description and tags too. Mark lines only the subject can approve as
"needs subject's yes".
Return rows: # | Sev | Where | Problem | Evidence | Exact fix.
Add a "do not add" list of tempting material that must stay out.
```

### Comedy reviewer

```
You are the comedy reviewer for a roast music video. The subject must stay
cool and in on the joke. Files: lyrics.md, treatment.md, shots.csv,
strings.csv (and frames at the cut review).
Flag: static stretches (repeated choruses with the same staging), jokes that
need context a stranger lacks, text held too short to read (over 3 words in
under 1 s, or more than about 4 words per second), too many text layers at
once, the subject looking sweaty, sad or mocked for their body, clones, and an
ending that dies on small print. Name the weakest five jokes. Suggest extra
gags only if they are true and sourced.
Return rows: # | Sev | Where | Problem | Evidence | Exact fix.
```

### Cut review additions

At the cut, give reviewers frames: one per shot midpoint and one at the first fully visible frame of every string. Export both with `contact_sheet.py <final>` (shot sheet) and `contact_sheet.py <final> --strings` (`<out>/string_frames/<id>_<style>_t<seconds>.png` plus `index.json`); pass the `final` value from `out/last_build.json` verbatim as `<final>`, it is already a full path. Add to every brief: "Check text against the frames: text on the subject's face or eyes, text over another text, captions ghosting across cuts, counters covering heads."

## Rulings

Merge the reviewers' rows into `review/plan-review.md` (or `cut-review.md`), then write `review/rulings.md`:

```markdown
# Rulings on the plan review (<time>, <date>)

Rulings bind the shot list, the strings and the edit, and override
treatment.md where they differ. Rows marked SUBJECT go at the top of the
hand-over report. A BLOCK is closed only when its fix is applied or the material is removed; a ruling alone does not close it. Material awaiting the subject's approval stays out of every prompt and string until approved.

| Review row | Ruling |
|---|---|
| 3 one repo shown as all | Card reads "ONE OF THEIR PUBLIC REPOS: ..." with the date. |
| 5 quote shortened | Show the full quote on screen. SUBJECT: confirm before publishing. |
| FIX: static choruses | The spine prop grows in each chorus. |
| All other FIX rows | Apply as written unless they conflict with a ruling above. |

## Never add
<items from handle-with-care and the reviewers' do-not-add lists>
```

Before writing a ruling's replacement text, re-check its wording against the source; a ruling can carry the same misquote as the plan it fixes.

## Applying the cut review

One fix round. Back up `strings.csv` (for example `strings_v1.csv`), apply, then record each row:

```
| # | Status | What / why |
| 1 | applied | ... |
| 13 | skipped | conflicts with ruling 4 (binding); left for the main session |
| 5 | no change | gated on the subject's yes |
```

After editing `strings.csv`, run `plan.py` first (`burn.py --qa` and the render read the cached `out/edl.json`, so without it they check and draw the old text). Then run `burn.py --qa` (exits 1 on any layout or source failure; it must pass), `burn.py`, `burn.py --mux` and `qa.py`, and check the corrected frames (`contact_sheet.py <final> --strings`).
