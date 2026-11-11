"""collect_sessions.py : what does a person actually type to their AI assistant? -> research/digest.json, research/digest.md, research/messages.jsonl
Scans local session logs (default: ~/.claude/projects/**/*.jsonl, Claude Code) plus any folders or files given with --root (any *.jsonl of
chat records; Codex-style and plain {"role":"user","content":...} records are understood too). Reads files only; makes no network calls.
Other formats (Gemini or desktop *.json exports, web exports) are NOT read: the digest reports how many *.json files it saw under --root
folders and skipped. Convert them to one JSON object per line first, or build a dossier by hand.

BEST EFFORT ONLY. The redaction below catches many credential formats, not all of them. The output is private data about a real person:
INSPECT research/ LOCALLY before anything in it is shared, pasted into another tool, or committed. Get the subject's consent first.

What is kept: only messages the human typed. Skipped and counted: tool results, injected reminders, command wrappers, sub-agent prompts,
machine-written session-continuation summaries ("This session is being continued ..."), pasted blocks and very long messages.
Duplicate copies of a message (resumed sessions) are counted once.
Redaction happens BEFORE any statistic or quote is written. A message that contains a credential anywhere (quoted or unquoted key/value
fields such as password, secret, token, api key, authorization; URL user:password@host; HTTP Basic or Bearer values; PEM or SSH key blocks;
known provider token shapes) is DROPPED WHOLE, not partly masked, and counted as dropped_credential. Email addresses are masked as
[redacted-email]. The script prints totals and file paths, never message text.

Outputs:
  research/messages.jsonl  one record per kept message: project, source_file, line, full timestamp, redacted full text (not shortened)
  research/digest.json, research/digest.md  totals and filtering counts, most frequent whole-message phrases, repeated typos, activity by
                           weekday and hour (local time), by project, longest and shortest messages, a sample of dated quotes.
                           Every shortened quotation is marked "excerpt" and points back to its record in messages.jsonl.
Paths: the project folder is ROAST_PROJECT_DIR if set, else the current folder; --out is relative to it.

Usage:
  python collect_sessions.py                          Claude Code sessions only
  python collect_sessions.py --root D:/other/logs     add another folder (repeatable)
  python collect_sessions.py --no-default --root X    only the given folders
  python collect_sessions.py --since 2025-01-01 --out research --max-chars 1500 --samples 25"""
import os, re, sys, json, glob, argparse, random, datetime, collections
from roots import project_root, under_root

# ----------------------------------------------------------------------------- redaction
# Each entry is (label, compiled regex). A hit anywhere in a message drops the whole message.
_KEYNAME = (r'(?:passwords?|passwd|passcode|passphrase|pwd|secrets?|client[_-]?secret|'
            r'(?:access|refresh|auth|api|bearer|session|bot|private|id)[_ -]?token|token|api[_ -]?key|apikey|x-api-key|authorization|private[_ -]?key|credentials?)')
