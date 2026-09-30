#!/usr/bin/env python3
"""The Quest headset from the command line, over adb (guide: tools-guides/webxr.md).

    python3 eidoverse/xr/quest.py status                  # which headset, USB or Wi-Fi, awake or asleep
    python3 eidoverse/xr/quest.py wireless                # over USB once: switch on adb over Wi-Fi and connect
    python3 eidoverse/xr/quest.py open https://<mac-ip>:8892/eidoverse/xr/example.html
    python3 eidoverse/xr/quest.py awake                   # keep it rendering off-head (until it reboots)
    python3 eidoverse/xr/quest.py pull [--kind video|photo] [--n 1] [--out work/<id>/quest] [--sheet]

Needs adb (Android platform tools) and developer mode on the headset. Wi-Fi debugging switches itself off
when the headset restarts: plug it in over USB and run `wireless` again. Recordings: press the Meta button
and choose Record video (or Camera); `pull` fetches the newest from the headset (--sheet also makes a
contact sheet with contact_sheet.py). Stop screen mirroring (scrcpy) before a VR session: the encoder load
freezes immersive sessions.
"""
import argparse
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PORT = 5555
LAST = os.path.join(ROOT, 'work', '.quest_address')     # the headset's Wi-Fi address, from the last `wireless`
DIRS = {'video': '/sdcard/Oculus/VideoShots', 'photo': '/sdcard/Oculus/Screenshots'}


def adb(*args, serial=None, check=True, timeout=60):
    cmd = ['adb'] + (['-s', serial] if serial else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        sys.exit(f"adb {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def devices():
    """[(serial, state)] for every attached device; Wi-Fi ones are ip:port."""
    out = adb('devices', check=False)
    return [tuple(l.split('\t')[:2]) for l in out.splitlines()[1:] if '\t' in l]


def device(prefer_usb=False):
    ready = [s for s, st in devices() if st == 'device']
    if not ready and os.path.exists(LAST):          # Wi-Fi debugging outlives an unplug; adb's connection doesn't
        addr = open(LAST).read().strip()
        adb('connect', addr, check=False, timeout=15)
        ready = [s for s, st in devices() if st == 'device']
    if not ready:
        sys.exit('no headset: plug it in over USB (and allow USB debugging in the headset), or run `wireless`')
    usb = [s for s in ready if ':' not in s]
    return (usb or ready)[0] if prefer_usb else (ready[0])


def headset_ip(serial):
    out = adb('shell', 'ip', '-f', 'inet', 'addr', 'show', 'wlan0', serial=serial, check=False)
    m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
    return m.group(1) if m else None


def cmd_status(a):
    if not any(st == 'device' for _, st in devices()) and os.path.exists(LAST):
        adb('connect', open(LAST).read().strip(), check=False, timeout=15)
    ds = devices()
    if not ds:
        print('no headset attached (USB or Wi-Fi)')
        return
    for s, st in ds:
        kind = 'Wi-Fi' if ':' in s else 'USB'
        extra = ''
        if st == 'device':
            wake = adb('shell', 'dumpsys', 'power', serial=s, check=False)
            m = re.search(r'mWakefulness=(\w+)', wake)
            extra = f"  {m.group(1) if m else ''}  wlan {headset_ip(s) or '?'}"
        print(f'{s}  {kind}  {st}{extra}')


def cmd_wireless(a):
    s = device(prefer_usb=True)
    if ':' in s:
        print(f'already on Wi-Fi: {s}')
        return
    ip = headset_ip(s)
    if not ip:
        sys.exit('the headset is not on Wi-Fi')
    adb('tcpip', str(PORT), serial=s)
    time.sleep(2)
    print(adb('connect', f'{ip}:{PORT}').strip())
    os.makedirs(os.path.dirname(LAST), exist_ok=True)
    with open(LAST, 'w') as fh:
        fh.write(f'{ip}:{PORT}\n')
    print(f'Wi-Fi debugging on: {ip}:{PORT} (until the headset restarts; you can unplug it now)')


def cmd_open(a):
    s = device()
    if a.fresh:                                   # avoid a pile of duplicate tabs
        adb('shell', 'am', 'force-stop', 'com.oculus.browser', serial=s)
    adb('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', a.url, 'com.oculus.browser', serial=s)
    print(f'opened {a.url} in the Quest browser on {s}: put the headset on and press ENTER VR')


def cmd_awake(a):
    s = device()
    adb('shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.prox_close', serial=s)
    print('the headset stays awake off-head until it restarts (undo: automation_disable with prox_open)')


def cmd_pull(a):
    s = device()
    folder = DIRS[a.kind]
    names = [n.strip() for n in adb('shell', 'ls', '-t', folder, serial=s, check=False).splitlines() if n.strip()]
    if not names:
        sys.exit(f'nothing in {folder}')
    out = os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    for n in names[:a.n]:
        dst = os.path.join(out, n)
        if os.path.exists(dst):
            print(f'already here: {os.path.relpath(dst, ROOT)}')
        else:
            adb('pull', f'{folder}/{n}', dst, serial=s, timeout=600)
            print(f'pulled {os.path.relpath(dst, ROOT)} ({os.path.getsize(dst) / 1e6:.1f} MB)')
        if a.sheet and a.kind == 'video':
            subprocess.run([sys.executable, os.path.join(ROOT, 'contact_sheet.py'), dst, '--every', '3'], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status').set_defaults(fn=cmd_status)
    sub.add_parser('wireless').set_defaults(fn=cmd_wireless)
    p = sub.add_parser('open')
    p.add_argument('url')
    p.add_argument('--fresh', action='store_true', help='close the browser first (no duplicate tabs)')
    p.set_defaults(fn=cmd_open)
    sub.add_parser('awake').set_defaults(fn=cmd_awake)
    p = sub.add_parser('pull')
    p.add_argument('--kind', choices=sorted(DIRS), default='video')
    p.add_argument('--n', type=int, default=1, help='how many of the newest')
    p.add_argument('--out', default='work/quest', help='repo-relative folder')
    p.add_argument('--sheet', action='store_true', help='also make a contact sheet of each video')
    p.set_defaults(fn=cmd_pull)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
