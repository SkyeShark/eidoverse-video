"""tests/xr/test_xr_quest.py: eidoverse/xr/quest.py, every command, against a stand-in adb. System Python, no GPU:

    python blender/tests/xr/test_xr_quest.py

quest.py carries over to the Blender edition unchanged (it opens a page in the Quest browser, keeps the headset awake,
pulls its recordings; nothing in it touches a renderer). This machine has no adb and no headset, so the test imports
quest.py and answers its adb calls with a recording stand-in that behaves like a Quest 3 on USB: `adb devices`, the
wlan0 address, `dumpsys power`, `tcpip` + `connect` (after which the headset is also listed on Wi-Fi), `am start`,
`am force-stop`, `am broadcast`, `ls -t` of the recordings folders and `pull` (which writes a real small H.264 video
when ffmpeg is on PATH, so `--sheet` runs the repo's contact_sheet.py on it for real). Checked: the exact adb commands
each subcommand sends, its printed answer, the Wi-Fi address file it keeps, and the files `pull` brings back.
"""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, 'out', 'quest')
QUEST = os.path.join(WORKTREE, 'eidoverse', 'xr', 'quest.py')
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


USB, IP = '2G0YC5ZG8F0123', '192.168.1.57'
VIDEOS = ['com.oculus.vrshell-20261107-101530.mp4', 'com.oculus.vrshell-20261106-221002.mp4']
PHOTOS = ['com.oculus.vrshell-20261107-101601.jpg']


class StandInADB:
    """Answers quest.py's adb calls like one Quest 3 plugged in over USB (and, after `wireless`, on Wi-Fi too)."""

    def __init__(self, video_src=None):
        self.calls, self.wifi, self.awake, self.video_src = [], False, 'Awake', video_src
        self.real_run = subprocess.run
        self.sheets = []

    def __call__(self, cmd, *a, **kw):
        if cmd and cmd[0] == sys.executable and any(str(x).endswith('contact_sheet.py') for x in cmd):
            self.sheets.append(list(cmd))                        # --sheet: run the repo's contact sheet for real
            return self.real_run(cmd, *a, **kw)
        if not cmd or cmd[0] != 'adb':
            return self.real_run(cmd, *a, **kw)
        self.calls.append(list(cmd[1:]))
        args = list(cmd[1:])
        if args[:1] == ['-s']:                                   # the device it names: there is one
            args = args[2:]
        out, rc = '', 0
        if args == ['devices']:
            rows = [f'{USB}\tdevice'] + ([f'{IP}:5555\tdevice'] if self.wifi else [])
            out = 'List of devices attached\n' + '\n'.join(rows) + '\n\n'
        elif args[:2] == ['connect', f'{IP}:5555']:
            self.wifi = True
            out = f'connected to {IP}:5555\n'
        elif args[:1] == ['tcpip']:
            out = f'restarting in TCP mode port: {args[1]}\n'
        elif args[:1] == ['shell'] and args[1:3] == ['ip', '-f']:
            out = (f'25: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 3000\n'
                   f'    inet {IP}/24 brd 192.168.1.255 scope global wlan0\n')
        elif args[:3] == ['shell', 'dumpsys', 'power']:
            out = f'POWER MANAGER (dumpsys power)\n  mWakefulness={self.awake}\n  mWakefulnessChanging=false\n'
        elif args[:3] == ['shell', 'am', 'start']:
            out = 'Starting: Intent { act=android.intent.action.VIEW }\n'
        elif args[:3] == ['shell', 'am', 'force-stop'] or args[:3] == ['shell', 'am', 'broadcast']:
            out = 'Broadcast completed: result=0\n' if args[2] == 'broadcast' else ''
        elif args[:3] == ['shell', 'ls', '-t']:
            folder = args[3]
            out = '\n'.join(VIDEOS if folder.endswith('VideoShots') else PHOTOS) + '\n'
        elif args[:1] == ['pull']:
            src, dst = args[1], args[2]
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if dst.endswith('.mp4') and self.video_src:
                shutil.copyfile(self.video_src, dst)
            else:
                with open(dst, 'wb') as f:
                    f.write(b'\xff\xd8\xff\xe0' + b'\0' * 2048)
            out = f'{src}: 1 file pulled.\n'
        else:
            out, rc = f'stand-in adb: unknown {args}', 1
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr='' if rc == 0 else out)


