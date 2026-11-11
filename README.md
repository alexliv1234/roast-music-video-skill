# roast-music-video-skill

A Claude Code skill that researches your own AI chat history and makes a roast music video about you.

It reads the messages you typed into Claude Code, Codex, Gemini and similar tools (on one computer or several), finds what is true and funny, writes a song where every line has a source, and builds a cartoon music video in which you are the cool guest of honour at your own roast. Three review gates (lyrics, plan and cut) check every quote, number and privacy risk. It ends with a hand-over report and never publishes anything by itself.

Example output: https://youtu.be/zjHfUPFfB_o

## Quick start

In Claude Code, install the skill (once):

```
/plugin marketplace add alexliv1234/roast-music-video-skill
/plugin install roast-music-video@roast-music-video
```

In a terminal, make a **separate, private project folder** (not inside this repo) and install the core dependencies. ffmpeg and ffprobe must be on PATH.

```
mkdir my-roast && cd my-roast
python -m pip install pillow opencv-python numpy
claude
> Make a roast music video about me from my AI chat history.
```

The skill starts by writing a `.gitignore` (`*` and `!.gitignore`) into the project folder, so research, photos and audio cannot be committed by accident. It then asks about consent, ground rules, budget and tools, and works stage by stage with a gate between each. The beat-grid step needs the analysis extras (librosa); if you skip them, the skill writes the grid by hand. Exact commands, with the installed scripts path, are in `skills/roast-music-video/scripts/README.md`.

## Install

**As a Claude Code plugin:** the two `/plugin` commands above.

**As a plain skill folder:** copy `skills/roast-music-video/` to `~/.claude/skills/roast-music-video/` (personal) or `.claude/skills/roast-music-video/` inside a project. The scripts travel with it in `skills/roast-music-video/scripts/`.

## Requirements

- Python 3.10+, and both `ffmpeg` and `ffprobe` on PATH. Core packages: `skills/roast-music-video/scripts/requirements.txt` (Pillow, OpenCV, numpy). Beat-grid analysis: `requirements-analysis.txt` (librosa, soundfile). A local Whisper model for word timings is optional.
- Four provider roles, each `mcp`, `cli`, `manual` or `none`: `song`, `transcription`, `images`, `video`. A manual hand-off means the skill writes a prompt pack, you generate the file in a web app and drop it in the project folder. See `skills/roast-music-video/references/providers.md`.
- **Zero budget:** no paid provider is needed. Use a song you record or own, stills you make or already have, and set `video` to `none`; the film builds as a stills animatic with slow push-ins.

## Cost

Costs vary a lot by provider and change often. The skill reads prices before spending, agrees a cap with you before any paid call, runs a two-clip motion test before a batch, and logs every job. Nothing paid (song, images, video) starts until the lyrics and claims have been reviewed and you have approved them.

## Privacy and consent

- **Roast only yourself, or someone who has agreed in writing.** The skill asks first, records it in `project.json` (`consent`), and stops without consent.
- **The collector runs locally and makes no network calls**, reads only what you typed, and drops messages that contain credentials. This is best-effort: some secrets can slip through, so you inspect its output files locally before the assistant reads them, and you approve the dossier before any downstream use.
- **Excerpts leave your machine when you use a model or media provider.** The assistant you run, any second-vendor reviewer and any song, image or video service you pick process the text you give them. The skill tells you who they are and asks before sending anything to an extra vendor.
- **Nothing sensitive is used.** Other people, health, money, legal, family and home matters go in a handle-with-care list that is never used. By default the employer, its products, customers and colleagues are never named or shown, and no real logos are drawn.
- **Nothing is published by the skill.** The hand-over report lists every line that needs your own yes before you post it.
- **Keep private files out of git.** The skill writes a `.gitignore` in your project folder. This repo's own `.gitignore` does not protect other folders.

## Layout

```
skills/roast-music-video/SKILL.md        the method, stages and gates
skills/roast-music-video/references/     research, lyrics, cast, schemas, reviews, generation, build, hand-over, providers
skills/roast-music-video/scripts/        collection, song analysis, plan, render, text layer, QA (see its README.md)
```

## Licence

MIT. See `LICENSE`.
