# Books, covers, spreads and PDFs

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender edition. The hardcover rig is the engine's own
`eidoverse/book_core.js`, unchanged: a case binding skinned along one strip of
bookcloth, leaves that turn as inextensible arcs, the mull that ties the block
to the case, three textured window leaves around the opening. `eidoblend.media.book`
runs it in Deno (`blender/eidoblend/media/js/book_export.mjs`), poses it on
every frame of a schedule, and builds the book in Blender: one mesh per part
with a Mesh Cache (PC2) modifier and native materials. Nothing runs at render
time.

```python
from pathlib import Path
from eidoblend.media import book

plan = book.schedule((1, 120), open=[(1, 0.0), (30, 1.0)], turns=[(40, 58), (70, 88)])
b = book.make_book('work/<id>/book', plan, size=(0.15, 0.222, 0.026),
                   cover={'front': 'eidoverse/assets/book_template/front.png',
                          'back': 'eidoverse/assets/book_template/back.png',
                          'spine': 'eidoverse/assets/book_template/spine.png', 'color': '#1e4d2b'},
                   spreads=sorted(Path('eidoverse/assets/book_spreads').glob('*.jpg')),
                   lining='eidoverse/assets/book_template/lining.png')
b.root.location = (0.0, 0.0, desk_top)      # the closed book's underside sits on z = 0 of its root
```

`size` is the closed book in metres (width, height, thickness); a thickness of
`None` is estimated from the pages, as `makeBookFromSpec` does. The book lies
on its back board, spine toward −X, as the rig's `layFlat` laid it (three's
axes mapped to Blender's: (x, y, z) → (x, −z, y)). Rotate `b.root` to place
it. Measured 11-07 (`blender/tests/media/test_book.py`): the Mesh Cache reads
back the exported pose exactly, and the underside stays within 0.13 mm of the
desk while the book opens (the rig rides on its own spine).

## Drive the book from the film's frames

A schedule is one state per frame: `{f, open, page, turn, wad}`, or
`{f, open, riffle: {...}}`. Build it with:

- `book.schedule(frames, open=[(frame, 0..1), …], page=0, turns=[(f0, f1), …],
  back_turns=[…], wad=1)`: `open` keys are eased between; each forward turn
  flies the next leaf over `f0 … f1` and lands it (page + 1 from `f1`); `wad`
  sheets fly together for a bulk skip.
- `book.riffle_schedule(frames, start, seconds_per_page=1.2,
  turn_fraction=0.72)`: `rig.riffle`, the timed sequential turns.

Or write the list yourself. One driver per frame, as in the engine. The export
belongs to its schedule: change the timing, run `make_book` again (about a
second for a 17-leaf book over 60 frames).

`b.states` reports each frame's page, open amount, turn phase, cover side, the
window slots' spreads and the lowest point. The facade's getters read it per
film frame: `b.page_at(f)` is `page`, `b.open_amount(f)` is `openAmount`
(0 shut … 1 open), and `b.max_page`, `b.spread_count`, `b.metrics` are as in
the engine. (`make_book(open_at=…)` is the rig's `openAt` option, the leaves
already on the left: a build option, not a per-frame state.)
`b.page_turn_events()` returns `[{t, clip, gain}]` at each turn's start, for
`audio.place_events` or a mix's event list (`eidoverse/assets/book_sfx/` holds
the recorded page sounds).

`b.frames` is `rig.frames`: `{'case_frame', 'page_frame'}`, the rig's two
coordinate frames as empties under `b.root`, keyed (LINEAR) on every frame of
the schedule. They keep the engine's local axes: `case_frame` runs X along the
cross-section (back fore-edge → spine → front fore-edge), Y out through the
front cover and Z along the turning axis, with its origin at the back board's
fore-edge on the back cover's outer face; `page_frame` sits at the gutter.
Parent a prop to one, or read a point in its axes with
`b.frames['case_frame'].matrix_world.inverted() @ p`. Measured 11-07 on the
janus book, closed: `case_frame`'s origin on the fore-edge (0.00 mm) and
0.18 mm above the underside, its Z along the spine; `page_frame` inside the
block at the gutter, 155 mm from the fore-edge.

