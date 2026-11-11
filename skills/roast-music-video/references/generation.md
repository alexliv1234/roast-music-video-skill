# Generation: refs, keyframes, clips

Provider-agnostic. Model names and prices change; read `providers.md` for how to connect or hand off each role.

## Order

1. Style baseline: one text file (`refs/baseline.txt`) with the style block, palette and "no text" line, pasted into every prompt.
2. Character refs: one image per character on a plain background, full body, front three-quarter view.
3. Keyframes: one per generated clip (`frames/k_<clip_id>.png`), plus blank plates for code shots (`frames/<plate>.png`; the plate id already starts with `K_`, so plate `K_CURTAIN` is `frames/K_CURTAIN.png`). `plates.csv` is a catalogue the scripts do not read.
4. Motion test: two clips.
5. Batch, with the job log and budget cap.
6. Retakes, hard failures only.

Stills are cheap or free on many tools and can be redone at will; clips cost real money. Spend iteration on stills. Paid image and clip calls start only after the Stage 5 review, the user's yes to the spend and the cap, and the Stage 10 plan review (SKILL.md). A zero cap needs no spend approval.

## Keyframe prompt pattern

Build each prompt from fixed blocks in this order, so every keyframe shares the same look:

```
<STYLE> Bold 2D cartoon illustration, thick confident ink line (#1B1B1F), flat
colour with one soft shadow tone, a little paper grain, palette <hexes>, not
photoreal, 16:9.
<SETTING> <the setting sentence from the treatment>.
<SHOT> <what we see at the first frame, one action about to happen>.
<CAST> <name>: <full description> (use the reference image of <name>); ...
<FRAMING> <wide / medium / close>, <where each character sits in frame>.
<NO TEXT> No text, letters, numbers or logos anywhere; every sign, card,
screen, receipt and button is blank.
```

- Describe every cast member in full in every prompt, even with a ref attached, because some tools weight text over images.
- Compose for the text you will add: leave a clean area where the card, bubble or caption goes, away from faces.
- Surfaces that will carry text are simple and front-facing (a flat card, a phone screen square to camera), so code-drawn text can sit on them convincingly.
- Clocks, calendars, receipts and screens get no numerals, hands or lines.

## Motion prompt pattern

```
Animate this 2D cartoon illustration as fluid, high-quality 2D animation,
keeping every character design, the line art and the colours exactly.
First two seconds: <action A>. Last two seconds: <action B>.
<camera: locked / slow push-in / smooth pan right ending on X>.
No new characters, no text.
```

- One clear physical action per character. "Throws head back laughing and slaps the armrest" animates; "is amused" does not.
- Split a 4 s clip into two halves with different actions when the shot list reuses the clip for two one-bar shots.
- Name the camera move. Unnamed, models drift.

Fictional example (Sam, a product manager):

```
Animate this 2D cartoon illustration ... exactly. First two seconds: the seven
Drafts robots hop onto the desk in a row, each one smaller than the last. Last
two seconds: Sam laughs, waves them down with her notebook, and the smallest Draft
salutes. Camera locked. No new characters, no text.
```

## Settings that matter

- Start image: the approved keyframe.
- Length: the model's standard clip (often 4 or 5 s); the shot list assumes one value.
- Aspect 16:9 (or the project's format), resolution as in `project.json` (720p is enough for this look).
- No audio (the song is muxed later); if the tool always adds audio, it is stripped in the build.
- Draft resolution first only if the tool's draft is truly cheaper and close in look.

## Motion test

Before the batch, generate two clips: the one with the subject's face largest, and the one with the most characters. Pass if: likeness holds for all four seconds, no character appears or changes, no text appears, the planned action happens, and the line art stays clean. Fix the prompt pattern before spending on the rest.

## Batch and job log

Append one row per job to `jobs.csv`:

```
time,clip_id,version,job_id,model,resolution,seconds,credits,status,file
2026-03-04T01:40,G05,1,abc123,<model>,720p,4,<cost>,done,footage/final/G05_v1.mp4
```

- Check the price before each paid call; stop at the cap in `project.json` and report.
- Submit in small batches; review each batch on a contact sheet before releasing the next.
- Save as `footage/final/<clip_id>_v<N>.mp4`; the highest N wins in the build.

## Retake rule

Retake only hard failures:
- text or letters appeared;
- smearing, melting or a body breaking apart;
- the planned action did not happen;
- a character changed design, or a new one appeared;
- the subject looks wrong (likeness lost, looks unhappy).

Keep odd motion that reads as a cartoon gag. A retake prompt is the original prompt plus **one** corrective sentence ("The paper stays completely blank, no marks of any kind."), so you know what fixed it and nothing else changes. Set a retake cap (for example 10% of clips) and log each retake as a decision.

## Zero-budget path

If image-to-video is `none`, skip the motion test and the batch. `plan.py` resolves a missing clip to its keyframe and `base.py` renders it with a slow push-in, so the full film builds as a stills animatic. Text, song and QA work the same. The complete route is `providers.md` section 6.
