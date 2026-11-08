"""Probe: a book from a PDF (eidoblend.media.book, pdf=): the janus "Simulacra and Simulators" PDF, 351 pages.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media/test_book_pdf.py

pymupdf (system Python) rasterises the pages, Pillow composes the spreads, the rig sizes the leaf count and the
thickness from the page count; the book opens in the middle of the document (page 60) and turns a leaf.
Stills: out/book_pdf_f024.png (open), out/book_pdf_f036.png (mid-turn).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import book  # noqa: E402

OUT = S.OUT
J = S.ASSETS / 'book_janus'
sc = S.fresh_scene(frames=(1, 44))
sc.eevee.shadow_ray_count = 4
sc.eevee.shadow_step_count = 12
plan = book.schedule((1, 44), open=[(1, 0.0), (20, 1.0)], page=60, turns=[(28, 44)])
b = book.make_book(OUT / 'book_pdf_work', plan, size=(0.16, 0.23, None), pdf=J / 'simulacraAndSimulators.pdf',
                   cover={'wrap': J / 'wrap_basecolor.jpg', 'color': '#5a1218'}, lining=J / 'lining.jpg',
                   edges=J / 'page_edges.jpg', pdf_page_height=900)
m = b.metrics
print(f'[pdf] {b.info["spreads"]} spreads, {m["N_LEAF"]} leaves, thickness {2 * m["HALF_T"] * 1000:.1f} mm, '
      f'maxPage {b.info["maxPage"]}, leaf verts {len(b.parts["leaves"].data.vertices)}')
S.box(sc, 'desk', (1.4, 0.9, 0.04), (0.05, 0.1, -0.02),
      S.pbr_material('desk_wood', S.cached('textures', 'Planks039_2k'), scale=1.4))
b.root.rotation_euler.z = -0.08
S.area_light(sc, (-0.6, -0.4, 0.75), (0, 0, 0), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
S.camera(sc, (0.02, -0.36, 0.40), (0.0, 0.005, 0.0), lens=35)
for f in (24, 36):
    st = b.frame_state(f)
    print(f'[pdf] frame {f}: page {st["page"]} turn {st["turn"]} slots', [(s['recto'], s['verso']) for s in st['slots']])
    S.render_still(sc, f, OUT / f'book_pdf_f{f:03d}.png')
print('[test_book_pdf] done')