def load_quest():
    spec = importlib.util.spec_from_file_location('eido_xr_quest', QUEST)
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True       # (no __pycache__ left in the kit's folder)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


def run(mod, adb, argv):
    """quest.py's main() with argv, the stand-in answering adb; returns (exit code, printed text)."""
    adb.calls.clear()
    buf = io.StringIO()
    keep_argv, keep_run, keep_sleep = sys.argv, mod.subprocess.run, mod.time.sleep
    sys.argv = ['quest.py'] + argv
    mod.subprocess.run = adb
    mod.time.sleep = lambda s: None
    rc = 0
    try:
        with contextlib.redirect_stdout(buf):
            mod.main()
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if e.code not in (None, 0) and not isinstance(e.code, int):
            buf.write(str(e.code))
    finally:
        sys.argv, mod.subprocess.run, mod.time.sleep = keep_argv, keep_run, keep_sleep
    return rc, buf.getvalue()


def tiny_video(path):
    """A real 6 s H.264 clip (ffmpeg's test pattern) for `pull --sheet`; None without ffmpeg."""
    ff = shutil.which('ffmpeg')
    if not ff:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = subprocess.run([ff, '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=24', '-t', '6',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path], capture_output=True, text=True)
    return path if r.returncode == 0 and os.path.exists(path) else None


shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
q = load_quest()
q.LAST = os.path.join(OUT, '.quest_address')          # (quest.py keeps it in <repo>/work/; the test keeps it in out/)
src = tiny_video(os.path.join(OUT, '_source', 'recording.mp4'))
adb = StandInADB(video_src=src)

# status: the USB headset, awake, its Wi-Fi address
rc, out = run(q, adb, ['status'])
check('status: lists the headset (USB), awake, with its wlan address', rc == 0 and f'{USB}  USB  device  Awake  wlan {IP}' in out,
      out.strip())
check('status: asks adb for devices, dumpsys power and the wlan0 address',
      ['devices'] in adb.calls and ['-s', USB, 'shell', 'dumpsys', 'power'] in adb.calls
      and ['-s', USB, 'shell', 'ip', '-f', 'inet', 'addr', 'show', 'wlan0'] in adb.calls, adb.calls)

# wireless: tcpip 5555 over USB, connect to ip:5555, remember the address
rc, out = run(q, adb, ['wireless'])
check('wireless: tcpip 5555 on the USB headset, then connect to its Wi-Fi address',
      rc == 0 and ['-s', USB, 'tcpip', '5555'] in adb.calls and ['connect', f'{IP}:5555'] in adb.calls, adb.calls)
saved = open(q.LAST).read().strip() if os.path.exists(q.LAST) else None
check('wireless: keeps the address for the next run (quest.LAST)', saved == f'{IP}:5555', saved)
rc, out = run(q, adb, ['wireless'])
check('wireless again: the USB device is preferred, so it re-arms Wi-Fi (no duplicate address file)',
      rc == 0 and open(q.LAST).read().strip() == f'{IP}:5555', out.strip().splitlines()[-1:] if out else out)

# open: the exported bundle's page in the Quest browser; --fresh force-stops the browser first
url = 'https://10.0.0.182:8892/blender/tests/xr/out/city/vr/index.html'
rc, out = run(q, adb, ['open', url])
check('open: am start VIEW <url> in com.oculus.browser', rc == 0 and any(
    c[-7:] == ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url, 'com.oculus.browser'] for c in adb.calls)
      and 'put the headset on and press ENTER VR' in out, out.strip())
