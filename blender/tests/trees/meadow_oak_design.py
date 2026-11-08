"""The meadow oak, as dials: a white oak designed for a sunny-meadow shot.

A lone open-grown white oak reads as a short massive bole dividing low into a few
heavy spreading scaffolds under a broad dome wider than it is tall; leaves fill
the outer shell and light reaches the limbs inside. Judged in meadow_oak.py's
renders (wide / near / backlit / under / LOD1) against the species default.
"""

SEED = 1737   # chosen from 1737 / 42 / 7: the broadest, most open-grown silhouette
MEADOW_OAK = {
    'height': 14.5,          # open-grown: shorter and broader than a forest oak
    'levels': 4,             # a fourth branch order: fine twigs inside the crown
    'trunks': 1,             # one massive bole (the preset forks at the soil)
    'trunkThickness': 1.4,   # meadow oaks carry a thick, flared trunk
    'crownShape': 2,         # hemispherical: the LOWEST limbs are the longest -> broad dome
    'branchDensity': 24,     # fewer, heavier scaffolds than the preset's 26
    'branchAngle': 64,       # spreading, not drooping (74 laid a limb on the grass)
    'gnarliness': 80,
    'leafSize': 0.38,        # near real leaf size (the preset's 0.6 m cards read as giant leaves)
    'leavesPerBranch': 24,
    'paramOverrides': {
        'length': {1: 0.56, 2: 0.46, 3: 0.4},   # long scaffolds: crown wider than tall
        'branches': {2: 18, 3: 12},             # the 4th order needs children (0 in the preset = leafless)
        'downAngle': {3: 45},
        'curveV': {3: 60},
    },
}
