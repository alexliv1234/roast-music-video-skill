# Providers: pick your tools, connect them or hand off

No provider is required. Every vendor named here is an example only; model names, features and prices change often, so check current docs and prices before you plan a budget.

## Contents
1. The four modes
2. Roles: what the skill needs
3. Connected-tool mode
4. Manual hand-off mode
5. Bring your own (`project.json`)
6. Zero-budget route

## 1. The four modes

| Mode | When | What the agent does |
|---|---|---|
| `mcp` | an MCP server for the tool is connected | discovers its tools with tool search, reads the price, runs jobs, logs them |
| `cli` | a command-line tool is installed and signed in | same, through the shell |
| `manual` | no account, no connector, or the user prefers their own web app | writes a prompt pack in `handoff/`, says where to save results, validates the files, continues |
| `none` | the role is not used | skips the role; see the table in section 5 for what each role does without a tool |

Every route needs the Stage 5 truth and privacy review cleared and the person's consent. Approval to spend is needed only when spending is planned, and a zero cap proceeds without it. Paid song and transcription calls require Stage 5 approval; paid images and clips additionally require Stage 10 (SKILL.md).

The source project mixed modes: a manual song, CLI keyframes, connected clips.

## 2. Roles: what the skill needs

### Song
- **In:** style box and lyric box (`lyrics-and-song.md`).
- **Out:** at least two full takes as MP3 or WAV, 44.1 or 48 kHz, stereo.
- **Settings that matter:** custom lyrics mode (not auto-written), tempo in the style text, clean ending, no fade-out. Download the full take, not a preview.
- **Without a provider:** a recording the user made or owns the rights to (one take is enough), dropped in as `audio/take1.<ext>`.
- **Examples:** Suno, Udio, or any song model on a connected service.

### Transcription (word times; role `transcription`)
- **In:** the master song (or its vocal stem).
- **Out:** word-level timestamps as JSON.
- **Settings that matter:** word timestamps on; the lyric text as a prompt or hint if the tool accepts one.
- **Mode `none`:** allowed and common. Skip `--words` and set string times by ear from the grid; `analysis/words.json` is optional.
- **Examples:** a local Whisper model (free, used by `analyze_song.py --words` if installed), or a hosted transcription API.

### Images (refs, keyframes, plates)
- **In:** prompts from `generation.md`, character refs as image inputs.
- **Out:** PNG at or above the video resolution, in the project aspect (16:9 by default).
- **Settings that matter:** image reference or edit input for consistent characters; aspect ratio; no drawn text (say it in the prompt; check every output).
- **Without a provider (mode `manual`):** stills the user draws, photographs or already has, saved under the same file names. Image generation is the one role that needs some source of pictures.
- **Examples:** Codex CLI image generation, Higgsfield, Scenario, or any image model you can call.

### Image-to-video (clips)
- **In:** start image (the keyframe), motion prompt.
- **Out:** MP4, the model's standard length (often 4 or 5 s), 16:9, 720p or more, 24 to 30 fps.
- **Settings that matter:** start-image mode, fixed duration, aspect 16:9, no audio, no drawn text, no extra characters.
- **Mode `none`:** stills animatic, no clips (section 6).
- **Examples:** Higgsfield, Kling, Runway, Luma, Veo or similar, through MCP, CLI or a web app.

### Voice or SFX (optional)
- **In:** a line or a sound description.
- **Out:** WAV or MP3.
- **Use:** a spoken MC line in the intro, a rimshot, applause. The build mixes only the song. Extra audio must be mixed into one approved master outside the build and supplied as the `song` file.
- **Examples:** ElevenLabs or any TTS/SFX tool.

## 3. Connected-tool mode

1. **Discover.** Use your tool search (for example a query like "video generate image-to-video") to find connected servers. Read each tool's schema; do not guess parameter names.
2. **Price first.** Use the tool's quote or dry-run feature, or its published price, before every paid call. Multiply by the planned count and compare with the cap in `project.json`.
3. **Small first.** One test job per role before any batch (for clips, the two-clip motion test).
4. **Log.** Every job goes in `jobs.csv` with its job id, model, resolution, seconds, credits and status, so spend can be audited and failed jobs found.
5. **Never retry blindly.** A repeated generation call usually charges again. Poll the existing job instead.
6. **Download and rename** to the project layout: `audio/`, `frames/k_<clip_id>.png` (plates `frames/<plate>.png`), `footage/final/<clip_id>_v<N>.mp4`.

## 4. Manual hand-off mode

Write one file per job the user must run, tell them where to save the result, then validate.

### Song pack: `handoff/song_prompt.md`

