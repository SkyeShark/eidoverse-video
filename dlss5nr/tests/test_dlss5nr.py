"""dlss5nr/tests/test_dlss5nr.py: the DLSS 5 tools from a clean checkout, with no GPU and no weights needed.

    python dlss5nr/tests/test_dlss5nr.py [--out DIR] [--real]

1. The tables: every proxy code on the half grid and increasing, and an 8-bit value back as itself after the round trip.
2. The motion files: motion_npz's save / load / raw planes / conventions agree with np.load.
3. A small film made here (24 frames, 192x108, a texture panning 2 px right and 1 px up a frame, a tone for its sound).
   flow_motion.py on it (needs OpenCV; skipped without it) must find that motion, X near -2 and Y near -1, and
   motion_check.py must name "+X -Y" from those files.
4. dlss5nr.py on the film through a stand-in program (tests/fake_dlss5vk.py: the stream protocol, frames answered
   unchanged): the output has every frame, the sound, the picture it went in with (within the encoder's loss), and the
   program was sent what the options say (motion planes, the negation flag for "-Y", resets on the first frame and on
   --cuts); --from / --to with --keep-rest sends only that range and keeps the whole film.
5. --real, or whenever $DLSS5VK_MODEL and the built program are there: the same film through the real network.
Writes into --out (default: a new temporary folder, removed when every check passed) and prints PASS / FAIL / SKIP per
check; exit 1 on any FAIL.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(TESTS)
sys.path.insert(0, TOOL)
import numpy as np  # noqa: E402

import dlss5nr  # noqa: E402
import flicker  # noqa: E402
import motion_check  # noqa: E402
import motion_npz  # noqa: E402

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
W, H, N, FPS = 192, 108, 24, 24
SHIFT = (2, -1)                       # the texture's motion a frame: 2 px right, 1 px up
RESULTS = []


def record(name, ok, detail=''):
    outcome = 'SKIP' if ok is None else 'PASS' if bool(ok) else 'FAIL'
    RESULTS.append(outcome)
    print(f'[{outcome}] {name}' + (f': {detail}' if detail else ''), flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, **kw)


def frames_of(path, w=W, h=H, pix_fmt='rgb24'):
    """a video's frames: (n, h, w, 3) RGB, or (n, h, w) luma with pix_fmt 'gray'"""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', pix_fmt, '-'],
                         capture_output=True, check=True, creationflags=NO_WINDOW).stdout
    shape = (-1, h, w) if pix_fmt == 'gray' else (-1, h, w, 3)
    return np.frombuffer(raw, np.uint8).reshape(shape)


def psnr(a, b):
    mse = float(((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean())
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def make_film(path):
    """the test film: a smooth random texture, panned SHIFT a frame, near-lossless, with a 440 Hz tone"""
    rng = np.random.default_rng(7)
    big = rng.random((H + 64, W + 96, 3))
    for _ in range(4):                                        # blur: features a flow can follow
        big = (big + np.roll(big, 1, 0) + np.roll(big, -1, 0) + np.roll(big, 1, 1) + np.roll(big, -1, 1)) / 5
    big = (big - big.min()) / (big.max() - big.min())
    tex = (big * 200 + 28).astype(np.uint8)
    frames = [np.roll(np.roll(tex, SHIFT[0] * t, axis=1), SHIFT[1] * t, axis=0)[32:32 + H, 48:48 + W] for t in range(N)]
    raw = np.stack(frames).tobytes()
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                        '-i', '-', '-f', 'lavfi', '-i', f'sine=frequency=440:duration={N / FPS}', '-c:v', 'libx264', '-qp', '0',
                        '-pix_fmt', 'yuv444p', '-c:a', 'aac', '-shortest', path], input=raw, capture_output=True,
                       creationflags=NO_WINDOW)
    if r.returncode:
        raise SystemExit(f'ffmpeg could not make the test film: {r.stderr.decode(errors="replace")}')
    return np.stack(frames)


def has_audio(path):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_name', '-of', 'json', path])
    return bool(json.loads(r.stdout or '{}').get('streams'))


def test_tables():
    lut = dlss5nr.PROXY_LUT
    on_grid = np.array_equal(lut, lut.astype(np.float16).astype(np.float32))
    rising = bool(np.all(np.diff(lut) > 0))
    back = dlss5nr.BACK_LUT[(np.clip(lut, 0, 1) * 4096.0 + 0.5).astype(np.int32)]
    record('tables: proxy codes on the half grid and increasing', on_grid and rising)
    record('tables: 8-bit -> proxy -> 8-bit is exact', np.array_equal(back, np.arange(256)),
           f'{int(np.count_nonzero(back != np.arange(256)))} of 256 values change')


