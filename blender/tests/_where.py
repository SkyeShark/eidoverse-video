"""Where things are, for the Blender edition's tests, so that no file in the repo carries one machine's paths.

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))   # from blender/tests/<area>/
    import _where
    _where.REPO                    # this checkout's root (eido_blender.py, run_blender.sh, eidoverse/)
    _where.main_checkout()         # the checkout that holds the untracked shared folders (node_modules/,
                                   # eidoverse/assets/cache/): $EIDO_MAIN_CHECKOUT if set; else, when this checkout is a
                                   # git worktree, the repository's main worktree; else REPO itself
    _where.blender_cmd(script, *args)   # the command line that runs a script in headless Blender through this
                                        # checkout's run_blender.sh, after $EIDO_GPU_WRAP when that is set
    _where.external('EIDO_X_DIR', 'what it is')   # an input that lives outside the repo, or None (and why)

Inputs that live outside the repo (another project's assets, a folder of reference renders from another engine) never
get a default path here: a test reads them from an environment variable through external() and skips that check, saying
which variable to set, when it is absent.

EIDO_GPU_WRAP is a command prefix for machines where Blender jobs queue for the GPU (a slot script, `nice`, a job
runner), for example `env HEAVY_VRAM_GB=4 bash /path/to/slot.sh 12`. Unset, Blender runs directly.
"""
import os
import shlex
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parents[1]


def main_checkout() -> Path:
    """The checkout holding the untracked shared folders: $EIDO_MAIN_CHECKOUT, else the main worktree of this
    repository when REPO is a linked worktree (its .git is a file "gitdir: <main>/.git/worktrees/<name>"), else REPO."""
    env = os.environ.get('EIDO_MAIN_CHECKOUT')
    if env:
        return Path(env)
    git = REPO / '.git'
    if git.is_file():
        line = git.read_text(encoding='utf-8').strip()
        if line.startswith('gitdir:'):
            gitdir = Path(line.split(':', 1)[1].strip())
            # git 2.48+ can write the gitdir relative to the worktree (worktree.useRelativePaths): join it to REPO,
            # never to the process's working directory; an absolute gitdir stays as it is
            return (REPO / gitdir).resolve().parents[2]
    return REPO


def blender_cmd(script, *args) -> list:
    """The argv that runs `script` in headless Blender through REPO's run_blender.sh (its args after Blender's `--`),
    with $EIDO_GPU_WRAP's words in front when it is set."""
    wrap = shlex.split(os.environ.get('EIDO_GPU_WRAP', ''))
    return wrap + ['bash', str(REPO / 'run_blender.sh'), str(script)] + [str(a) for a in args]


def external(var: str, what: str):
    """An input that lives outside this repo, named by the environment variable `var`: its Path when it exists, else
    None after printing which variable to set, so the caller skips the checks that need it."""
    p = os.environ.get(var)
    if p and Path(p).exists():
        return Path(p)
    print(f'[skip] {what}: set {var} to it' + (f' ({p} does not exist)' if p else ''))
    return None
