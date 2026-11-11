# Research: mining the subject's own AI sessions

Goal: one dossier per computer with true, dated, quotable material, plus a list of what must never be used. Read only what the subject typed.

## Contents
1. Ground rules
2. Where sessions live
3. Running the collector
4. What makes good material
5. Portable instructions for a second computer
6. Dossier template

## 1. Ground rules

- **Never read, print or copy a credential.** Skip `.env`, auth, token and credential files. If a message looks like it holds a key, drop the whole message. Keys in a roast dossier end up in prompts sent to other vendors.
- **Redaction is best-effort.** The collector runs locally with no network calls, but some secrets can get through. The subject inspects the collector's output files locally before any assistant reads them. Approved excerpts then leave the machine when a model drafts the dossier, and again if any excerpt goes to a provider. The subject approves the dossier before any downstream use.
- **Keep it out of git.** Work only in the private project folder whose `.gitignore` (`*` and `!.gitignore`) was written in stage 0.
- **Read only.** No installs beyond Python, no spending, no posting.
- **Only the subject's typed words.** Skip tool results, system text, sidechain or sub-agent messages, and lines that start with `<` or "This session is being continued". Those are machine text and will give you jokes about the AI, not the person.
- **Quote exactly**, typos included, under 25 words, with file and date. Misquotes are the most common failure later.
- **Other people stay out** of the main sections. Name them only as "a colleague", "a customer" in handle-with-care.
- **Health, money, legal, family, dating, home security** go in handle-with-care, one line, no detail.
- Mark anything you inferred rather than read as `(inferred)`, because reviewers need to know which claims are soft.

## 2. Where sessions live

Paths differ by OS; `~` is the home folder (`%USERPROFILE%` on Windows).

| Tool | Where | What to take |
|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl`; also `memory/*.md`, `CLAUDE.md` | lines with `type` = "user", `isSidechain` not true, `message.content` a string or a text item |
| Claude desktop app | app data folder (`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS) | readable session JSON, if any (manual route) |
| Codex CLI | `~/.codex/sessions/` | prompts the user typed |
| Gemini CLI | `~/.gemini/` (chats, `logs.json`, `GEMINI.md`) | user turns |
| Project folders | wherever sessions point | README files; `git log --format="%ad %s" --date=short` (dates and messages only) |

Web chat exports (if the subject downloads them) can be used through the manual route; treat them the same way. The collector does not read them.

## 3. Running the collector

`collect_sessions.py` reads `.jsonl` session logs only. By default it reads Claude Code logs under `~/.claude/projects`; other tools' logs are read only if they use the same record shape (`type` "user", text content); check the counts it prints. Codex, Gemini and desktop-app JSON, and web chat exports, are **not** read: it counts them as unsupported and skips them. For those, use the portable block in section 5 on that machine, or have the user paste a redacted export, and say in the dossier's Gaps section which sources were not read.

```
python "$SKILL_SCRIPTS/collect_sessions.py"
python "$SKILL_SCRIPTS/collect_sessions.py" --no-default --root D:/exports/claude-logs --out research --since 2025-01-01
```

Flags: `--root PATH` (repeatable; a folder or a `.jsonl` file), `--no-default`, `--out DIR`, `--since YYYY-MM-DD`, `--max-chars N`, `--samples N`, `--top N`, `--seed N`. It keeps only what the human typed (it skips tool results, injected reminders, sub-agent prompts, "This session is being continued" summaries, pasted blocks and duplicates, and counts each), and writes `research/digest.json`, `digest.md` and `messages.jsonl` (project, source file, line, timestamp, text). Messages with credentials are dropped whole and counted. Work from the digests; delegate one sub-agent per few projects to draft dossier sections, then merge.

## 4. What makes good material

- **Repeated one-word messages** ("punchier", "again", "go") with counts. These make choruses.
- **Reversals** on the same day: praise at one time, rejection a few hours later.
- **Absurd requests** and arguments with an AI, with the best quote.
- **Typos** that recur, with counts, shown exactly as typed.
- **Rhythm numbers:** messages by hour, by weekday, busiest day, longest session.
- **Public self-claims** (bio lines, project pages) only if the subject agrees, and quoted from the page itself, not a tool's summary.

Weak material: anything needing a paragraph of context, anything about other people, anything that reads as a professional failing to an employer or customer.

## 5. Portable instructions for a second computer

Give the user this block to paste into an AI coding session on the other computer. Replace `<NAME>` with the subject's first name.

```
I am making a funny music video about myself from my own AI chat history.
Mine this computer's AI sessions and write ONE file: ~/roast-dossier/DOSSIER.md
(create the folder). Change nothing else.

Rules
- Never read, print or copy an API key, password, token or credential. Skip
  .env, auth and credential files. Drop any line that looks like a key.
- Read only. No spending, posting or installs beyond Python.
- Every item needs a source: file path and date. Quote <NAME>'s own words
  exactly, typos included, under 25 words.
- Other people: no names or details in the main sections; list them only in
  section 8 as "a colleague", "a customer" and so on.
- Health, money, legal and private family matters: section 8 only, one line
  each, no detail.
- Mark anything inferred as (inferred). Plain English.

Where to look
1. Claude Code: ~/.claude/projects/*/*.jsonl. Only lines with type "user",
   isSidechain not true, message.content a string or text item. Skip tool
   results and text starting with "<" or "This session is being continued".
   Also memory/*.md and CLAUDE.md files.
2. Claude desktop app data folder (readable session JSON only).
3. Gemini: ~/.gemini/. 4. Codex: ~/.codex/sessions/ (typed prompts only).
5. Project READMEs and git log --format="%ad %s" --date=short.
Write a small Python script that pulls <NAME>'s typed messages with
timestamps into per-project digests, and work from those, not whole
transcripts.

Write these sections in this order (template below).
When done, reply with the file path and the section 2 totals.
```

Then paste the dossier template (section 6) under it. The user carries the file back (USB stick, cloud drive, or pasting the text) to `research/<computer-name>/DOSSIER.md`.

When merging two dossiers, keep counts per computer and say so on screen ("one computer only") unless you have truly de-duplicated them.

## 6. Dossier template

```markdown
# DOSSIER: <first name>, <computer label>, <date range>

## 1. Projects
| name | what it is, one line | first seen | last seen | sessions | status | source |

## 2. Numbers
Totals: sessions, typed messages, date range.
Messages by hour of day (table). Messages by weekday (table).
Longest session. Busiest days (top 5).
30 most repeated short messages, with counts.
Slash commands with counts. Interrupts. Git numbers (say how counted; note
duplicates, rebases and AI-authored commits).

## 3. Habits and quirks
15 to 30 items. Each: one line, then 1 or 2 exact quotes with date and file.

## 4. Funny moments
15 to 30 short true stories. Each: date, what happened in 2 or 3 sentences,
best quote.

## 5. Catchphrases and typos
Recurring words with counts. Typos exactly as typed, with counts.

## 6. Journey
10 to 25 dated lines: how projects and tools changed.

## 7. Things they are proud of
Real wins and numbers, with sources.

## 8. Handle with care
### People   (one line each: "a colleague", "a customer", no names)
### Sensitive matters   (one line each, no detail)

## 9. Gaps
What could not be read and why.
```

Worked example of one habit row (fictional subject "Sam, a product manager"):

```
- Ends every planning session by asking for a punchier version.
  "ok make it punchier. no, punchier" (2026-02-11, proj-roadmap digest)
  "even punchier pls" (2026-03-27, proj-launch digest)
```