def test_npz(out):
    rng = np.random.default_rng(3)
    xyzw = (rng.standard_normal((4, 12, 20)) * 5).astype(np.float16)
    p = os.path.join(out, 'npz_check.npz')
    motion_npz.save(p, xyzw)
    same = np.array_equal(np.load(p)['xyzw'], xyzw) and np.array_equal(motion_npz.load(p), xyzw)
    a, b = motion_npz.raw_planes(p, 0, 1, 12, 20)
    planes = np.array_equal(np.frombuffer(a, np.float16).reshape(12, 20), xyzw[0]) and \
        np.array_equal(np.frombuffer(b, np.float16).reshape(12, 20), xyzw[1])
    dx, dy = motion_npz.displacement(xyzw, '+X -Y')
    signs = np.array_equal(dx, xyzw[0].astype(np.float32)) and np.array_equal(dy, -xyzw[1].astype(np.float32))
    try:
        motion_npz.parse_convention('X Y')
        refused = False
    except ValueError:
        refused = True
    record('motion files: save / load / raw planes / conventions', same and planes and signs and refused)


def test_flow(film, out):
    try:
        import cv2  # noqa: F401
    except ImportError:
        record('flow_motion + motion_check on a panning film', None, 'OpenCV is not installed (pip install opencv-python-headless)')
        return None
    flow = os.path.join(out, 'flow')
    r = run([sys.executable, os.path.join(TOOL, 'flow_motion.py'), film, flow, '--preset', 'medium'])
    if r.returncode:
        record('flow_motion runs', False, r.stdout + r.stderr)
        return None
    files = sorted(f for f in os.listdir(flow) if f.endswith('.npz'))
    xs, ys = [], []
    for f in files[2:-2]:
        xyzw = motion_npz.load(os.path.join(flow, f)).astype(np.float32)
        xs.append(np.median(xyzw[0][8:-8, 8:-8]))
        ys.append(np.median(xyzw[1][8:-8, 8:-8]))
    x, y = float(np.median(xs)), float(np.median(ys))
    record('flow_motion: a file a frame after the first', files == [f'{i:04d}.npz' for i in range(1, N)], f'{len(files)} files')
    record('flow_motion: the pan, current -> previous with Y up', abs(x + SHIFT[0]) < 0.3 and abs(y - SHIFT[1]) < 0.3,
           f'median X {x:+.2f} (want {-SHIFT[0]:+d}), Y {y:+.2f} (want {SHIFT[1]:+d})')
    results = [motion_check.check_frame(film, flow, m, 0, W, H) for m in (6, 12, 18)]
    best = motion_check.verdict(results)
    errs = results[1]['errors'] or {}
    record('motion_check: names "+X -Y" on flow files', best == '+X -Y',
           f'verdict {best}; frame 12: +X -Y {errs.get("+X -Y", 0):.2f}, none {errs.get("none", 0):.2f}')
    return flow


def stream(film, out_mp4, extra, model, exe, log=None):
    env = dict(os.environ)
    if log:
        env['FAKE_DLSS5VK_LOG'] = log
        if os.path.exists(log):
            os.remove(log)
    return run([sys.executable, os.path.join(TOOL, 'dlss5nr.py'), film, out_mp4, '--model', model, '--exe', exe] + extra,
               env=env)


def test_stream(film, frames, flow, out):
    model = os.path.join(out, 'model_stub')
    os.makedirs(model, exist_ok=True)
    with open(os.path.join(model, 'manifest.json'), 'w', encoding='utf-8') as f:
        f.write('{"stub": "for the stand-in program; the real program needs real weights"}\n')
    fake = os.path.join(TESTS, 'fake_dlss5vk.py')
    log = os.path.join(out, 'fake_log.jsonl')
    # without weights the tool refuses with the sentence that says what to supply
    r = run([sys.executable, os.path.join(TOOL, 'dlss5nr.py'), film, os.path.join(out, 'x.mp4'), '--exe', fake, '--model',
             os.path.join(out, 'no_model_here')], env={k: v for k, v in os.environ.items() if k != 'DLSS5VK_MODEL'})
    record('dlss5nr: refuses without weights', r.returncode != 0 and 'supply the weights' in (r.stdout + r.stderr))
    extra = ['--motion', flow, '--convention', '+X -Y', '--offset', '0', '--cuts', '12'] if flow else []
    dst = os.path.join(out, 'fake_whole.mp4')
    r = stream(film, dst, extra, model, fake, log)
    if r.returncode:
        record('dlss5nr through the stand-in', False, (r.stdout + r.stderr)[-1500:])
        return
    got = frames_of(dst, pix_fmt='gray')
    luma = frames_of(film, pix_fmt='gray')
    record('dlss5nr: every frame back, and the sound', len(got) == N and has_audio(dst), f'{len(got)} frames')
    record('dlss5nr: the picture comes back as it went in (stand-in: no network)', psnr(got, luma) > 38,
           f'luma PSNR {psnr(got, luma):.1f} dB after x264 crf 16')
    sent = [json.loads(line) for line in open(log, encoding='utf-8')]
    if flow:
        want = [0] + [2 | 8 | (1 if f == 12 else 0) for f in range(1, N)]      # frame 0 has no flow file
        flags = [s['flags'] for s in sent]
        record('dlss5nr: motion, "-Y" negation and the cut sent per frame', flags == want, f'flags {flags}')
        xyzw = motion_npz.load(os.path.join(flow, '0010.npz')).astype(np.float32)
        s10 = sent[10]
        record('dlss5nr: the motion planes sent as stored', abs(s10['dx_mean'] - xyzw[0].mean()) < 1e-3
               and abs(s10['dy_mean'] - xyzw[1].mean()) < 1e-3)
    # a range with --keep-rest: only frames 4-9 go to the program, the film stays whole, the range starts with a reset
    dst = os.path.join(out, 'fake_range.mp4')
    r = stream(film, dst, ['--from', '4', '--to', '9', '--keep-rest'] + extra, model, fake, log)
    if r.returncode:
        record('dlss5nr --from/--to --keep-rest', False, (r.stdout + r.stderr)[-1500:])
        return
    sent = [json.loads(line) for line in open(log, encoding='utf-8')]
    got = frames_of(dst, pix_fmt='gray')
    first_reset = (sent[0]['flags'] & 1) == 1 if flow else True
    record('dlss5nr: --from 4 --to 9 --keep-rest', len(sent) == 6 and len(got) == N and first_reset,
           f'{len(sent)} frames sent, {len(got)} in the film')


