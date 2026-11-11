"""analyze_song.py <song> : length, tempo, first downbeat, bar length and section guesses -> analysis/grid.json
Optional --words : word timings -> analysis/words.json (needs faster-whisper or openai-whisper). Transcription runs locally; first use may
download model weights. Audio is not uploaded.

Needs librosa (python -m pip install librosa soundfile). Without it this script says so and exits; you can still write analysis/grid.json by hand
(see README: duration, tempo, first_downbeat, beats_per_bar, bar_length) and the rest of the pipeline works.

The grid is an estimate: it assumes 4 beats to the bar and picks the downbeat phase with the strongest low-frequency energy.
Listen to the first bars and correct first_downbeat / tempo by hand if they are off; every cut should land on a bar or beat line.
After analysis, set project.json "duration" to the song's real length (printed below): build and QA fail if they differ by more than 0.25 s.

Paths: the project folder is ROAST_PROJECT_DIR if set, else the current folder. A relative song path is resolved under that
folder; --out is relative to it (default analysis/). Run one command per take with its own --out (analysis/take1, analysis/take2).

Usage:
  python analyze_song.py audio/song_master.mp3
  python analyze_song.py audio/song_master.mp3 --words [--model base] [--lang en] [--bpb 4] [--sections 6] [--out analysis]"""
import sys, os, json, argparse
from roots import project_root, under_root, raw_project, write_json

def need_librosa():
    try:
        import librosa  # noqa
        return librosa
    except ImportError:
        raise SystemExit('librosa is not installed, so the beat grid cannot be estimated automatically.\n'
                         '  Install it with:  python -m pip install librosa soundfile\n'
                         '  Or write analysis/grid.json by hand: {"duration": 30.0, "tempo": 120.0, "first_downbeat": 0.0, "beats_per_bar": 4, "bar_length": 2.0}')