## Covers, linings, edges and spreads

- `cover`: `front`, `back`, `spine` images, each authored upright as seen on
  the closed book, composed into the arc-length wrap by the rig's own
  composer (`composeWrapTexture`), so the art lands where the strip's
  coordinate puts it; `color` is the plain cloth on the rims and turn-ins.
  Or `{'wrap': <a full arc-length wrap>, 'color': …}`.
- `lining` (the endpaper) and `edges` (the cut edges): an image or a hex.
- `spreads`: two-page images in reading order, left page | right page, top up
  (resized to the first one's size). A window leaf's recto shows the right
  half of spread V − 1 + w and its verso the left half of the next, exactly
  as the engine's window does: the three leaves sample one image sequence
  (file 0 blank paper, file k spread k − 1) whose frame offset is keyed to the
  page.

Materials are Blender's own: bookcloth with sheen and a fine weave bump, the
plain trim, the lining, the edges, the kraft inlay and the cotton mull (both
textures drawn by the rig itself and exported), and paper with translucency
(a thin slab), so the underside of a lifting leaf is lit, which the engine
faked with an emissive glow.

## Read a PDF

```python
J = 'eidoverse/assets/book_janus/'
plan = book.schedule((1, 44), open=[(1, 0.0), (20, 1.0)], page=60, turns=[(28, 44)])
b = book.make_book('work/<id>/book', plan, size=(0.16, 0.23, None), pdf=J + 'simulacraAndSimulators.pdf',
                   cover={'wrap': J + 'wrap_basecolor.jpg', 'color': '#5a1218'},
                   lining=J + 'lining.jpg', edges=J + 'page_edges.jpg', pdf_page_height=900)
```

The system Python's pymupdf rasterises the pages (`BOOK_PYTHON` picks the
executable, as before; height `pdf_page_height`, default 1200 px) and Pillow
composes the spreads: spread 0 is blank | page 1. Leaf count and thickness
follow the page count as in `makeBookFromSpec` (the binding holds up to 502
leaves). Measured 11-07 (`test_book_pdf.py`): the 351-page janus PDF became
176 spreads on 178 leaves, 25.6 mm thick; opened at page 60 it shows PDF
page 120 ("gpt-3 on coherent extrapolated volition") on the right and the
blank page before that chapter on the left, exactly the document's own
order. The whole build took 17 s. A long document is a heavy cache: 178
leaves are 42 k vertices a frame in the leaves' PC2 (about 0.5 MB a frame),
502 leaves 118 k.

## A book from a GLB — `makeBook(gltf)`

The janus book ("simulacra and simulators", crimson bookcloth) is a modelled
asset with its own wrap, normal and ORM maps. `makeBook(gltf)` measured such
an asset into the rig's spec and dressed the rig in the asset's own
materials. `make_book(gltf=...)` does the same:

```python
GLB = 'eidoverse/assets/models/simulacra_and_simulators_book_janus_repligate_crimson_bookcloth_hardcover_readable_pages.glb'
plan = book.schedule((1, 72), open=[(1, 0.0), (24, 1.0), (56, 1.0), (72, 0.0)], turns=[(32, 50)],
                     side=[(1, 'front'), (56, 'back')])
b = book.make_book('work/<id>/janus', plan, gltf=GLB, spreads=sorted(Path('eidoverse/assets/book_spreads').glob('*.jpg')),
                   name='janus')                     # pages=26, open_at=1, angle=180, page_angle=179, page_glow=0.55
b.root.location = (0.0, 0.0, desk_top)
```

- **The measure** (`book.measure_book_glb(root)`, also callable on its own)
  reads the boards, spine and wrap off the glTF importer's objects, as
  `book.js` did:
  - `halfT` and `halfH` come from the whole asset's bounds;
  - `jointX` and `foreX` from the back board;
  - `lip` and `round` from the spine's outline at its edge and apex;
  - `uJoint` from the back board's largest u.
