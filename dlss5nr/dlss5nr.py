"""dlss5nr/dlss5nr.py: DLSS 5 neural rendering over a finished film, as one stream through OpenDLSS-NR.

    python dlss5nr/dlss5nr.py <in.mp4> <out.mp4> --model <model dir>
        [--from f0 --to f1] [--keep-rest] [--seed 1 | --seed-per-frame] [--style S] [--tone T] [--structure S] [--skin S]
        [--motion <dir> --convention "+X -Y" [--offset N] [--cuts 110,220,... | --cuts <file>]]
        [--stills <dir> [--stills-every 12]] [--crf 16] [--preset medium] [--exe <dlss5vk.exe>] [--workers 8] [--ahead 24]

The film is decoded by ffmpeg, every frame goes straight into ONE `dlss5vk run --stream` (OpenDLSS-NR built with this
folder's patch: build.py), and the published frames come straight back into x264 (High, yuv420p, crf 16, preset medium);
the film's own sound is muxed back, cut to the same frames. Nothing is written but the output (and the stills).

The network re-renders a frame: it adds the detail, shading and tone of its training (NVIDIA's DLSS 5 Neural Rendering,
build 310.8.0); input and output are the same size. Its input is a display-referred proxy, and a finished film is display-
referred already, so a frame's display value v (sRGB decoded) stands where the proxy has paper-white-relative radiance:
proxy = srgb(shoulder(v)), the shoulder NVIDIA's (above 0.75: 0.75 + 0.25 (1 - exp(-5.770780 (v - 0.75)))), on the half
grid. The published RGB is in that same code space; the shoulder is undone on the way out, so where the network changes
nothing the film's own grade comes back as it was (an 8-bit value survives the round trip exactly). Both conversions are
tables (PROXY_LUT, BACK_LUT below); the program builds its own and sends them when it starts, and this script stops
unless they are exactly these.

THE TEMPORAL PATH. Run frame by frame, the network makes the light flicker (each frame is re-rendered on its own). With
--motion it carries its history as a game does: the previous published frame, warped by the motion vectors, in its
history lanes, blended by its own per-pixel weight. --motion is a folder of motion files, one a frame
(motion_npz.py: blender/tools/render_motion.py writes them from EEVEE's Vector pass on the Blender editions, the WebGPU
runner's "motionVectors" from three's velocity, flow_motion.py from the frames themselves). --convention says which pair
of their channels, with which signs, points from a pixel to where it was in the previous frame, rows down; every source
here writes "+X -Y", and motion_check.py decides it on the film rather than assuming it. --offset N: the motion file of
video frame f is <motion>/<f - N:04d>.npz (Blender numbers frames from the scene's frame_start, usually 1: offset -1;
flow_motion and the WebGPU runner number from 0: offset 0). The history resets on the first frame and on every cut:
--cuts lists the motion-file frames that start a shot (or a file of them, as render_motion.py writes); a frame with no
motion file runs alone. Without --motion every frame runs alone, with a fixed --seed (or the frame index with
--seed-per-frame).

THE CONDITIONING passes to the network as it is: --style (0 default; 1 moves the picture furthest, toward crisper shading
and richer colour), --tone and --structure (scale the default), --skin (-1: automatic).

--from / --to (0-based video frames) choose the range the network sees; --keep-rest copies the frames outside it
unchanged, so the output is still the whole film. --stills writes every 12th frame (--stills-every) as before | after
PNGs (needs Pillow). --workers / --ahead: the threads reading the motion files, and how many frames ahead they read.

WHAT IT NEEDS: Windows, an NVIDIA Ada (or newer) GPU with a driver exposing VK_KHR_cooperative_matrix,
VK_NV_cooperative_matrix2, VK_EXT_shader_float8 and VK_NV_cuda_kernel_launch; ffmpeg and ffprobe on PATH; numpy. The
program: --exe, else $DLSS5VK_EXE, else what build.py builds (dlss5nr/opendlss/build/dlss5vk.exe). The weights are
yours to supply: --model, else $DLSS5VK_MODEL, a model directory in OpenDLSS-NR's layout (its manifest.json and stage
files). This toolkit contains no NVIDIA software or weights and no instructions for obtaining them; OpenDLSS-NR is not
affiliated with or endorsed by NVIDIA, and "DLSS" is NVIDIA's trademark (patch/NOTICE).
"""
import json
import os
import queue
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import motion_npz  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXE = os.path.join(HERE, 'opendlss', 'build', 'dlss5vk.exe')
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0       # CREATE_NO_WINDOW: no console window for the children
K = 5.770780                                           # NVIDIA's shoulder