CREDENTIAL_PATTERNS = [
    ('pem_block', re.compile(r'-----BEGIN [A-Z0-9 ]{3,}-----')),
    ('ssh_key', re.compile(r'\b(?:ssh-(?:rsa|ed25519|dss)|ecdsa-sha2-nistp\d+)\s+AAAA[0-9A-Za-z+/=]{20,}')),
    # key: value in JSON ("password": "x"), YAML (password: x), env (PASSWORD=x), shell (export API_KEY="x"), header (Authorization: ...)
    ('credential_field', re.compile(r'(?i)' + _KEYNAME + r'''["']?\s*(?:=>|[:=])\s*(?:(["'])(?:(?!\1)[^\r\n]){3,}\1|["']?[^\s"',;)}\]]{3,})''')),   # a quoted value may hold spaces
    ('credential_sentence', re.compile(r'(?i)\b(?:passwords?|passwd|passcode|passphrase|api[_ -]?key|token)\s+(?:is|was|=)\s+["\']?\S{3,}')),
    ('url_userinfo', re.compile(r'\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@')),
    ('url_token_userinfo', re.compile(r'\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]{20,}@')),
    ('url_query_secret', re.compile(r'(?i)[?&](?:key|token|sig|signature|password|passwd|access_token|api_key|apikey|secret|client_secret)=[^&\s]{3,}')),
    ('curl_user', re.compile(r'(?:^|\s)(?:-u|--user)\s+[^\s:]+:\S+')),
    ('bearer_value', re.compile(r'\bBearer\s+(?=[A-Za-z0-9._~+/=-]*[0-9._~+/=-])[A-Za-z0-9._~+/=-]{12,}')),
    ('basic_value', re.compile(r'\bBasic\s+(?=[A-Za-z0-9+/=]+[A-Z0-9+/=])[A-Za-z0-9+/]{12,}={0,2}')),
    ('openai_anthropic_key', re.compile(r'\bsk-(?:proj-|svcacct-|admin-|ant-[A-Za-z0-9]{2,8}-)?[A-Za-z0-9_-]{16,}')),
    ('sk_underscore_key', re.compile(r'\b[sr]k_(?:live_|test_)?[A-Za-z0-9]{16,}')),
    ('stripe_publishable', re.compile(r'\bpk_(?:live|test)_[A-Za-z0-9]{16,}')),
    ('github_token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})')),
    ('gitlab_token', re.compile(r'\bglpat-[A-Za-z0-9_-]{16,}')),
    ('slack_token', re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}')),
    ('aws_key_id', re.compile(r'\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}\b')),
    ('google_key', re.compile(r'\b(?:AIza[A-Za-z0-9_-]{35}|ya29\.[A-Za-z0-9_-]{20,})')),
    ('huggingface_token', re.compile(r'\bhf_[A-Za-z0-9]{30,}')),
    ('npm_token', re.compile(r'\bnpm_[A-Za-z0-9]{30,}')),
    ('pypi_token', re.compile(r'\bpypi-[A-Za-z0-9_-]{40,}')),
    ('replicate_token', re.compile(r'\br8_[A-Za-z0-9]{30,}')),
    ('fal_key', re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b')),
    ('sendgrid_key', re.compile(r'\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}')),
    ('telegram_bot_token', re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')),
    ('jwt', re.compile(r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}')),
    ('long_hex', re.compile(r'\b[0-9a-fA-F]{32,}\b')),
    ('long_mixed_secret', re.compile(r'\b(?=[A-Za-z0-9+/_=-]*[0-9])(?=[A-Za-z0-9+/_=-]*[a-z])(?=[A-Za-z0-9+/_=-]*[A-Z])[A-Za-z0-9+/_=-]{32,}')),
]
EMAIL = re.compile(r'(?<![/\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')      # not the user part of ssh://git@host URLs
MARKER = re.compile(r'\[redacted-[a-z]+\]')

def credential_hit(text):
    """label of the first credential pattern found in the text, or None"""
    for label, rx in CREDENTIAL_PATTERNS:
        if rx.search(text): return label
    return None

def redact_message(text):
    """(clean_text, None) for a safe message (emails masked), or (None, label) if it holds a credential and must be dropped whole"""
    label = credential_hit(text)
    if label: return None, label
    return EMAIL.sub('[redacted-email]', text), None

# ----------------------------------------------------------------------------- reading records
SKIP_START = ('<', '[Request interrupted', 'Caveat:', '# AGENTS.md', 'Base directory for this skill', '[Image', 'Warmup')
CONTINUATION = 'this session is being continued'

def text_of(content):
    """the typed text of a message `content` (str or list of blocks), or None if it carries tool results / no text"""
    if isinstance(content, str): return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict): continue
            t = b.get('type')
            if t in ('tool_result', 'tool_use', 'image', 'input_image'): return None
            if t in ('text', 'input_text') and isinstance(b.get('text'), str): parts.append(b['text'])
        return '\n'.join(parts) if parts else None
    return None

def classify(rec, max_chars):
    """(kind, text, timestamp). kind: 'ok' (typed by the human), 'machine' (not typed by hand), 'pasted' (too long or a pasted block), 'not_user'"""
    if not isinstance(rec, dict): return 'not_user', None, None
    ts = rec.get('timestamp') or (rec.get('payload') or {}).get('timestamp')
    msg = None
    if rec.get('type') == 'user' and isinstance(rec.get('message'), dict) and rec['message'].get('role') == 'user': msg = rec['message'].get('content')
    elif rec.get('role') == 'user' and 'content' in rec: msg = rec['content']
    elif isinstance(rec.get('payload'), dict) and rec['payload'].get('role') == 'user' and rec['payload'].get('type') == 'message': msg = rec['payload'].get('content')
    elif rec.get('role') == 'user' and isinstance(rec.get('text'), str): msg = rec['text']
    if msg is None: return 'not_user', None, None
    if rec.get('isMeta') or rec.get('isSidechain') or rec.get('isCompactSummary') or rec.get('toolUseResult') is not None: return 'machine', None, ts
    t = text_of(msg)
    if t is None: return 'machine', None, ts                   # tool results and image-only blocks
    t = t.strip()
    if not t: return 'machine', None, ts
    if t.startswith(SKIP_START) or t.lower().startswith(CONTINUATION): return 'machine', None, ts
    if len(t) > max_chars or t.count('\n') > 25 or '[Pasted' in t or '```' in t or '<system-reminder' in t: return 'pasted', None, ts
    return 'ok', t, ts

def parse_ts(ts, fallback):
    if isinstance(ts, (int, float)):
        try: return datetime.datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts).astimezone()
        except Exception: return fallback
    if isinstance(ts, str):
        try: return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()
        except Exception: pass
    return fallback

