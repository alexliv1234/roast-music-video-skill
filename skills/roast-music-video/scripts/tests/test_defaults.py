"""Checks that the shipped defaults pass their own QA minimums and that the numeric validation rejects bad settings.
Run with:  python tests/test_defaults.py     (uses the system fallback fonts; Pillow and numpy needed)"""
import os, sys, json, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
checks = 0

def run(code, project):
    """run python code with a throwaway project folder as the project root; returns the CompletedProcess"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'project.json'), 'w', encoding='utf-8') as fh: json.dump(project, fh)
        env = dict(os.environ, ROAST_PROJECT_DIR=d, PYTHONPATH=SCRIPTS)
        return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, encoding='utf-8', env=env, cwd=d)

def check(cond, msg):
    global checks; checks += 1
    assert cond, msg

def main():
    ex = json.load(open(os.path.join(SCRIPTS, 'project.example.json'), encoding='utf-8'))
    ex['fonts'] = {'display': '', 'body': '', 'mono': ''}            # force the system fallback fonts
    code = ("import common as c, json\n"
            "roles = {'caption_size':'display','tag_size':'display','namecard_name_size':'display','namecard_role_size':'body','bubble_size':'body'}\n"
            "print(json.dumps({k: c.cap_height(r, int(round(c.TX[k]*c.S))) for k, r in roles.items()} | {'min': c.MIN_CAP}))")
    r = run(code, ex)
    check(r.returncode == 0, r.stderr[-500:])
    caps = json.loads(r.stdout.strip().splitlines()[-1])
    mn = caps.pop('min')
    check(all(v >= mn for v in caps.values()), 'default text sizes below the %s px cap-height minimum: %s' % (mn, caps))
    # bad numbers are rejected with a message, not a traceback from a division
    for key, bad in (('fps', 0), ('duration', 0), ('size', [1281, 720]), ('retime', 0), ('safe_margin', 0.6), ('min_hold', -1)):
        p = json.loads(json.dumps(ex)); p[key] = bad
        r = run('import common', p)
        check(r.returncode != 0 and 'invalid settings' in r.stderr + r.stdout, 'setting %s=%r should be rejected: %s' % (key, bad, r.stderr[-300:]))
    p = json.loads(json.dumps(ex)); p['providers']['video']['mode'] = 'sometimes'
    r = run('import common', p)
    check(r.returncode != 0 and 'mode' in r.stderr, 'unknown provider mode rejected')
    p = json.loads(json.dumps(ex)); p['providers']['video']['mode'] = 'none'
    check(run('import common', p).returncode == 0, 'provider mode none allowed')
    print('test_defaults: %d checks passed (caps %s, min %s px)' % (checks, caps, mn))

if __name__ == '__main__':
    main()
