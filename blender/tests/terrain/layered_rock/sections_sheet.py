"""True-scale cross-sections across the trunk, the independent review's figure (out/review/scripts/sections.py, read
only: its sections() at 5 stations from 20 % to 80 % along the trunk, metres above each section's low point) for the
real reference and any number of generated fields, one row each, so a fix is judged on the review's own figure.

    python blender/tests/terrain/layered_rock/sections_sheet.py <recipe> <out.png> <npz> [<npz> ...]

<npz>: gen.py's main-level files (h, cell). Writes <out.png>.
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.join(TN, 'out', 'review', 'scripts'))
from judge import refs  # noqa: E402
import sections as RS  # noqa: E402  (the review's)


def main(a):
    recipe, out = a[0], a[1]
    rows = [('real: ' + RS.REF[recipe], RS.sections(refs.load(RS.REF[recipe]).h, refs.load(RS.REF[recipe]).pixel,
                                                    RS.HALF[recipe]))]
    for p in a[2:]:
        d = np.load(p)
        rows.append((os.path.splitext(os.path.basename(p))[0],
                     RS.sections(np.asarray(d['h'], np.float64), float(d['cell']), RS.HALF[recipe])))
    fig, axs = plt.subplots(len(rows), 5, figsize=(25, 3.2 * len(rows)), sharey=True, squeeze=False)
    for r, (lab, S) in enumerate(rows):
        for k in range(5):
            ax = axs[r, k]
            if k < len(S):
                t, z = S[k]
                ax.fill_between(t, 0, z, color=('#9a8a78' if r == 0 else '#7890a8'))
                ax.plot(t, z, color='k', lw=0.7)
            ax.set_aspect('equal')
            ax.set_title(f'{lab}, station {k + 1}', fontsize=9)
            ax.grid(alpha=0.3)
    fig.suptitle(f"{recipe}: sections across the trunk (true scale, metres above the section's low point)")
    fig.tight_layout()
    fig.savefig(out, dpi=70)
    plt.close(fig)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1:])
