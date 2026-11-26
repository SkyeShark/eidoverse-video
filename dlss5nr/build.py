"""dlss5nr/build.py: OpenDLSS-NR's `dlss5vk.exe` with this folder's stream patch, built from a fresh clone.

    python dlss5nr/build.py [--dir DIR]

1. Clones maanHimself/OpenDLSS-NR (MIT) into DIR (default: dlss5nr/opendlss, git-ignored) and checks out the commit
   the patch is made for, 9d08f41 (the pinned full hash is UPSTREAM_COMMIT below).
2. Applies patch/opendlss_stream.diff to its src/main.cpp (the `run --list` and `run --stream` modes) and copies
   patch/shaders/stream_* into its shaders/ (the stream's GPU passes).
3. Runs upstream's own build: scripts/fetch_tools.ps1 (the portable toolchain into DIR/tools: glslang, Vulkan-Headers,
   volk, CMake, Ninja; no Vulkan SDK) and scripts/build.ps1 (every shader, the PTX kernels, DIR/build/dlss5vk.exe).
4. Checks that the exe and the stream shaders were built, and prints the line that runs dlss5nr.py with them.

Running it again reuses the clone (it must be at the pinned commit, with the patch applied or not yet applied);
fetch_tools.ps1 skips what it already fetched. The patch's and shaders' upstream notices are patch/LICENSE and
patch/NOTICE. Nothing here downloads or builds NVIDIA's weights: dlss5nr.py takes a model directory you supply.

Requirements (upstream's): Windows; git; Visual Studio 2022 or later with the C++ x64 toolset (found through
vswhere, or set VCVARS64 to your vcvars64.bat); Python 3 on PATH as `python` (the PTX generators). Running the exe
also needs an NVIDIA Ada (or newer) GPU and a driver exposing VK_KHR_cooperative_matrix, VK_NV_cooperative_matrix2,
VK_EXT_shader_float8 and VK_NV_cuda_kernel_launch.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM_URL = 'https://github.com/maanHimself/OpenDLSS-NR.git'
UPSTREAM_COMMIT = '9d08f4184bbcb9d858e2fb7a7834ec0837a9d2f1'
PATCH = os.path.join(HERE, 'patch', 'opendlss_stream.diff')
SHADERS = os.path.join(HERE, 'patch', 'shaders')
DEFAULT_DIR = os.path.join(HERE, 'opendlss')
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0       # CREATE_NO_WINDOW: no console window for the build's programs
# fetch_tools.ps1 unpacks CMake's release zip (3.31.12) into tools/cmake-unzip with Windows PowerShell's Expand-Archive,
# which stops at Windows' 260-character path limit; that zip's deepest file is 123 characters down
CMAKE_DEPTH = len(os.path.join('', 'tools', 'cmake-unzip', '')) + 123
PATH_LIMIT = 259


def say(*a):
    print('[build]', *a, flush=True)


def run(cmd, cwd=None, check=True, quiet=False):
    """a command without a window; its output relayed to ours line by line unless quiet (then it is returned). (A
    windowless child given no handles of ours writes into a hidden console of its own: hence the pipe.)"""
    if quiet:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, creationflags=NO_WINDOW)
        if check and r.returncode != 0:
            raise SystemExit(f'[build] {" ".join(cmd)} failed ({r.returncode}):\n{r.stdout}{r.stderr}')
        return r
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=NO_WINDOW)
    for line in iter(proc.stdout.readline, b''):
        sys.stdout.write(line.decode('utf-8', 'replace'))
        sys.stdout.flush()
    code = proc.wait()
    if check and code != 0:
        raise SystemExit(f'[build] {" ".join(cmd)} failed ({code})')
    return code


def git(d, *args, **kw):
    return run(['git', '-C', d] + list(args), quiet=True, **kw)


def checkout(d):
    """a clone of upstream at the pinned commit in d"""
    if not os.path.isdir(os.path.join(d, '.git')):
        if os.path.exists(d) and os.listdir(d):
            raise SystemExit(f'[build] {d} exists and is not a git clone: give another --dir')
        say(f'cloning {UPSTREAM_URL} into {d}')
        run(['git', 'clone', UPSTREAM_URL, d])
    head = git(d, 'rev-parse', 'HEAD', check=False).stdout.strip()
    if head != UPSTREAM_COMMIT:
        if git(d, 'status', '--porcelain', '--untracked-files=no').stdout.strip():
            raise SystemExit(f'[build] {d} has local changes and is at {head or "no commit"}, not {UPSTREAM_COMMIT[:7]}')
        if git(d, 'cat-file', '-e', UPSTREAM_COMMIT + '^{commit}', check=False).returncode != 0:
            git(d, 'fetch', 'origin', UPSTREAM_COMMIT)
        git(d, 'checkout', '--quiet', '--detach', UPSTREAM_COMMIT)
    say(f'upstream at {UPSTREAM_COMMIT[:7]}')


def apply_patch(d):
    """the stream patch on src/main.cpp (once) and the stream shaders beside upstream's"""
    if git(d, 'apply', '--reverse', '--check', PATCH, check=False).returncode == 0:
        say('src/main.cpp: the patch is already applied')
    elif git(d, 'apply', '--check', PATCH, check=False).returncode == 0:
        git(d, 'apply', PATCH)
        say('src/main.cpp: patched (run --list, run --stream)')
    else:
        raise SystemExit(f'[build] {PATCH} does not apply to {d}/src/main.cpp: is it edited? '
                         f'(git -C {d} diff src/main.cpp)')
    names = sorted(n for n in os.listdir(SHADERS) if n.startswith('stream_'))
    for n in names:
        shutil.copyfile(os.path.join(SHADERS, n), os.path.join(d, 'shaders', n))
    say(f'shaders: {", ".join(names)}')