def iter_files(roots):
    """yields (root_label, root_dir, file) for every *.jsonl under the roots (or a root that is itself a file), each real file once"""
    seen = set()
    for label, r in roots:
        r = os.path.expanduser(r)
        pats = [r] if os.path.isfile(r) else [os.path.join(r, '**', '*.jsonl')]
        base = os.path.dirname(r) if os.path.isfile(r) else r
        for pat in pats:
            for f in sorted(glob.glob(pat, recursive=True)):
                rp = os.path.realpath(f)
                if rp not in seen and os.path.isfile(rp): seen.add(rp); yield label, base, f

def project_of(root, f):
    parts = os.path.relpath(f, root).split(os.sep)
    return parts[0] if len(parts) > 1 else (os.path.basename(root) or 'root')

# ----------------------------------------------------------------------------- typos
WORD = re.compile(r"[A-Za-z][a-z']{2,}")
def edit1(a, b):
    """True if a and b differ by one insertion, deletion, substitution or adjacent swap"""
    if a == b or abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if len(a) > len(b): a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]: i += 1
    return a[i:] == b[i + 1:]

def find_typos(texts, min_count=3, ratio=6):
    c = collections.Counter(w.lower() for t in texts for w in WORD.findall(MARKER.sub(' ', t)))   # redaction markers are not the person's words
    common = [w for w, n in c.items() if n >= max(min_count * 3, 10)]
    by_first = collections.defaultdict(list)
    for w in common: by_first[w[0]].append(w)
    out = []
    for w, n in c.items():
        if n < min_count or w in common: continue
        best = None
        for g in by_first.get(w[0], []):
            if edit1(w, g) and c[g] >= n * ratio and (best is None or c[g] > c[best]): best = g
        if best: out.append({'typed': w, 'times': n, 'meant_probably': best, 'meant_times': c[best]})
    return sorted(out, key=lambda x: -x['times'])[:25]

# ----------------------------------------------------------------------------- main
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
def clip(s, n=300):
    """(text, was_shortened): whitespace-normalised and cut to n characters"""
    s = ' '.join(s.split())
    return (s, False) if len(s) <= n else (s[:n - 3] + '...', True)

