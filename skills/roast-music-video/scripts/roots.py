"""roots.py : the one place that decides which folder is "the project". Standard library only, so light helpers can use it too.

Every script resolves the project root the same way: the folder named by the ROAST_PROJECT_DIR environment variable if it is set,
otherwise the current working directory. project.json, shots.csv, strings.csv, audio/, frames/, footage/, analysis/, research/ and out/
are all looked up under that root unless a setting or flag gives an absolute path."""
import os, json


def project_root():
    return os.path.abspath(os.environ.get('ROAST_PROJECT_DIR') or os.getcwd())


def under_root(p, root=None):
    """absolute path of p: p itself if absolute, else p under the project root"""
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.join(root or project_root(), p)


def raw_project(root=None):
    """project.json as a dict, or {} if there is none (for helpers that work without a project)"""
    p = os.path.join(root or project_root(), 'project.json')
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding='utf-8-sig') as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def out_dir(root=None):
    root = root or project_root()
    return under_root((raw_project(root).get('dirs') or {}).get('out') or 'out', root)


def read_json(p):
    with open(p, encoding='utf-8-sig') as fh:
        return json.load(fh)


def write_json(p, obj, **kw):
    kw.setdefault('indent', 1)
    kw.setdefault('ensure_ascii', False)
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, **kw)