# ---- the conversions between a film's 8-bit sRGB and the network's proxy code space
def srgb_dec(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_enc(v):
    v = np.clip(v, 0.0, None)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)


def shoulder(v):
    return np.where(v > 0.75, 0.75 + 0.25 * (1.0 - np.exp(-K * (v - 0.75))), v)


def unshoulder(s):
    s = np.clip(s, 0.0, 0.75 + 0.25 * (1 - 1e-6))
    return np.where(s > 0.75, 0.75 - np.log(1.0 - (s - 0.75) / 0.25) / K, s)


# an 8-bit film value -> its proxy code, on the half grid (exact: 256 entries)
PROXY_LUT = srgb_enc(shoulder(srgb_dec(np.arange(256) / 255.0))).astype(np.float16).astype(np.float32)
# the way back, srgb_enc(unshoulder(srgb_dec(x))) on x in [0, 1], is one monotone curve: 4097 entries read at the
# nearest 1/4096, within 0.06 of a level of the exact maths
BACK_LUT = np.clip(srgb_enc(unshoulder(srgb_dec(np.linspace(0.0, 1.0, 4097)))) * 255.0 + 0.5, 0, 255).astype(np.uint8)
HELLO_BYTES = 16 + 256 * 4 + 4097 + 3
FLAG_RESET, FLAG_MOTION, FLAG_NEGATE_X, FLAG_NEGATE_Y = 1, 2, 4, 8

# Every pipe gets a 32 MB buffer. Windows' default is a few KB, and ffmpeg writes its frames 32 KB at a time: through such
# a pipe each write waits for the reader's next read, and the decoder delivers around 30 1080p frames a second where
# through a 32 MB one it delivers over 100, the same bytes.
PIPE_BYTES = 32 << 20


def probe(src):
    """width, height, rate, frames: the container's frame count, or the frames counted where it has none"""
    def run_probe(extra):
        out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0'] + extra + ['-of', 'json', src],
                             capture_output=True, text=True, check=True, creationflags=NO_WINDOW).stdout
        return json.loads(out)['streams'][0]
    s = run_probe(['-show_entries', 'stream=width,height,r_frame_rate,nb_frames'])
    n = s.get('nb_frames')
    if not str(n).isdigit():
        n = run_probe(['-count_frames', '-show_entries', 'stream=nb_read_frames'])['nb_read_frames']
    return int(s['width']), int(s['height']), s['r_frame_rate'], int(n)


def read_exact(stream, n):
    """n bytes from a pipe, or None if it ends first"""
    buf = bytearray(n)
    view, got = memoryview(buf), 0
    while got < n:
        k = stream.readinto(view[got:])
        if not k:
            return None
        got += k
    return buf


def write_all(stream, data):
    view = memoryview(data).cast('B')
    while len(view):
        view = view[stream.write(view):]


def pipe_pair():
    """(read fd, write fd) of an anonymous pipe with a PIPE_BYTES buffer"""
    if os.name != 'nt':
        return os.pipe()
    import _winapi
    import msvcrt
    r, w = _winapi.CreatePipe(None, PIPE_BYTES)
    return msvcrt.open_osfhandle(r, os.O_RDONLY), msvcrt.open_osfhandle(w, 0)


def spawn(cmd, stdin=False, stdout=False, stderr=None):
    """a child without a window, with big pipes for the stdin / stdout asked for: (process, its stdin, its stdout)"""
    ins, outs = pipe_pair() if stdin else (None, None), pipe_pair() if stdout else (None, None)
    proc = subprocess.Popen(cmd, stdin=ins[0], stdout=outs[1], stderr=stderr, creationflags=NO_WINDOW)
    for fd in (ins[0], outs[1]):        # the child's ends: closed here, so the ends of the stream reach the other side
        if fd is not None:
            os.close(fd)
    return (proc, open(ins[1], 'wb', buffering=0) if stdin else None, open(outs[0], 'rb', buffering=0) if stdout else None)