def quote(m, n):
    t, cut = clip(m['text'], n)
    return {'date': m['when'].date().isoformat(), 'time': m['when'].strftime('%H:%M'), 'timestamp': m['timestamp'], 'project': m['project'],
            'source_file': m['source_file'], 'line': m['line'], 'chars': m['chars'], 'text': t, 'excerpt': cut}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', action='append', default=[], help='extra folder (or .jsonl file) of session logs; repeatable')
    ap.add_argument('--no-default', action='store_true', help='skip ~/.claude/projects')
    ap.add_argument('--out', default='research', help='output folder (default research)')
    ap.add_argument('--since', default=None, help='only messages on or after YYYY-MM-DD')
    ap.add_argument('--max-chars', type=int, default=2000, help='skip messages longer than this, treated as pasted (default 2000)')
    ap.add_argument('--samples', type=int, default=20, help='dated quotes in the sample (default 20)')
    ap.add_argument('--top', type=int, default=20, help='rows in the frequent-phrase table (default 20)')
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    roots = ([] if a.no_default else [('claude-code', os.path.join('~', '.claude', 'projects'))]) + \
            [(os.path.basename(os.path.normpath(r)) or 'root', r) for r in a.root]
    since = datetime.datetime.fromisoformat(a.since).astimezone() if a.since else None

    msgs = []; seen = set(); nfiles = 0; skipped_files = 0
    cnt = collections.Counter()
    for label, base, f in iter_files(roots):
        nfiles += 1
        try: fb = datetime.datetime.fromtimestamp(os.path.getmtime(f)).astimezone()
        except OSError: fb = None
        proj = project_of(base, f); srcname = label + '/' + os.path.relpath(f, base).replace(os.sep, '/')
        try:
            with open(f, encoding='utf-8', errors='replace') as fh:
                for ln, line in enumerate(fh, 1):
                    if not line.strip().startswith('{'): continue
                    try: rec = json.loads(line)
                    except ValueError: continue
                    kind, text, ts = classify(rec, a.max_chars)
                    if kind == 'not_user': continue
                    if kind == 'machine': cnt['machine_generated_or_tool'] += 1; continue
                    if kind == 'pasted': cnt['pasted_or_too_long'] += 1; continue
                    clean, why = redact_message(text)
                    if clean is None: cnt['dropped_credential'] += 1; continue
                    when = parse_ts(ts, fb)
                    if when is None or (since and when < since): cnt['outside_date_range'] += 1; continue
                    key = (when.isoformat(timespec='seconds'), clean)
                    if key in seen: cnt['duplicates'] += 1; continue
                    seen.add(key)
                    msgs.append({'when': when, 'timestamp': when.isoformat(timespec='seconds'), 'project': proj, 'source_file': srcname,
                                 'line': ln, 'text': clean, 'chars': len(clean)})
        except OSError:
            skipped_files += 1
    unsupported = 0
    for label, r in roots:
        r = os.path.expanduser(r)
        if os.path.isdir(r): unsupported += len(glob.glob(os.path.join(r, '**', '*.json'), recursive=True))
    if not msgs:
        raise SystemExit('no human-typed messages found in %d file(s) under: %s (counted: %s; unsupported .json files seen: %d)' % (
            nfiles, ', '.join(r for _, r in roots) or '(none)', dict(cnt), unsupported))
    msgs.sort(key=lambda m: m['when'])
    texts = [m['text'] for m in msgs]
    words = [len(t.split()) for t in texts]
    norm = collections.Counter(); orig = collections.defaultdict(collections.Counter)
    for t in texts:
        k = re.sub(r'\s+', ' ', t.lower()).strip(' .!?'); norm[k] += 1; orig[k][' '.join(t.split())] += 1
    phrases = []
    for p, n in norm.most_common(a.top):
        if n > 1:
            shown, cut = clip(orig[p].most_common(1)[0][0], 120)       # most common original spelling and case
            phrases.append({'phrase': shown, 'count': n, 'excerpt': cut})
    wd = collections.Counter(m['when'].weekday() for m in msgs); hr = collections.Counter(m['when'].hour for m in msgs)
    days = collections.Counter(m['when'].date().isoformat() for m in msgs)
    by_project = collections.Counter(m['project'] for m in msgs)
    by_len = sorted(msgs, key=lambda m: m['chars'])
    rnd = random.Random(a.seed)
    sample = sorted(rnd.sample(msgs, min(a.samples, len(msgs))), key=lambda m: m['when'])
    digest = {
        'totals': {'messages': len(msgs), 'files_scanned': nfiles, 'files_unreadable': skipped_files, 'active_days': len(days),
                   'first': msgs[0]['when'].isoformat(timespec='minutes'), 'last': msgs[-1]['when'].isoformat(timespec='minutes'),
                   'words': sum(words), 'mean_words': round(sum(words) / len(words), 1), 'median_words': sorted(words)[len(words) // 2],
                   'one_word_messages': sum(1 for w in words if w == 1), 'questions': sum(1 for t in texts if t.endswith('?')),
                   'all_caps_messages': sum(1 for t in texts if len(t) > 3 and t.isupper()),
                   'busiest_day': max(days.items(), key=lambda kv: kv[1]) if days else None},
        'filtering': {'kept': len(msgs), 'dropped_credential': cnt['dropped_credential'], 'machine_generated_or_tool': cnt['machine_generated_or_tool'],
                      'pasted_or_too_long': cnt['pasted_or_too_long'], 'duplicates': cnt['duplicates'], 'outside_date_range': cnt['outside_date_range'],
                      'unsupported_json_files_seen_not_read': unsupported},
        'by_project': dict(by_project.most_common(30)),
        'frequent_whole_message_phrases': phrases,
        'repeated_typos': find_typos(texts),
        'by_weekday': {DAYS[i]: wd.get(i, 0) for i in range(7)},
        'by_hour': {'%02d' % h: hr.get(h, 0) for h in range(24)},
        'longest': [quote(m, 300) for m in by_len[-5:][::-1]],
        'shortest': [quote(m, 300) for m in [x for x in by_len if x['chars'] > 0][:5]],
        'sample_quotes': [quote(m, 240) for m in sample],
        'note': 'Best-effort redaction. Inspect locally before sharing; these are a real person\'s words. Quotes marked excerpt are shortened: full text is in messages.jsonl.',
    }
    out = under_root(a.out, project_root()); os.makedirs(out, exist_ok=True)
    pj, pm, pr = os.path.join(out, 'digest.json'), os.path.join(out, 'digest.md'), os.path.join(out, 'messages.jsonl')
    with open(pr, 'w', encoding='utf-8') as fh:
        for m in msgs:
            fh.write(json.dumps({'project': m['project'], 'source_file': m['source_file'], 'line': m['line'], 'timestamp': m['timestamp'],
                                 'chars': m['chars'], 'text': m['text']}, ensure_ascii=False) + '\n')
    with open(pj, 'w', encoding='utf-8') as fh: json.dump(digest, fh, indent=1, ensure_ascii=False)
    T = digest['totals']; F = digest['filtering']
    def q(x): return '- %s %s [%s, %s line %d]%s: %s' % (x['date'], x['time'], x['project'], x['source_file'], x['line'], ' (excerpt)' if x['excerpt'] else '', x['text'])
    L = ['# Typing digest', '', '_Best-effort redaction. Inspect locally before sharing or using; these are a real person\'s words. Quotes marked excerpt are shortened; full text and its source are in messages.jsonl._', '',
        '## Totals', '', '- %d messages typed by hand across %d active days (%s to %s), from %d files' % (T['messages'], T['active_days'], T['first'], T['last'], T['files_scanned']),
        '- %d words; mean %.1f, median %d per message; %d one-word messages; %d questions; %d all-caps messages' % (T['words'], T['mean_words'], T['median_words'], T['one_word_messages'], T['questions'], T['all_caps_messages']),
        '- busiest day: %s' % (('%s (%d messages)' % T['busiest_day']) if T['busiest_day'] else 'n/a'), '',
        '## What was filtered out', '',
        '- dropped whole because they held a credential: %d' % F['dropped_credential'],
        '- machine-generated or tool records (incl. session-continuation summaries): %d' % F['machine_generated_or_tool'],
        '- pasted blocks or too long: %d; duplicates: %d; outside date range: %d' % (F['pasted_or_too_long'], F['duplicates'], F['outside_date_range']),
        '- unsupported .json files seen under --root folders and not read: %d' % F['unsupported_json_files_seen_not_read'], '',
        '## By project', ''] + ['- %s: %d' % (k, v) for k, v in digest['by_project'].items()] + ['', '## Most frequent whole-message phrases', '']
    L += ['- "%s"%s x %d' % (p['phrase'], ' (excerpt)' if p['excerpt'] else '', p['count']) for p in phrases] or ['- none repeated']
    L += ['', '## Repeated typos (rare word one edit away from a common word)', '']
    L += ['- "%s" x %d (probably "%s", typed correctly %d times)' % (t['typed'], t['times'], t['meant_probably'], t['meant_times']) for t in digest['repeated_typos']] or ['- none detected']
    L += ['', '## By weekday', ''] + ['- %s: %d' % (d, n) for d, n in digest['by_weekday'].items()]
    L += ['', '## By hour (local)', ''] + ['- %s:00  %s %d' % (h, '#' * int(40 * n / max(hr.values())), n) for h, n in digest['by_hour'].items()]
    L += ['', '## Longest messages', ''] + [q(x) + ' (%d chars)' % x['chars'] for x in digest['longest']]
    L += ['', '## Shortest messages', ''] + [q(x) for x in digest['shortest']]
    L += ['', '## Sample of dated quotes', ''] + [q(x) for x in digest['sample_quotes']]
    with open(pm, 'w', encoding='utf-8') as fh: fh.write('\n'.join(L) + '\n')
    print('%d human messages from %d files, %d active days -> %s, %s, %s' % (T['messages'], nfiles, T['active_days'], pj, pm, pr))
    print('filtered: %s' % ', '.join('%s %d' % (k, v) for k, v in F.items() if k != 'kept'))
    print('Redaction is best-effort: inspect %s locally before sharing anything in it.' % out)

if __name__ == '__main__':
    main()
