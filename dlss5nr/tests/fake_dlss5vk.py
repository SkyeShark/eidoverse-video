"""dlss5nr/tests/fake_dlss5vk.py: a stand-in for `dlss5vk run --stream` that needs no GPU and no weights, for testing
dlss5nr.py's side of the stream: the hello with the two tables, then per frame the "NRF1" record (seed, flags, the frame
and, with flag 2, two float16 motion planes) answered with the frame unchanged (an 8-bit value round-trips the tables
exactly, as the real program publishes a frame the network left alone). With $FAKE_DLSS5VK_LOG set, it appends a JSON
line a frame: its index, seed and flags, and the mean of each motion plane as received (before any negation).

    python dlss5nr/dlss5nr.py <in.mp4> <out.mp4> --exe dlss5nr/tests/fake_dlss5vk.py --model <a dir with manifest.json>
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402

from dlss5nr import BACK_LUT, PROXY_LUT  # noqa: E402


def read_exact(stream, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None if not buf else bytes(buf)
        buf += chunk
    return bytes(buf)


def main():
    a = sys.argv[1:]
    if a[:2] != ['run', '--stream'] or '--model' not in a:
        sys.exit('usage: fake_dlss5vk.py run --stream --model <dir> --width W --height H [conditioning]')
    w, h = int(a[a.index('--width') + 1]), int(a[a.index('--height') + 1])
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    stdout.write(struct.pack('<4sIII', b'NRS1', 1, w, h) + PROXY_LUT.astype('<f4').tobytes() + BACK_LUT.tobytes()
                 + b'\0\0\0')
    stdout.flush()
    log = os.environ.get('FAKE_DLSS5VK_LOG')
    index = 0
    while True:
        head = read_exact(stdin, 16)
        if head is None:
            break
        magic, seed, flags, _ = struct.unpack('<4sIII', head)
        if magic != b'NRF1':
            sys.exit('fake_dlss5vk: a frame record does not start with NRF1')
        frame = read_exact(stdin, w * h * 3)
        record = {'index': index, 'seed': seed, 'flags': flags}
        if flags & 2:
            planes = np.frombuffer(read_exact(stdin, w * h * 4), np.float16).astype(np.float32).reshape(2, h, w)
            record['dx_mean'], record['dy_mean'] = float(planes[0].mean()), float(planes[1].mean())
        stdout.write(frame)
        stdout.flush()
        if log:
            with open(log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + '\n')
        index += 1
    sys.stderr.write(f'fake_dlss5vk: streamed {index} frames at {w}x{h}\n')


if __name__ == '__main__':
    main()
