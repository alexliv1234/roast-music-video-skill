---
name: roast-music-video
description: Research a person's own AI chat history (Claude Code, Codex, Gemini, desktop apps) on one or more computers and turn it into a sourced, consenting roast music video about them, with a generated or self-made song, a cartoon cast, code-drawn text and adversarial truth and privacy reviews. Use this whenever someone asks for a roast video, a funny music video about themselves or a willing friend, "make a song about how I use AI", a birthday or farewell roast built from real chat logs, or wants to turn their prompt habits into a comedy film, even if they do not say "music video". Works with no paid provider at all (stills animatic).
---

# Roast music video from your own AI history

An AI reads the subject's own AI sessions, finds what is true and funny, writes a song with a source for every line, and builds a cartoon music video where the subject is cool and in on the joke. The skill makes the film and a hand-over report. It never publishes anything; the subject decides that.

The method came from one finished cartoon roast with a generated song, generated clips, two adversarial reviews and an overnight build. Every rule below exists because something went wrong without it (`references/lessons.md`).

## How to work

- **Orchestrate, do not grind.** You plan, decide and review. Delegate mining, drafting, prompt writing, code runs and frame checks to cheaper sub-agents with narrow briefs; your context is the scarce resource.
- **A second vendor as reviewer is optional** (a Codex or Gemini CLI, say). Two vendors miss different things. Sending anything to one is a disclosure: see Stage 0.
- **Files are the state.** Everything lives in one project folder so a later session can resume from the files alone.
- **Gates are real.** Do not start a stage until the gate before it has passed. **Every route needs the Stage 5 review cleared and the person's consent. Paid song or transcription calls also need the user's yes to the spend and the cap at Stage 5; paid images or clips additionally need Stage 10 passed. With a zero cap there is nothing to approve: proceed without a spend approval.**
- **Run scripts the documented way.** `SKILL_SCRIPTS` is the installed `scripts/` folder. Make the project folder the working directory (or set `ROAST_PROJECT_DIR`) and call `python "$SKILL_SCRIPTS/<script>.py"` (PowerShell: `"$env:SKILL_SCRIPTS\<script>.py"`). Setup, flags and exact names: `scripts/README.md` and `scripts/INTERFACE.md`. Python 3.10+, `ffmpeg` and `ffprobe` on PATH, `requirements.txt` for the core, `requirements-analysis.txt` for beat analysis.

## Project folder

```
<project>/
  .gitignore            "*" and "!.gitignore" (Stage 0): nothing is committable by accident
  project.json          subject, consent, audience, off_limits, budget, providers, formats
  DECISIONS.md          every decision you took alone, with why and how to undo
  research/             dossier(s), digests (private)
  concepts.md lyrics.md treatment.md
  shots.csv strings.csv plates.csv
  review/               plan-review.md, rulings.md, cut-review.md
  handoff/              prompt packs for manual providers
  audio/song_master.<ext>  analysis/ (grid.json, words.json optional)
  refs/ frames/ footage/final/ jobs.csv
  out/                  bases, text layers, finals, QA reports
```

Start `project.json` from `scripts/project.example.json`. Script names: `collect_sessions.py`, `analyze_song.py`, `validate_assets.py`, `plan.py`, `base.py`, `burn.py`, `qa.py`, `contact_sheet.py`.

## Overnight autonomy

If the user says "keep going while I sleep", you may answer your own questions as they would, logging each in `DECISIONS.md` (`# | Time | Decision | Why | How to undo`; "how to undo" names an action and its cost). Never decide alone on: publishing, anything on the handle-with-care list, raising the budget cap, sending material to a new vendor, or a line the reviewers flagged for the subject's own yes.

---

## Stage 0. Project folder, privacy and tools