def test_flicker():
    """flicker.measure on a held picture whose copy pumps by 3 levels a frame: every pixel still in the input, each
    output step 6 levels, the mean 0 apart"""
    rng = np.random.default_rng(5)
    a = np.repeat(rng.integers(20, 230, (1, 40, 60)).astype(np.float32), 9, axis=0)
    b = a + 3.0 * (-1.0) ** np.arange(9)[:, None, None]
    m = flicker.measure(a, b)
    ok = (m['frames'] == 9 and m['still_share'] == 1.0 and m['still_input'] == 0.0 and abs(m['still_output'] - 6.0) < 1e-3
          and abs(m['mean_step_output'] - 6.0) < 1e-3 and abs(m['mean_offset'] - 3.0 / 9) < 1e-3)
    record('flicker: a pumping copy of a held picture', ok,
           f'still {m["still_share"] * 100:.0f} %, output {m["still_output"]:.2f} levels a frame, '
           f'mean steps {m["mean_step_output"]:.2f}')


def test_real(film, frames, flow, out):
    model = os.environ.get('DLSS5VK_MODEL')
    exe = os.path.abspath(os.environ.get('DLSS5VK_EXE') or dlss5nr.DEFAULT_EXE)
    if not (model and os.path.isfile(os.path.join(model, 'manifest.json')) and os.path.isfile(exe)):
        record('the real network', None, 'needs DLSS5VK_MODEL (your weights) and a built program (build.py)')
        return
    dst = os.path.join(out, 'real.mp4')
    extra = ['--motion', flow, '--convention', '+X -Y', '--offset', '0'] if flow else []
    r = stream(film, dst, extra + ['--style', '1'], model, exe)
    tail = (r.stdout + r.stderr).strip().splitlines()
    if r.returncode:
        record('the real network', False, '\n'.join(tail[-12:]))
        return
    got, luma = frames_of(dst, pix_fmt='gray'), frames_of(film, pix_fmt='gray')
    record('the real network: every frame, re-rendered', len(got) == N and 15 < psnr(got, luma) < 60,
           f'{len(got)} frames, luma PSNR against the input {psnr(got, luma):.1f} dB; '
           + next((t for t in tail if t.startswith('[run] streamed')), ''))


def main():
    A = sys.argv[1:]
    out = A[A.index('--out') + 1] if '--out' in A else tempfile.mkdtemp(prefix='dlss5nr_test_')
    os.makedirs(out, exist_ok=True)
    for tool in ('ffmpeg', 'ffprobe'):
        if shutil.which(tool) is None:
            raise SystemExit(f'{tool} is not on PATH')
    print(f'[test] writing into {out}', flush=True)
    test_tables()
    test_npz(out)
    test_flicker()
    film = os.path.join(out, 'pan.mp4')
    frames = make_film(film)
    frames = frames_of(film)                     # as the tools see it (through yuv444p)
    flow = test_flow(film, out)
    test_stream(film, frames, flow, out)
    if '--real' in A or os.environ.get('DLSS5VK_MODEL'):
        test_real(film, frames, flow, out)
    fails = RESULTS.count('FAIL')
    print(f'[test] {RESULTS.count("PASS")} passed, {fails} failed, {RESULTS.count("SKIP")} skipped')
    if '--out' not in A and not fails:            # its own temporary folder: removed when all passed, kept to look at
        shutil.rmtree(out, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
