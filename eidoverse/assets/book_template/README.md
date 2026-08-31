# book template — bring your own book

Any book, in either eidoverse, from a folder of images — or a PDF and cover
art. No 3D work: the rig (case binding, skinned page-turning leaves) is
generated; you supply artwork.

**Orientation is automatic.** Author every panel upright, exactly as you'd
see it looking at the closed book from outside — front and back as
portraits, spine as its tall strip. The composer owns every flip.

## The fastest path: a PDF

Give it your document and covers; page count, spreads, and paging come from
the PDF (any length — only the spreads near the open page are ever decoded):

```js
// video
const book = await globalThis.makeBookFromSpec({
    size: { width: 0.135, height: 0.20, thickness: 0.075 },
    pdf: ASSETS.pdf,                       // scene asset — any page count
    cover: { front: ASSETS.front, back: ASSETS.back, spine: ASSETS.spine,
             color: '#1e4d2b' },
    lining: ASSETS.lining, edges: ASSETS.edges,
});
```

```
# worlds — same idea, URLs instead of scene assets
comp {id: "book1", type: "book", data: {
       size: {width: 0.135, height: 0.20, thickness: 0.075},
       pdf: "/library/…/mybook.pdf",
       cover: {front: "/library/…/front.png", color: "#1e4d2b"},
       open: 0, page: 0}}
```

Leaf count follows the PDF (capped ~40; longer documents page through a
virtual window on the same leaves). `pdfPageHeight` (default 1200 px) sets
rasterization sharpness.

## The slots

| file          | what it is                          | orientation                | fallback |
|---------------|-------------------------------------|----------------------------|----------|
| `front.png`   | front cover art                     | upright, as printed        | `cover.color` cloth |
| `back.png`    | back cover art                      | upright, as printed        | dimmed front echo |
| `spine.png`   | spine strip                         | TALL, text running head→tail | `cover.color` cloth |
| `lining.png`  | endpaper (case interior)            | upright, LANDSCAPE — spans the whole opened interior (both boards + spine) as one unstretched field inside the cloth border; aspect ≈ (2×width + spine) : height | plain cream |
| `edges.png`   | the block's cut edges (speckle)     | small tile                 | plain stock |
| `spread_NN.*` | two-page scans, in reading order    | left page \| right page, top up | plain stock pages |

Covers may be ANY aspect — they are fitted to the board you specify. Spreads
are best ~2:1.4 (two pages side by side). All slots except `size` optional.

## eidoverse-video (film scenes)

```js
const book = await globalThis.makeBookFromSpec({
    size: { width: 0.15, height: 0.222, thickness: 0.026 },   // metres, closed
    pages: 26,                       // leaf count (visual thickness of block)
    cover: { front: ASSETS.front, back: ASSETS.back, spine: ASSETS.spine,
             color: '#8a1420' },     // cloth color: trim, rims, gaps
    lining: ASSETS.lining, edges: ASSETS.edges,
    spreads: [ASSETS.spread_00, ASSETS.spread_01 /* … */],
});
book.layFlat(); scene.add(book.root);
book.root.position.y += -book.seatBox().min.y;   // seat on the floor/desk
book.setOpen(1);                                  // 0..1
book.setPage(3);                                  // jump to a spread
book.poseTurn(0.5);                               // scrub the next leaf mid-flight
book.riffle(t, { start: 5, secondsPerPage: 1.2 }); // or timed turns for a film
```

Alternatively `cover: { wrap: ASSETS.wrap }` supplies the full arc-length
wrap (back | spine | front in one image, the janus-asset layout).

## eidoverse-worlds (interactive, persistent)

The zero-config path: `comp {id: "book1", type: "book", data: {}}` builds
THE DEFAULT BOOK — janus's simulacra, full art and spreads. Supplying any
cover/spreads/pdf replaces it with your own.

For a custom book, serve the images (the video repo's files are already at
`/library/...`; `POST /upload` works too), then author the component + bind
the keeper:

```
spawn {id: "book1", lib: "<any small anchor>", pos: [x, y, z]}
comp  {id: "book1", type: "book", data: {
        size: {width: 0.15, height: 0.222, thickness: 0.026},
        cover: {front: "/library/…/front.png", back: "/library/…/back.png",
                spine: "/library/…/spine.png", color: "#8a1420"},
        lining: "/library/…/lining.png",
        spreads: ["/library/…/spread_00.jpg", …],
        pages: 26, open: 0, page: 0}}
behavior {id: "book1keeper", src: <upload of sdk/examples/bookkeeper.js>,
          attach: "book1"}
```

Anyone can then `/use book1` (toggle), `/use book1 next`, `/use book1 prev` —
state folds into the log, so late joiners see the book open at the right
page. The anchor model hides while the comp is attached.

## The empty-case test

Hide the leaves (`book.leaves.forEach(l => l.mesh.visible = false)`) and open
the case: the interior must read as ONE pasted paper field across both boards
and the spine, framed by cloth on all four sides, your endpaper art upright
and unstretched. `work/book_norm/bare.js` renders exactly this.

## Acceptance

`work/book_norm/` is the acceptance battery: adversarial art (bold back
cover, labeled endpaper) + `scene.json` (visual sweep) + `scene_audit.json`
(raycast battery: pastedown clearances, cover-over-page, leaf spacing,
spine escape through opening and mid-turn). A change to the rig should keep
that audit green and those renders readable.

The example files in this folder are the labeled test panels — replace them
with your art, keep the names.