1. Ask for a **separate private working folder** (not inside any repo) and make it. First action in it: write `.gitignore` containing `*` and `!.gitignore`. The skill repository's own ignore file does not protect it.
2. Check Python 3.10+, `ffmpeg`, `ffprobe`; install per `scripts/README.md`.
3. **Disclose before reading anything.** Tell the user, plainly: the collector runs locally, makes no network calls and drops messages containing credentials, but redaction is best-effort. The user inspects the collector's output files (`research/`) locally before any assistant reads them. Approved excerpts then leave the machine when a model drafts the dossier (you, sub-agents, a second-vendor reviewer), and again if any excerpt goes to a song, image or video provider. Name the processors you plan to use. The user approves the dossier before any downstream use, and approves any extra vendor before a source packet is sent to it. Handle-with-care details never go in such a packet.

**Gate:** folder and `.gitignore` exist, tools run, the user has seen the disclosure.

## Stage 1. Consent and ground rules

Ask, and write into `project.json` and the top of `treatment.md`:

1. **Who is roasted.** The user, or someone who agreed in writing to having their AI history read and roasted. Record `consent.given: true` and `consent.evidence` (what, when, how). No consent, no further work; do not read any history.
2. **Audience.** Private or public. Public raises the bar on employer, customers and anything clippable out of context.
3. **Off limits.** Default: other people's names, health, money, legal, family, dating, home security, credentials, and the employer's products, customers and colleagues.
4. **What may be named.** Usually no employer, products or real logos; third-party platform names as plain sung words only if the subject agrees.
5. **Tone.** The subject is cool and in on the joke. Ask how they want to look and what they reject.
6. **Budget.** Total cap, currency, reserve (at least 25%) and retake cap, into `budget`. Zero is a valid answer: it selects the zero-budget route.

**Gate:** `consent.given` true with evidence, off-limits list written, budget recorded.

## Stage 2. Pick your tools

Four roles: `song`, `transcription`, `images`, `video`. Each has a mode, recorded in `project.json` under `providers`:

- **mcp / cli:** a connected tool. Read its price before every paid call; log every job in `jobs.csv`.
- **manual:** you write a prompt pack in `handoff/`, the user makes the file in a web app and drops it in the project folder, you validate it. Fully walkable for every role.
- **none:** no tool. For `transcription` and `video` this is a normal choice.

**Zero-budget route:** `song` = a recording you own or make (manual), `images` = stills you make or already have (manual), `transcription` = none, `video` = none. The film is a stills animatic. Follow `references/providers.md` section 6 start to finish.

**Gate:** all four roles have a mode; expected spend per role stated and inside the cap.

## Stage 3. Research the person's own AI sessions

Mine only what the subject typed, on every computer they use. Run `collect_sessions.py` for Claude Code logs (it reads `.jsonl` only; other formats need the manual route in `references/research.md`), and work from digests, never whole transcripts. For a second computer, hand the user the portable block in `references/research.md`.

The dossier has fixed sections: projects, numbers, habits with exact quotes, funny moments with dates, catchphrases and typos with counts, journey, wins, **handle with care** (one line each, no detail), gaps. Mark inferences `(inferred)`. Never print a credential; quote exactly, typos included.

**Gate:** the dossier has counts, dated quotes and a handle-with-care section, and the subject has read it. Handle-with-care material is never used.

## Stage 4. Concepts and lyrics

Pitch three or four concepts (genre plus a hook from a real habit); the user picks. Write lyrics with a table: `line | fact | source`. Every line has a row or is cut. Keep a "to check" list. Read `references/lyrics-and-song.md`.

**Gate:** the user has read and approved the lyrics.

## Stage 5. Truth and privacy review, then approval to spend (if any)

On every route, before any song prompt or lyrics leave your hands (paid or free), run the **truth** and **privacy and employer** reviewers (`references/review-rubrics.md`) on the lyrics, the dossier excerpts they cite and the song prompt. Apply every BLOCK fix or remove the material; a ruling is not a fix until it is applied. Material only the subject can approve is left out of the prompts until approved. If any spending is planned (a paid song or transcription now; paid images and clips are also held until Stage 10), ask for the explicit yes to spend, with the cap. With a zero cap there is no spend to approve: say so and go on.

