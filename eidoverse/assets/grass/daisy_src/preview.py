# python eidoverse/assets/grass/daisy_src/preview.py <renders_dir> <region> <out.png> — contact strip of a region's
# passes: albedo x AO | normal | AO | lit relief (two raking lights) | alpha
import sys, numpy as np
from PIL import Image

d, key, out = sys.argv[1], sys.argv[2], sys.argv[3]
L = lambda m: np.load(f'{d}/{key}_{m}.npy')
col, nrm, ao = L('col'), L('nrm'), L('ao')
a = col[..., 3:4]
un = lambda x: np.where(a > 1e-4, x[..., :3] / np.maximum(a, 1e-4), 0)
alb = un(col); n = un(nrm) * 2 - 1
n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
occ = un(ao)[..., :1]
def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)
def lit(n, ldir):
    l = np.array(ldir, dtype=np.float32); l /= np.linalg.norm(l)
    return np.clip((n * l).sum(-1, keepdims=True), 0, 1)
shade = 0.15 + 0.85 * lit(n, [-0.6, 0.5, 0.6])
panels = [
    srgb(alb * (0.35 + 0.65 * occ)) * a + (1 - a) * 0.25,
    (n * 0.5 + 0.5) * a + (1 - a) * 0.25,
    np.repeat(occ, 3, -1) * a + (1 - a) * 0.25,
    srgb(alb * shade * (0.4 + 0.6 * occ)) * a + (1 - a) * 0.12,
    np.repeat(a, 3, -1),
]
strip = np.concatenate([p[::-1] for p in panels], axis=1)       # rows bottom-up -> PNG top-down
Image.fromarray((np.clip(strip, 0, 1) * 255).astype(np.uint8)).save(out)
print('alb range', alb[a[..., 0] > 0.99].min(0), alb[a[..., 0] > 0.99].max(0), 'ao mean', occ[a[..., 0] > 0.99].mean())
