"""The back of the sign board: it was a shipping box once. Faded generic box print (no marks of any
real company), a flattened-fold crease and a scuff. RGBA: multiply-blended onto the kraft back."""
import os, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts'))
W, H = 1200, 900                                  # 0.60 x 0.45 m at 2 px/mm
im = Image.new('RGBA', (W, H), (255, 255, 255, 0))
d = ImageDraw.Draw(im)
ink = (38, 32, 30, 190)
f = ImageFont.truetype(os.path.join(FONTS, 'Rajdhani-Bold.ttf'), 70)
# an up-arrow pair + THIS SIDE UP, rotated as the box panel was
arr = Image.new('RGBA', (520, 300), (0, 0, 0, 0)); a = ImageDraw.Draw(arr)
for x in (60, 190):
    a.polygon([(x, 120), (x + 50, 40), (x + 100, 120)], fill=ink)
    a.rectangle([x + 32, 118, x + 68, 230], fill=ink)
a.rectangle([40, 245, 320, 262], fill=ink)
a.text((330, 60), 'THIS', font=f, fill=ink); a.text((330, 130), 'SIDE UP', font=f, fill=ink)
arr = arr.rotate(90, expand=True)
im.alpha_composite(arr, (W - arr.size[0] - 70, 120))
f2 = ImageFont.truetype(os.path.join(FONTS, 'Rajdhani-Bold.ttf'), 44)
d.text((90, H - 170), 'FRAGILE  -  HANDLE WITH CARE', font=f2, fill=(38, 32, 30, 150))
d.text((90, H - 115), 'BOX 24 x 18 x 12', font=f2, fill=(38, 32, 30, 120))
# fade the print unevenly (old flexo ink rubbed off)
rng = np.random.default_rng(4)
A = np.asarray(im, np.float32)
noise = np.asarray(Image.fromarray((rng.random((H // 20, W // 20)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
fine = rng.random((H, W)).astype(np.float32)
A[..., 3] *= np.clip(0.35 + 0.65 * noise, 0, 1) * (0.75 + 0.25 * fine)
# the flattened fold: a crease line with a soft shadow on one side
x0 = int(W * 0.33)
for dx in range(-10, 11):
    w = np.exp(-(dx / 4.0) ** 2) * (60 if dx < 0 else 25)
    A[:, x0 + dx, :3] = A[:, x0 + dx, :3] * 0 + 60
    A[:, x0 + dx, 3] = np.maximum(A[:, x0 + dx, 3], w)
out = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8), 'RGBA').filter(ImageFilter.GaussianBlur(0.6))
out.save(os.path.join(HERE, 'sign_back_print.png'))
print('ok')