**Gate:** no open BLOCK on the lyrics and the dossier excerpts; consent still on record. If spending is planned, the user said yes to it and to the cap in this session. A zero cap passes without that yes.

## Stage 6. Song

Provider per `providers.song`: generate through a connected tool, or write `handoff/song_prompt.md` (style box, lyric box with section tags only, nothing else in brackets) for the user's own web app, or use the user's own recording. Ask for two takes where the tool allows; one usable recording is enough. Save under `audio/`.

**Gate:** at least one take saved.

## Stage 7. Measure the song; the song sets the length

Run `analyze_song.py` per take (separate `--out`), pick the master, copy to `audio/song_master.<ext>`, and set `project.json` `duration` to its real length. Details: `references/build-and-qa.md`. Do not cut the user's song without asking; `allow_trim: true` is for a deliberately longer song only.

**Gate:** `analysis/grid.json` exists; `duration` matches the song. `analysis/words.json` is optional: without it, set string times by ear.

## Stage 8. Treatment and cast

Write `treatment.md`: rules that cannot bend, look, cast, section plan, spine device, on-screen text plan, formats and budget. Read `references/treatment-and-cast.md`. The subject is relaxed and laughing hardest; every other character has a distinct silhouette, material and colour; one physical action per character per shot.

**Gate:** the user (or a logged decision) approves look and cast.

## Stage 9. Shot list and strings

Build `shots.csv` and `strings.csv` from the grid: cuts on bar lines, generated shots no longer than the clip length, code shots on plates for long text. Every string with a digit or quote has a `source`. Read `references/shot-list-schema.md`. Run `plan.py` until it resolves.

**Gate:** plan resolves; generated seconds times price fits the budget with the reserve.

## Stage 10. Adversarial plan review

Run all three reviewers (truth, privacy and employer, comedy) on the treatment, shots and strings, each with the dossier but not your reasoning. Merge into `review/plan-review.md`, write binding `review/rulings.md`, apply every BLOCK before any paid image or clip.

**Gate:** every BLOCK applied or removed; subject-only items on the hand-over list.

## Stage 11. Character refs and keyframes

One ref image per character, then one keyframe per generated clip, plus plates for code shots. Every sign, card and screen is generated **blank**; words are drawn in code. Read `references/generation.md`. View every image; redo freely, stills are cheap. Zero-budget: use the stills you have, same file names.

**Gate:** keyframes approved; `validate_assets.py` and a `contact_sheet.py` sheet checked.

## Stage 12. Motion test, then the batch

Skip this stage when `video` is `none`. Otherwise generate **two** clips (the subject; the busiest cast), check them, then release the batch under the cap with `jobs.csv`. Retake only hard failures, one corrective sentence each, within the retake cap. Details in `references/generation.md`.

**Gate:** every generated shot has a clip, or is knowingly left as a keyframe push-in.

## Stage 13. Build

Follow `references/build-and-qa.md`: `validate_assets.py`, `plan.py`, `base.py`, `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`. Text changes never need a new base. `qa.py` fails if the final came from an older plan.

**Gate:** QA passes, or each failure is accepted in `DECISIONS.md`.

## Stage 14. Adversarial cut review and one fix round

Export frames (`contact_sheet.py ... --strings` for one frame per string, plus the shot sheet), run the three reviewers on the cut, apply rows in one fix round, record each as applied, skipped (why) or no change. Back up `strings.csv` first.

**Gate:** no open BLOCK except those reserved for the subject's own yes.

## Stage 15. Hand-over

Write the report from `references/handover.md`: final path, length, spend by role against the cap, decisions, and a **"needs your yes before publishing"** list on top. Stop there. **The skill never uploads, posts or shares anything;** publishing needs the user's explicit yes, given outside this skill's run.

Lessons from the source project (misquotes, drifting claims, invented details, gibberish text, tags on faces): `references/lessons.md`.