def powershell(script, d):
    run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
         os.path.join(d, 'scripts', script)], cwd=d)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dir', default=DEFAULT_DIR, help='the clone and its build (default: %(default)s)')
    args = ap.parse_args()
    if os.name != 'nt':
        raise SystemExit('[build] OpenDLSS-NR builds on Windows only (MSVC, PowerShell scripts)')
    for tool in ('git', 'powershell', 'python'):
        if shutil.which(tool) is None:
            raise SystemExit(f'[build] `{tool}` is not on PATH')
    d = os.path.abspath(args.dir)
    if len(d) + CMAKE_DEPTH > PATH_LIMIT and not os.path.isfile(os.path.join(d, 'tools', 'cmake', 'bin', 'cmake.exe')):
        raise SystemExit(f'[build] {d} is {len(d)} characters long: upstream\'s toolchain fetch unpacks CMake to files '
                         f'{CMAKE_DEPTH} characters below it, past Windows\' {PATH_LIMIT + 1}-character path limit. Give a '
                         f'--dir of at most {PATH_LIMIT - CMAKE_DEPTH} characters (e.g. C:\\opendlss)')
    checkout(d)
    apply_patch(d)
    say('upstream scripts/fetch_tools.ps1 (the toolchain into tools/; skips what is there)')
    powershell('fetch_tools.ps1', d)
    say('upstream scripts/build.ps1 (shaders, PTX kernels, the exe)')
    powershell('build.ps1', d)
    exe = os.path.join(d, 'build', 'dlss5vk.exe')
    missing = [p for p in [exe] + [os.path.join(d, 'build', 'shaders', f'stream_{k}.spv')
                                   for k in ('unpack', 'warp', 'inject', 'composite')] if not os.path.isfile(p)]
    if missing:
        raise SystemExit(f'[build] the build did not produce {missing}')
    say(f'built {exe}')
    default = os.path.normcase(os.path.abspath(DEFAULT_DIR)) == os.path.normcase(d)
    say('run it: python dlss5nr/dlss5nr.py <in.mp4> <out.mp4> --model <your model dir>'
        + ('' if default else f' --exe {exe}') + ' (or set DLSS5VK_MODEL'
        + ('' if default else ' and DLSS5VK_EXE') + ')')


if __name__ == '__main__':
    main()