```markdown
# Song prompt pack

1. Open your music tool in custom-lyrics mode.
2. Paste the STYLE box into the style field and the LYRICS box into the lyrics field.
3. Generate at least two takes. Download each full take.
4. Save them as audio/take1.mp3, audio/take2.mp3 in the project folder.
5. Tell me when they are saved.

## STYLE
<one paragraph>

## LYRICS
<section tags and sung words only>
```

### Clip pack: `handoff/clips/<clip_id>.md`

```markdown
# G05

- Start image: frames/k_G05.png
- Duration: 4 s   Aspect: 16:9   Resolution: 720p   Audio: off
- Motion prompt (paste exactly):

  Animate this 2D cartoon illustration ... No new characters, no text.

- Save as: footage/final/G05_v1.mp4
- Reject and redo if: any text appears, a character changes or a new one
  appears, the action does not happen.
```

Also write `handoff/clips/INDEX.md` listing every clip id in order with checkboxes, so the user can work through them in one sitting.

### Validation

When the user says files are saved, check each one before continuing. At Stage 6 check each song take directly with `ffprobe` and by listening (`validate_assets.py` needs `audio/song_master.*`, the set `duration` and the Stage 9 shot sheet, so run it only after the master is chosen, `duration` is set and `shots.csv` exists; it then covers the song and every shot):
- **Song:** exists, plays, length within reason of the lyrics, not a 30 s preview, sample rate and channels.
- **Clip:** exists, duration close to the planned seconds, aspect and resolution, fps, no audio stream needed.
- **Image:** exists, size and aspect.

Report what passed and what needs a redo in one short list. `plan.py`, `base.py` and `validate_assets.py` report missing or short clips too.

## 5. Bring your own (`project.json`)

The user fills in one block, so replacements are explicit and the scripts and later sessions know which mode each role uses:

```json
"providers": {
  "song":     {"name": "<your music tool>", "mode": "manual", "notes": "own account"},
  "transcription": {"name": "whisper (local)", "mode": "cli", "notes": ""},
  "images":   {"name": "<image tool>",      "mode": "cli",    "notes": "free tier"},
  "video":    {"name": "<video tool>",      "mode": "mcp",    "notes": "cap in budget"}
}
```

The four roles are exactly `song`, `transcription`, `images`, `video`; each has `name`, `mode` and `notes`. (`stt` still loads, with a warning; voice and sound effects are not build roles, see the optional-audio note above.)

| Role | Modes | If `none` |
|---|---|---|
| `song` | `mcp`, `cli`, `manual`, `none` | no generated song: bring your own recording as `audio/take1.<ext>` |
| `transcription` | `mcp`, `cli`, `manual`, `none` | no word times: set string times by ear |
| `images` | `mcp`, `cli`, `manual`, `none` | no generated images: bring your own stills |
| `video` | `mcp`, `cli`, `manual`, `none` | no clips: stills animatic |

## 6. Zero-budget route

No paid provider at all, start to finish. Set `budget.total` to 0, and in `project.json` set `song` to `manual` (or `none`), `transcription` to `none`, `images` to `manual`, `video` to `none`.

1. **Song.** Record yourself (or a friend) performing the approved lyrics over any backing you own, or use a track you hold the rights to. Save it as `audio/take1.<ext>` (MP3, WAV or M4A, with an audio stream); copy the chosen one to `audio/song_master.<ext>`. A free tier of a web song tool also works as a manual hand-off (section 4); free does not mean no review, so Stage 5 still applies.
2. **Measure.** `analyze_song.py audio/take1.mp3 --out analysis/take1` if librosa is installed; otherwise write `analysis/grid.json` by hand (`build-and-qa.md`). Set `duration` in `project.json` to the real length. Skip `--words`.
3. **Stills.** Make or find one image per generated shot and name it `frames/k_<clip_id>.png`; make blank plates for code shots as `frames/<plate>.png`. Drawings, collages, screenshots of your own blank-card mock-ups or a free image tool all work. Keep every surface blank: words are drawn in code. Any image you source must be yours to use, with no real logos and no real people other than the consenting subject.
4. **Sheets.** Write `shots.csv` and `strings.csv`; set string times by ear against the bars. Leave `clip_id` set on `gen` shots (clips will be missing; the keyframe is used).
5. **Check and build.** `validate_assets.py` (expect KEYFRAME-ONLY for every generated shot), `plan.py`, `base.py` (each keyframe gets a slow push-in), `burn.py --qa`, `burn.py`, `burn.py --mux`, `qa.py`. The output is `out/animatic_vN.mp4`.
6. **Review and hand over.** Cut review and hand-over as normal. Skip the motion test and the batch.

It is also a good first cut with a budget: the subject can approve jokes and timing before anything is paid for, and real clips drop in later one by one (`footage/final/<clip_id>_v1.mp4`, then rerun from `plan.py`).