check('open without --fresh does not close the browser', not any('force-stop' in c for c in adb.calls), adb.calls)
rc, out = run(q, adb, ['open', '--fresh', url])
i_stop = next((i for i, c in enumerate(adb.calls) if 'force-stop' in c), -1)
i_start = next((i for i, c in enumerate(adb.calls) if 'start' in c and 'am' in c), -1)
check('open --fresh: force-stops com.oculus.browser, then opens the page', rc == 0 and 0 <= i_stop < i_start
      and adb.calls[i_stop][-1] == 'com.oculus.browser', adb.calls)

# awake: the proximity broadcast
rc, out = run(q, adb, ['awake'])
check('awake: broadcasts com.oculus.vrpowermanager.prox_close', rc == 0 and any(
    c[-4:] == ['am', 'broadcast', '-a', 'com.oculus.vrpowermanager.prox_close'] for c in adb.calls), adb.calls)

# pull: the newest recordings into an out folder (absolute: quest.py joins it to the repo root)
dst = os.path.join(OUT, 'pulled')
rc, out = run(q, adb, ['pull', '--out', dst])
p0 = os.path.join(dst, VIDEOS[0])
check('pull: ls -t VideoShots, pulls the newest one', rc == 0 and os.path.exists(p0) and not os.path.exists(
    os.path.join(dst, VIDEOS[1])) and any(c[-4:] == ['shell', 'ls', '-t', '/sdcard/Oculus/VideoShots'] for c in adb.calls),
      out.strip())
rc, out = run(q, adb, ['pull', '--out', dst, '--n', '2'])
check('pull --n 2: the two newest; one already here is not pulled again', rc == 0 and 'already here' in out
      and os.path.exists(os.path.join(dst, VIDEOS[1])) and sum(1 for c in adb.calls if c[2:3] == ['pull']) == 1, out.strip())
rc, out = run(q, adb, ['pull', '--kind', 'photo', '--out', dst])
check('pull --kind photo: from /sdcard/Oculus/Screenshots', rc == 0 and os.path.exists(os.path.join(dst, PHOTOS[0]))
      and any(c[-1] == '/sdcard/Oculus/Screenshots' for c in adb.calls), out.strip())
os.remove(p0)
rc, out = run(q, adb, ['pull', '--out', dst, '--sheet'])
sheet = os.path.splitext(p0)[0] + '_contact_sheet.jpg'
if src:
    check('pull --sheet: runs contact_sheet.py on the pulled video (--every 3), a sheet beside it',
          rc == 0 and adb.sheets and adb.sheets[-1][2:] == [p0, '--every', '3'] and os.path.exists(sheet),
          adb.sheets[-1:] and adb.sheets[-1][1:])
else:
    check('pull --sheet: contact_sheet.py called with the pulled video (ffmpeg missing: not run for real)',
          rc == 0 and adb.sheets and adb.sheets[-1][2:] == [p0, '--every', '3'], adb.sheets[-1:])

# no headset: every command says so
class NoDevice(StandInADB):
    def __call__(self, cmd, *a, **kw):
        if cmd and cmd[0] == 'adb':
            self.calls.append(list(cmd[1:]))
            if cmd[1:] == ['devices']:
                return subprocess.CompletedProcess(cmd, 0, stdout='List of devices attached\n\n', stderr='')
            return subprocess.CompletedProcess(cmd, 1, stdout='', stderr='error: no devices/emulators found')
        return super().__call__(cmd, *a, **kw)


os.remove(q.LAST)
nd = NoDevice()
rc, out = run(q, nd, ['status'])
check('status with no headset: says so', rc == 0 and 'no headset attached' in out, out.strip())
rc, out = run(q, nd, ['open', url])
check('open with no headset: exits non-zero with the plug-it-in hint', rc != 0, rc)
with open(q.LAST, 'w') as f:
    f.write(f'{IP}:5555\n')
rc, out = run(q, nd, ['awake'])
check('a remembered Wi-Fi address is tried (adb connect) before giving up', any(c[:1] == ['connect'] for c in nd.calls),
      nd.calls)

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
