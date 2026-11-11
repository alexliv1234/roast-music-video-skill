"""Synthetic tests for collect_sessions.py redaction and filtering. Plain asserts; run with:  python tests/test_redaction.py
Every credential below is made up and assembled at run time so no real-looking secret sits in the source.
Redaction is best-effort: these tests prove the listed formats are caught and ordinary words are not, nothing more."""
import os, sys, json, tempfile, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
import collect_sessions as cs

checks = 0
def check(cond, msg):
    global checks
    checks += 1
    assert cond, msg

A = 'abcdefghijklmnopqrstuvwxyz'
N = '0123456789'
fake_jwt = 'eyJ' + 'hbGciOiJIUzI1NiJ9' + '.' + 'eyJzdWIiOiJ0ZXN0In0' + '.' + 'c2lnbmF0dXJlMTIz'

MUST_DROP = {
    'json quoted password': '{"password": "rosebud!"}',
    'json quoted token': '{"access_token": "zzz-123-yyy"}',
    'yaml password': 'db:\n  password: rosebud\n  host: x',
    'env password': 'DB_PASSWORD=rosebud',
    'env api key export': 'export OPENAI_API_KEY="' + 'q' * 3 + N + '"',
    'secret field': 'client_secret: ' + A[:12],
    'json quoted passphrase with spaces': '{"password": "my dog has fleas"}',
    'password sentence': 'my password is hunter22 ok',
    'url userinfo': 'postgresql://sam:simplePass!@localhost/db',
    'url token userinfo': 'https://' + ('a1' * 12) + '@example.test/repo.git',
    'url query secret': 'GET /v1/items?api_key=' + A[:10] + N[:4],
    'curl user': 'curl -u sam:simplePass https://example.test/',
    'basic header': 'Authorization: Basic dXNlcjpwYXNz',
    'bearer header': 'Authorization: Bearer ' + A[:16] + N[:4],
    'bearer value': 'use Bearer ' + A[:8] + N[:8] + ' for the call',
    'pem block': 'here\n-----BEGIN ' + 'PRIVATE KEY-----\nMIIBVgIBADANBg\n-----END ' + 'PRIVATE KEY-----\nthanks',
    'pem header only': '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----',
    'ssh public key line': 'ssh-ed25519 ' + 'AAAA' + A + N + ' me@laptop',
    'openai style key': 'sk-' + 'proj-' + A[:20] + N,
    'sk-short style': 'sk-' + A[:16],
    'sk underscore live': 'sk_' + 'live_' + A[:24],
    'github classic': 'ghp' + '_' + (A + N)[:36],
    'github fine grained': 'github_pat_' + (A + N)[:30] + '_' + A[:10],
    'gitlab': 'glpat' + '-' + A[:20],
    'slack': 'xoxb' + '-' + N + '-' + A[:12],
    'aws key id': 'AKIA' + 'ABCDEFGHIJKLMNOP',
    'google api key': 'AIza' + (A + N)[:35],
    'huggingface': 'hf' + '_' + (A + N)[:34],
    'npm': 'npm' + '_' + (A + N)[:36],
    'pypi': 'pypi' + '-' + (A + N + A)[:50],
    'replicate': 'r8' + '_' + (A + N)[:36],
    'fal': '12345678-1234-1234-1234-123456789abc:' + '0123456789abcdef' * 2,
    'sendgrid': 'SG' + '.' + A[:20] + '.' + A[:20],
    'telegram bot': '12345678' + ':' + (A + N)[:35],
    'jwt': fake_jwt,
    'long hex': '0123456789abcdef' * 3,
    'long mixed secret': 'Zk3' + A[:15] + 'Q9' + A.upper()[:20],
}

MUST_KEEP = {
    'skateboarding': 'I went skateboarding with sketchbooks all day',
    'ask-style words': 'task-oriented skeleton ask-me-anything skylight',
    'ordinary basic': 'Basic understanding of password managers is useful',
    'plural tokens colon': 'tokens: 1000 and max_tokens=1000',
    'token budget': 'the token budget is tight today',
    'bearer noun': 'Bearer of bad news',
    'github word': 'github and gitlab are fine, so is npm install',
    'hf and r8 words': 'hf radio and r8 engine, hfhf',
    'short secret word': 'tell no one the secret',
    'secret in prose': 'the secret is making it punchier',
    'plain url': 'see https://example.test/path?page=2&sort=name',
    'ssh url no password': 'git clone ssh://git@example.test/team/repo.git',
    'long slug lowercase': 'my-very-long-lowercase-project-name-with-many-words-in-it',
    'bypass': 'bypass: skip the check, compass: north',
}