- **The materials** are copies of the asset's own:
  - `case_cloth` is the cloth, with its wrap, normal map and ORM roughness
    wired as the importer made them, and is also the double-sided trim;
  - `case_inner` is the lining and `page_edges` the cut edges;
  - `page_spread`'s roughness goes on the paper.
  - The asset's images read the importer's v-flipped UV layer, which the rig's
    case carries as a second layer (`UVMap_gltf`), and its tangents too.
- **The asset itself** rides with the rig, laid flat as `layFlat()` laid it.
  Its source pieces (boards, spine, block, pages) stay hidden as `b.source`,
  for measuring and seating, as the engine kept them.
- **The options** are the engine's: `pages` (26), `open_at` (1), `angle` (the
  case's sweep, 180), `page_angle` (where a turned leaf lies, 179),
  `page_glow` (0.55: the engine's emissive glow becomes translucency, 0.4 ×
  page_glow).
- **The schedule** works as for any book. `side` picks which cover the open
  amount swings: 'back' closes the back cover over the block, so the finished
  book lies front-cover-down.

The rig's other surfaces:
- `b.page_materials()` returns the stock paper, then each window leaf's recto
  and verso;
- `b.edge_material` is the cut edges' material;
- `b.code_surfaces()` is `rig.codeSurfaces()`, for debugging: every surface a
  flat primary, so a render names the surface it shows (cloth red, lining
  blue, case rim cyan, recto green, verso yellow, leaf edges magenta, stock
  paper dark green). It is gated as `makeBook`'s facade gated it: it codes
  only a book made with `make_book(..., code=True)` (`opts.code`), or every
  book while `book.CODE_SURFACES = True` (`globalThis.__CODE_SURFACES`).
  Otherwise it changes nothing and returns False, so a scene can leave the
  call in;
- `b.code_surfaces(False)` puts the real materials back.

Measured 11-07 (`blender/tests/media2/test_book_glb.py`):
- **The measure:** the engine's own `makeBook` (book.js in Deno,
  `book_glb_parity.mjs`) and `measure_book_glb` read the same eight numbers
  off the GLB: halfT 0.01322, halfH 0.11095, boardLen 0.1504, jointX 0.0727,
  lip 0.005585, round 0.002415, uJoint 0.4573, foreX 0.0777.
- **The fit:** the closed rig matched the asset's own boards and spine to
  0.50 mm in bounds; the seat box's underside sat at −0.02 mm; the underside
  never sank below −0.13 mm as the book opened, turned and closed.
- **The film:** 16 spreads went on 26 leaves (max page 15). It opened by
  frame 24, turned a leaf over frames 32–50, and closed the back cover over
  the block from frame 56. `out/book_glb_sheet.png` shows the asset beside
  the closed rig, the film, and the colour-coded surfaces mid-turn.

## Rendering

- Soft light across thin paper: raise EEVEE's shadow rays. At 16 samples
  Blender's default (1 ray, 6 steps) stippled the turning leaf's penumbra on the
  page beneath. `scene.eevee.shadow_ray_count = 4` with
  `shadow_step_count = 12` reduces the grain a lot but does not clear it: a
  faint grain stays in the shadowed band beside the spine at 16 samples (11-07,
  `book_pdf_stipple_variants.png`). It is shadow sampling, not GI. Neither 16
  steps, nor a light `shadow_filter_radius` of 3, nor turning raytracing or fast
  GI off changed it. More render samples are the remaining lever; that is not
  measured here, because probes stay at 16.
- Paper has no bump: a 0.25 mm tooth is sub-pixel at reading distance.
- Check cover, page and desk contact through the whole move, in motion.

## Not yet ported

- Pick boxes and the interactive book UI (`leafField.pickL / pickR`): they
  serve clicking in a live page and have no use in a film.
- The live texture window, superseded: the spread sequence keyed to the page
  replaces it.
- A Python rewrite of the solve: not needed, because the bridge runs the
  reviewed JS (`book_core.js`) instead.
- `make_book(rig={...})`, a raw `makeBookRig` spec with no GLB, is accepted by
  the exporter but no probe has rendered it. The GLB path builds its spec the
  same way and is rendered.