def analyze(path, bpb, n_sections):
    librosa = need_librosa(); import numpy as np
    y, sr = librosa.load(path, sr=22050, mono=True)
    dur = float(len(y) / sr)
    hop = 512
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, tightness=120)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    if len(beats) < bpb * 2:
        raise SystemExit('could not find enough beats in %s (found %d); is it a normal song?' % (path, len(beats)))
    # snap tempo to the median beat spacing, which is steadier than the headline estimate for a generated, quantised song
    idx = np.arange(len(beats))
    spacing, off = np.polyfit(idx, beats, 1)           # least-squares line through the beat times: finer than frame-quantised beats
    spacing = float(spacing); tempo = 60.0 / spacing
    beats = off + spacing * idx
    # downbeat phase: low-frequency energy at each beat, pick the phase (0..bpb-1) with the strongest mean
    S = np.abs(librosa.stft(y, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr)
    low = S[freqs < 150].sum(axis=0)
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    n = min(len(low), len(onset))
    score = (low[:n] / (low[:n].max() + 1e-9)) + (onset[:n] / (onset[:n].max() + 1e-9))
    bf = np.clip(beat_frames, 0, n - 1)
    phase_scores = [float(np.mean(score[bf[p::bpb]])) for p in range(bpb)]
    phase = int(np.argmax(phase_scores))
    first_down = float(beats[phase])
    # extend the grid back to the start so the first bar line is the earliest one at or after 0
    bar = spacing * bpb
    while first_down - bar >= -1e-3: first_down -= bar
    bars = []; t = first_down
    while t < dur - 1e-3: bars.append(round(t, 3)); t += bar
    # sections: cluster bar-synchronous features, then cut where the clusters change
    sections = []
    try:
        feat = np.vstack([librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop),
                          librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop)])
        bar_frames = librosa.time_to_frames(np.array(bars + [dur]), sr=sr, hop_length=hop)
        bar_frames = np.clip(bar_frames, 0, feat.shape[1] - 1)
        sync = librosa.util.sync(feat, bar_frames[:-1], aggregate=np.mean) if len(bar_frames) > 2 else feat
        k = max(2, min(n_sections, sync.shape[1] // 2))
        seg = librosa.segment.agglomerative(sync, k)            # bar indices where a new section starts
        starts = sorted(set([0] + [int(s) for s in seg if 0 < int(s) < len(bars)]))
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        edges = [0.0] + [bars[i] for i in starts[1:]] + [dur]
        loud = []
        for a, b in zip(edges[:-1], edges[1:]):
            fa, fb = int(a * sr / hop), max(int(b * sr / hop), int(a * sr / hop) + 1)
            loud.append(float(np.mean(rms[fa:fb])))
        med = float(np.median(loud))
        for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            label = 'intro' if i == 0 else 'outro' if i == len(loud) - 1 else ('high-energy' if loud[i] > med * 1.08 else 'low-energy')
            sections.append({'start': round(a, 3), 'end': round(b, 3), 'bars': int(round((b - a) / bar)), 'label_guess': label, 'rms': round(loud[i], 4)})
    except Exception as e:
        print('section guess skipped: %s' % e, file=sys.stderr)
    return {'file': os.path.basename(path), 'duration': round(dur, 3), 'tempo': round(tempo, 2), 'beats_per_bar': bpb,
            'first_downbeat': round(first_down, 3), 'bar_length': round(bar, 4), 'beat_length': round(spacing, 4),
            'downbeat_phase_scores': [round(s, 3) for s in phase_scores], 'bars': bars, 'sections': sections,
            'note': 'estimated; 4/4 assumed; check by ear and edit by hand if needed'}

def words(path, model_name, lang):
    out = []
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(model_name, compute_type='int8')
        segs, _ = m.transcribe(path, word_timestamps=True, language=lang)
        for s in segs:
            for w in (s.words or []): out.append({'word': w.word.strip(), 'start': round(w.start, 3), 'end': round(w.end, 3)})
        return out, 'faster-whisper'
    except ImportError:
        pass
    try:
        import whisper
    except ImportError:
        raise SystemExit('--words needs faster-whisper or openai-whisper (neither is installed).\n'
                         '  python -m pip install faster-whisper     (or: python -m pip install openai-whisper)\n'
                         '  Or write analysis/words.json by hand as a list of {"word": "...", "start": 0.0, "end": 0.4}.')
    m = whisper.load_model(model_name)
    r = m.transcribe(path, word_timestamps=True, language=lang)
    for s in r['segments']:
        for w in s.get('words', []): out.append({'word': w['word'].strip(), 'start': round(w['start'], 3), 'end': round(w['end'], 3)})
    return out, 'openai-whisper'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('song'); ap.add_argument('--out', default='analysis')
    ap.add_argument('--bpb', type=int, default=4, help='beats per bar (default 4)')
    ap.add_argument('--sections', type=int, default=6, help='how many sections to guess (default 6)')
    ap.add_argument('--words', action='store_true', help='also transcribe word timings to words.json')
    ap.add_argument('--model', default='base', help='whisper model size for --words (tiny, base, small, medium ...)')
    ap.add_argument('--lang', default=None, help='language code for --words, e.g. en (default: detect)')
    a = ap.parse_args()
    if not 1 <= a.bpb <= 16: ap.error('--bpb must be a whole number from 1 to 16 (beats per bar)')
    if a.sections < 1: ap.error('--sections must be 1 or more')
    root = project_root()
    song = under_root(a.song, root)
    if not os.path.isfile(song): raise SystemExit('song not found: %s (relative paths are under %s)' % (song, root))
    out = under_root(a.out, root)
    os.makedirs(out, exist_ok=True)
    g = analyze(song, a.bpb, a.sections)
    p = os.path.join(out, 'grid.json'); write_json(p, g)
    print('%.2f s, %.2f BPM, first downbeat %.3f s, bar %.3f s, %d bars, %d sections -> %s' % (g['duration'], g['tempo'], g['first_downbeat'], g['bar_length'], len(g['bars']), len(g['sections']), p))
    for s in g['sections']: print('  %7.2f - %7.2f  %2d bars  %s' % (s['start'], s['end'], s['bars'], s['label_guess']))
    proj = raw_project(root).get('duration')
    if isinstance(proj, (int, float)) and abs(proj - g['duration']) > 0.25:
        print('NOTE: project.json duration is %.2f s but this song is %.2f s. Set "duration": %.2f (or "allow_trim": true to cut a longer song on purpose).' % (proj, g['duration'], g['duration']))
    elif proj is None:
        print('NOTE: set "duration": %.2f in project.json.' % g['duration'])
    if a.words:
        w, engine = words(song, a.model, a.lang)
        p = os.path.join(out, 'words.json'); write_json(p, w)
        print('%d words (%s) -> %s' % (len(w), engine, p))

if __name__ == '__main__':
    main()
