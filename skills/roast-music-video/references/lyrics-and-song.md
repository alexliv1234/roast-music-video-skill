# Concepts, lyrics and the song

## Concepts

Pitch three or four. Each concept is one paragraph plus a section sketch:

- **Genre** (show tune, brag rap, power ballad, nature documentary with a drop).
- **Hook:** one real habit that a crowd can shout. The most repeated short message is usually it.
- **Who sings:** the joke lands harder when the AI helpers sing about their boss, because the model writing it is part of the joke.
- **Look** in one line.
- **Rough cost** at the planned resolution and clip price, marked as an estimate.

Recommend one and say why. Let the user choose.

## Structure that works

| Section | Job |
|---|---|
| Intro | an MC sets up who is being roasted, in two lines |
| Verse 1 | one roaster, one kind of joke (habits) |
| Chorus | the hook: the subject's own vocabulary as a chant, with counts |
| Verse 2 | a second roaster, reversals and impossible notes |
| Verse 3 | fast patter: numbers and typos |
| Bridge | soft: the one kind thing the subject says to their AI, then undercut it |
| Final chorus | biggest |
| Outro | the subject's whole rebuttal in one word |

Each verse belongs to a different roaster with a different kind of joke, so the video has a new character and a new setting per section.

## Lyric rules

- **Every line has a source row.** Under the lyrics, keep `line | fact | source (dossier section, date)`. A line with no row is cut.
- **Sing approximations, show exact words.** A sung line may round ("forty", "quarter to nine"); the on-screen card shows the exact quote, date and number. Note each rounding in a "to check" list.
- **Do not merge two quotes into one line and then show it as one message.** If you merge for rhythm, the picture must show them as two dated cards.
- **Narrow numbers.** If a count covers one computer, one repo or one date range, say so on screen.
- **No names** of the employer, its products, customers or colleagues, sung or shown. Third-party platform names only if the subject agreed, and never as logos.
- **Weakest lines are flagged,** so a reviewer or picture gag can cover them.

Example lines (fictional subject "Sam, a product manager", whose habit is typing "punchier"):

```
[Verse 1]
She sent us off for slides, then she sent us back for zing
Seven drafts by midnight and she typed the same one thing
```

With the source table row:

| Line | Fact | Source |
|---|---|---|
| typed the same one thing | "punchier" typed 137 times as a whole message | dossier 2, top short messages |

(The number is invented for the example.)

## The song

The song comes from the provider set in `providers.song`: a connected tool, the user's own web app (manual hand-off, walked through in `providers.md` section 4), or a recording the user owns. For the first two, write `handoff/song_prompt.md` with two boxes.

**Style box** (one paragraph): genre, tempo in BPM, key instruments, lead voices and where they change, "big gang-vocal chant on the word X", "clear diction, every word intelligible", "clean ending, no fade-out". A clean ending gives the edit a last beat to land on.

**Lyric box:** section tags and sung words only.

```
[Intro]
Pull up a chair, you helpers, grab a seat
Tonight the boss is getting what she typed

[Chorus]
Punchier! Punchier!
...
```

Rules that stop the model singing what it should not:
- Only section tags go in square brackets. No `(spoken)`, no speaker names, no stage directions, no notes. Models sing anything in the box that looks like words.
- Spell letters the way they should be sung ("A P I", "Q A").
- Write numbers as words ("ninety-one"), so the singer says them the way you will caption them.
- Keep proper nouns you do not want sung out of the box entirely.

Ask for at least two takes. The song tool's own "extend" or "continue" may produce a take with a better ending; keep all takes.

## Choosing a take

Measure, do not guess (`analyze_song.py` once per take, see `build-and-qa.md`). Prefer:
1. the steadier beat grid, because every cut lands on it;
2. a ring-out or clean ending over a hard stop on the last sample;
3. all sections present, no repeated or missing lines;
4. hook words sung as intended (letters as letters).

Extra sung words (a repeated last word, an ad-lib) are fine if they suit the joke; note them, because the captions must follow what is sung, not what was written.