def main():
    for name, text in MUST_DROP.items():
        clean, why = cs.redact_message(text)
        check(clean is None and why, 'should drop whole message: %s -> %r' % (name, clean))
    for name, text in MUST_KEEP.items():
        clean, why = cs.redact_message(text)
        check(clean == text and why is None, 'should keep untouched: %s -> %r (%s)' % (name, clean, why))
    clean, _ = cs.redact_message('mail sam@example.test about skateboarding')
    check(clean == 'mail [redacted-email] about skateboarding', 'email masked, rest intact: %r' % clean)
    clean, why = cs.redact_message('line one is fine\npassword: rosebud\nline three is fine')
    check(clean is None, 'a credential line inside a longer message drops the whole message')

    # classification
    kind, _, _ = cs.classify({'type': 'user', 'timestamp': '2025-01-01T00:00:00Z', 'message': {'role': 'user', 'content': 'This session is being continued from a previous conversation...'}}, 2000)
    check(kind == 'machine', 'continuation summary is machine-generated')
    kind, text, _ = cs.classify({'type': 'user', 'timestamp': '2025-01-01T00:00:00Z', 'message': {'role': 'user', 'content': 'hello there'}}, 2000)
    check(kind == 'ok' and text == 'hello there', 'plain typed message kept')
    kind, _, _ = cs.classify({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'x'}]}}, 2000)
    check(kind == 'machine', 'tool result is not typed by hand')

    # typo statistics ignore redaction markers
    typos = cs.find_typos(['[redacted-email] hello'] * 40)
    check(all('redacted' not in t['typed'] and t['typed'] != 'email' for t in typos), 'markers are not counted as words')

    # end to end on a temporary folder: dropped count, per-message records, no secret in any output
    secret = 'sk-' + 'proj-' + A[:20] + N
    with tempfile.TemporaryDirectory() as d:
        logs = os.path.join(d, 'logs', 'projA'); os.makedirs(logs)
        recs = [
            {'type': 'user', 'timestamp': '2025-03-01T09:10:00Z', 'message': {'role': 'user', 'content': 'first plain message'}},
            {'type': 'user', 'timestamp': '2025-03-01T09:11:00Z', 'message': {'role': 'user', 'content': 'use ' + secret + ' for it'}},
            {'type': 'user', 'timestamp': '2025-03-01T09:12:00Z', 'message': {'role': 'user', 'content': 'This session is being continued from an earlier one'}},
            {'type': 'user', 'timestamp': '2025-03-01T09:13:00Z', 'message': {'role': 'user', 'content': 'second plain message'}},
        ]
        with open(os.path.join(logs, 's1.jsonl'), 'w', encoding='utf-8') as fh:
            for r in recs: fh.write(json.dumps(r) + '\n')
        out = os.path.join(d, 'research')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'collect_sessions.py'), '--no-default', '--root', os.path.join(d, 'logs'), '--out', out],
                           capture_output=True, text=True, encoding='utf-8', cwd=d, env=dict(os.environ, ROAST_PROJECT_DIR=d))
        check(r.returncode == 0, 'collector ran: ' + r.stderr[-400:])
        dig = json.load(open(os.path.join(out, 'digest.json'), encoding='utf-8'))
        check(dig['totals']['messages'] == 2, 'two messages kept, got %s' % dig['totals']['messages'])
        check(dig['filtering']['dropped_credential'] == 1, 'one dropped for credential')
        check(dig['filtering']['machine_generated_or_tool'] == 1, 'one machine-generated summary excluded')
        lines = [json.loads(x) for x in open(os.path.join(out, 'messages.jsonl'), encoding='utf-8')]
        check([m['line'] for m in lines] == [1, 4], 'records carry their source line numbers: %s' % [m['line'] for m in lines])
        check(all(m['project'] == 'projA' and m['timestamp'].startswith('2025-03-01') and m['source_file'].endswith('s1.jsonl') for m in lines), 'records carry project, source file and full timestamp')
        for fn in ('digest.json', 'digest.md', 'messages.jsonl'):
            check(secret not in open(os.path.join(out, fn), encoding='utf-8').read(), 'secret absent from ' + fn)
        check(secret not in r.stdout + r.stderr, 'secret absent from console output')

    print('test_redaction: %d checks passed (%d must-drop formats, %d must-keep phrases)' % (checks, len(MUST_DROP), len(MUST_KEEP)))

if __name__ == '__main__':
    main()