def cpu_seconds(proc):
    """the CPU time (user + kernel) a finished child used, from its process handle (Windows; 0 elsewhere)"""
    if os.name != 'nt':
        return 0.0
    import ctypes
    from ctypes import wintypes
    times = [wintypes.FILETIME() for _ in range(4)]
    if not ctypes.WinDLL('kernel32').GetProcessTimes(wintypes.HANDLE(int(proc._handle)), *[ctypes.byref(t) for t in times]):
        return 0.0
    return sum(((t.dwHighDateTime << 32) | t.dwLowDateTime) / 1e7 for t in times[2:])


def parse_cuts(value):
    """--cuts: a comma list of frames, or a file holding them (commas or whitespace)"""
    if not value:
        return set()
    text = open(value, encoding='utf-8').read() if os.path.isfile(value) else value
    return {int(v) for v in text.replace(',', ' ').split()}


def program_command(exe):
    """the program's argv head: the exe, or a Python stand-in (tests) run with this interpreter"""
    return [sys.executable, exe] if exe.lower().endswith('.py') else [exe]


def main():
    A = sys.argv[1:]
    if len(A) < 2 or A[0].startswith('--') or A[1].startswith('--'):
        raise SystemExit(__doc__)
    src, dst = A[0], A[1]
    t_start = time.time()

    def opt(k, d=None):
        return A[A.index(k) + 1] if k in A else d

    f0, f1 = int(opt('--from', '0')), opt('--to')
    keep_rest = '--keep-rest' in A
    seed_fixed = int(opt('--seed', '1'))
    per_frame = '--seed-per-frame' in A
    stills = opt('--stills')
    every = int(opt('--stills-every', '12'))
    motion_dir = opt('--motion')
    convention = opt('--convention')
    offset = int(opt('--offset', '0'))
    cuts = parse_cuts(opt('--cuts', ''))
    cond = [x for k in ('--style', '--tone', '--structure', '--skin') if k in A for x in (k, opt(k))]
    crf, preset = opt('--crf', '16'), opt('--preset', 'medium')
    exe = os.path.abspath(opt('--exe', os.environ.get('DLSS5VK_EXE') or DEFAULT_EXE))
    model = opt('--model', os.environ.get('DLSS5VK_MODEL'))
    workers, ahead = int(opt('--workers', '8')), int(opt('--ahead', '24'))
    if not model or not os.path.isfile(os.path.join(model, 'manifest.json')):
        raise SystemExit('[dlss5] supply the weights: --model <dir> (or DLSS5VK_MODEL), a model directory in '
                         "OpenDLSS-NR's layout with its manifest.json" + (f' ({model} has none)' if model else ''))
    if not os.path.isfile(exe):
        raise SystemExit(f'[dlss5] no program at {exe}: build it (python dlss5nr/build.py), or give --exe / DLSS5VK_EXE')
    if motion_dir and not convention:
        raise SystemExit('[dlss5] --motion needs --convention: run motion_check.py on the film first')
    if motion_dir:
        (sx, ix), (sy, iy) = motion_npz.parse_convention(convention)
        negate = (FLAG_NEGATE_X if sx < 0 else 0) | (FLAG_NEGATE_Y if sy < 0 else 0)   # the program negates dx / dy

    W, H, rate, N = probe(src)
    f1 = int(f1) if f1 is not None else N - 1
    fps = eval(rate)
    frame_bytes = W * H * 3
    first, last = (0, N - 1) if keep_rest else (f0, f1)
    print(f'[dlss5] {src}: {W}x{H} at {rate}, frames {f0}-{f1} of {N}' + (' (the rest copied)' if keep_rest else '')
          + (f'; temporal, motion {motion_dir} read as "{convention}", offset {offset}, cuts {sorted(cuts)}' if motion_dir
             else '; no history') + f'; streamed through {exe}', flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    # the decoder's frames: -frames:v ends it at the last one (select alone holds the last few back until the rest of the
    # film is decoded)
    dec, _, dec_out = spawn(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'select=between(n\\,{first}\\,{last})', '-fps_mode',
                             'passthrough', '-frames:v', str(last - first + 1), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            stdout=True)
    enc, enc_in, _ = spawn(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', rate,
                            '-i', '-', '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', crf,
                            '-preset', preset, dst + '.video.mp4'], stdin=True)
    run, run_in, run_out = spawn(program_command(exe) + ['run', '--stream', '--model', model, '--width', str(W), '--height',
                                                         str(H)] + cond, stdin=True, stdout=True, stderr=subprocess.PIPE)

    def relay_stderr():
        for line in iter(run.stderr.readline, b''):
            print('[run]', line.decode('utf-8', 'replace').rstrip(), flush=True)

    relay = threading.Thread(target=relay_stderr, daemon=True)
    relay.start()
    procs = (dec, enc, run)
    # where the time goes, summed over the frames: the sender waiting for the decoder and for the motion, and writing to
    # the program; the output side waiting for the program's frames and writing them to the encoder
    state = {'frames': 0, 'history': 0, 'error': None, 't_first': None,
             'decoder': 0.0, 'motion': 0.0, 'send': 0.0, 'program': 0.0, 'encoder': 0.0}
    try:
        hello = read_exact(run_out, HELLO_BYTES)
        if hello is None:
            raise SystemExit(f'[dlss5] the stream did not start: exit {run.wait()}')
        if struct.unpack_from('<4sIII', hello) != (b'NRS1', 1, W, H):
            raise SystemExit(f'[dlss5] the program answered {struct.unpack_from("<4sIII", hello)}, not NRS1 1 {W} {H}')
        if not (np.array_equal(np.frombuffer(hello, '<u4', 256, 16), PROXY_LUT.view('<u4'))
                and np.array_equal(np.frombuffer(hello, np.uint8, 4097, 16 + 1024), BACK_LUT)):
            raise SystemExit("[dlss5] the program's 8-bit <-> proxy tables are not this script's: not run")
        t_ready = time.time()

        frames_in = queue.Queue(maxsize=6)       # decoded frames, in order
        outs = queue.Queue()                     # what goes into the film, in order: ('copy', f, raw) / ('nr', f, before)

        def decode():
            try:
                for f in range(first, last + 1):
                    raw = read_exact(dec_out, frame_bytes)
                    if raw is None:
                        break
                    frames_in.put((f, raw))
            finally:
                frames_in.put(None)

        def output():
            try:
                while True:
                    item = outs.get()
                    if item is None:
                        return
                    kind, f, data = item
                    if kind == 'copy':                       # --keep-rest: as it is, in order
                        write_all(enc_in, data)
                        continue
                    t = time.time()
                    rgb = read_exact(run_out, frame_bytes)
                    if rgb is None:
                        raise RuntimeError(f'the stream ended before frame {f}: exit {run.wait()}')
                    t2 = time.time()
                    write_all(enc_in, rgb)
                    state['program'] += t2 - t
                    state['encoder'] += time.time() - t2
                    if stills and (f - f0) % every == 0:
                        from PIL import Image
                        after = np.frombuffer(rgb, np.uint8).reshape(H, W, 3)
                        Image.fromarray(np.concatenate([data, after], axis=1)).save(
                            os.path.join(stills, f'{f:05d}_before_after.png'))
                    state['frames'] += 1
                    if state['frames'] % 48 == 0:
                        speed = state['frames'] / (time.time() - state['t_first'])
                        print(f'[dlss5] {state["frames"]} frames, {speed:.1f} frames a second', flush=True)
            except BaseException as error:           # (the sender would wait on a program nobody reads: stop it)
                state['error'] = error
                run.kill()

        if stills:
            os.makedirs(stills, exist_ok=True)
        pool = ThreadPoolExecutor(max_workers=workers)
        motion_ahead = {}
        scheduled = [f0]

        def schedule(upto):                          # the motion of the frames up to `upto`, read in the pool
            while motion_dir and scheduled[0] <= min(upto, f1):
                g = scheduled[0]
                motion_ahead[g] = pool.submit(motion_npz.raw_planes, os.path.join(motion_dir, f'{g - offset:04d}.npz'),
                                              ix, iy, H, W)
                scheduled[0] += 1

        schedule(f0 + ahead)
        threads = [threading.Thread(target=decode, daemon=True), threading.Thread(target=output, daemon=True)]
        for t in threads:
            t.start()
        try:
            while True:
                t = time.time()
                item = frames_in.get()
                if state['t_first'] is not None:     # (the decoder's way to the first frame is start-up, not a wait)
                    state['decoder'] += time.time() - t
                if item is None:
                    break
                f, raw = item
                if not f0 <= f <= f1:
                    outs.put(('copy', f, raw))
                    continue
                flags, motion = 0, None
                if motion_dir:
                    t = time.time()
                    motion = motion_ahead.pop(f).result()
                    state['motion'] += time.time() - t
                    schedule(f + ahead)
                    if motion is not None:
                        reset = f == f0 or (f - offset) in cuts
                        flags = FLAG_MOTION | negate | (FLAG_RESET if reset else 0)
                        state['history'] += 0 if reset else 1
                seed = f + 1 if per_frame else seed_fixed
                outs.put(('nr', f, np.frombuffer(raw, np.uint8).reshape(H, W, 3) if stills else None))
                if state['t_first'] is None:
                    state['t_first'] = time.time()
                t = time.time()
                write_all(run_in, struct.pack('<4sIII', b'NRF1', seed, flags, 0))
                write_all(run_in, raw)
                if motion is not None:
                    write_all(run_in, motion[0])
                    write_all(run_in, motion[1])
                state['send'] += time.time() - t
        except OSError as error:                     # the program has gone: its own words are above, on stderr
            if state['error'] is None:
                state['error'] = error
        finally:
            try:
                run_in.close()
            except OSError:
                pass
            outs.put(None)
            pool.shutdown(wait=False, cancel_futures=True)
        if dec.poll() is None:                       # every frame wanted is read; past `last` select passes nothing more
            dec.kill()
        threads[1].join()
        code = run.wait()
        relay.join(timeout=10)
        if state['error'] is not None or code != 0:
            who = f'the encoder exited ({enc.poll()})' if enc.poll() not in (None, 0) else f'program exit {code}'
            raise SystemExit(f'[dlss5] the stream failed ({who}): {state["error"]!r}')
        enc_in.close()
        enc.wait()
        t_encoded = time.time()
        dec.wait()
        if enc.returncode != 0:
            raise SystemExit(f'[dlss5] the encoder failed: exit {enc.returncode}')
        per = 1000.0 / max(1, state['frames'])
        print(f'[dlss5] a frame waited {state["decoder"] * per:.1f} ms for the decoder, {state["motion"] * per:.1f} ms for its '
              f'motion, {state["send"] * per:.1f} ms going into the program; then {state["program"] * per:.1f} ms for the '
              f'program\'s answer, {state["encoder"] * per:.1f} ms going into the encoder; CPU a frame: decoder '
              f'{cpu_seconds(dec) * per:.0f} ms, program {cpu_seconds(run) * per:.0f} ms, encoder {cpu_seconds(enc) * per:.0f} '
              f'ms, this script {time.process_time() * per:.0f} ms', flush=True)
        # the film's own sound, cut to the same frames (no -shortest: the sound is cut to the frames' length already, and
        # a sound a few milliseconds short of the picture would cut its last frames)
        t0 = first / fps
        dur = (last - first + 1) / fps
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', dst + '.video.mp4', '-ss', f'{t0:.4f}', '-t', f'{dur:.4f}', '-i',
                        src, '-map', '0:v', '-map', '1:a?', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-movflags',
                        '+faststart', dst], check=True, creationflags=NO_WINDOW)
        os.remove(dst + '.video.mp4')
        n = state['frames']
        span = t_encoded - state['t_first'] if state['t_first'] else 0.0
        print(f'[dlss5] wrote {dst}: {n} frames through the network ({state["history"]} with history); '
              f'{n / span if span > 0 else 0.0:.1f} frames a second from the first frame in to the last one encoded '
              f'({span:.1f} s); {time.time() - t_start:.1f} s in all (start-up {t_ready - t_start:.1f} s, then the decoder\'s '
              f'way to frame {first} and the sound)', flush=True)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()


if __name__ == '__main__':
    main()
