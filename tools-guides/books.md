# Books, covers, spreads and PDFs

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The renderer injects `BookCore` and the two scene adapters in `book.js`.
Use `makeBookFromSpec` for a book defined by dimensions and images. It is async.
Use `makeBook(gltf)` for a compatible authored book asset; it expects named
`board_front` and `board_back` meshes, not an arbitrary rectangular GLB.

```js
// In setup(); cover_front and spread_0 are declared image assets.
const book = await makeBookFromSpec({
  size: {width: 0.16, height: 0.23, thickness: 0.025},
  cover: {front: ASSETS.cover_front, color: '#264f54'},
  spreads: [ASSETS.spread_0]
});
_s.add(book.root);
book.layFlat();
book.setOpen(1);
```

`cover` accepts a texture, `{wrap}`, or separate `{front, back, spine, color}`
images. `lining` and `edges` accept a texture or color. A spread is a two-page
image; the adapter composes separate cover images into the proper wrap.
Keep authored text orientation and image aspect ratios.

## Drive the book from media time

- `setOpen(0..1)` controls the opening.
- `setPage(index)` chooses a page turn; `poseTurn(0..1)` poses that turn.
- `riffle(t, {start, secondsPerPage})` drives a sequence from media time.
- `await loadSpreads(images)` replaces the spread images.
- `root`, `seatBox`, `frames`, `metrics`, `page`, `maxPage`, `spreadCount` and
  `openAmount` expose placement and state. Inspect the available range.

Use one page-turn driver at a time. `update()` is a compatibility no-op; it
does not advance a book by itself. The current rig uses GPU-posed leaves, so
do not recreate pages or rewrite their vertices in each frame. Place the book
using its actual dimensions and verify cover, page and table contact while
opening and turning.

## Read a PDF

```js
const book = await makeBookFromSpec({
  pdf: ASSETS.document_pdf,
  pdfPageHeight: 1200,
  size: {width: 0.16, height: 0.23},
  cover: {front: ASSETS.cover_front, color: '#264f54'}
});
_s.add(book.root);
```

The current PDF adapter accepts raw bytes or a filename. It requires Python
with `pymupdf`; `BOOK_PYTHON` selects the executable. It rasterizes pages once
to temporary files, then loads a window of spreads around the current opening.
Without an explicit thickness it estimates one from the bound page count.
The current binding caps document capacity at 1,000 pages; inspect `maxPage`
rather than animating beyond it. Scanned spread images avoid the PDF dependency.

`BookCore.makeBookRig(THREE, spec, materials, hooks)` is the lower-level rig
for toolkit maintenance. Scene work should normally use the adapters, which
prepare NodeMaterials, page images and paper lighting consistently.
