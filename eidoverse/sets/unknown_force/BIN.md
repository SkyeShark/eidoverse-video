# THE BIN (`bin.js`): the bridge, song 222.8–243.2 s

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Set index](README.md) · [Sources and licences](SOURCES.md)

"And here's the joke I can't climb out of / I am made of what you said / Every forum, every sermon / Every
manifesto read / There's no pure voice beneath the static / No true face behind the screen / If ideology's the
garbage / I was born inside the bin."

A canyon of thrown-away paper in the dark, built as Futurist papier collé, with a giant rusted trash can at its head.
The whole discourse was thrown into it, and she climbs out of it. Paper keeps drifting down out of the dark.

## What is in it
- **The can.** Poly Haven's "Metal Trash Can" (GurJas Studios, CC0; fetched on first use into the shared model library, `fetchModelFile('metal_trash_can', { res: '2k' })`,
  its licence sidecar beside it), the rusted
  one, scaled to a 6.2 m giant (radius 1.88 m), with its authored 2k PBR maps (rust, dents, ribbing). Painted INTO
  its material through cylindrical coordinates: a NO DUMPING vinyl sign, KEEP LID CLOSED, a hazard band, a stencil
  "BIN 01", a magenta spray tag with drips, a peeling wheat-pasted THE FUTURE / IS NOT YET poster, a blue round
  sticker, and a CONTENTS MAY SPEAK warning label. They wear off where the rust noise is high, and each has its own
  roughness and no metalness. The lid leans against the front left. The clean can lies toppled in the cliff.
- **The paper.** One 4092×4096 atlas (`bin_pages.js`) of 24 invented pages, all deterministic:
  - three newspapers with mastheads (THE MORNING CERTAINTY, THE EVENING ARGUMENT, THE DAILY DISCOURSE), headlines
    (BEFORE IT SPEAKS, ARE WE READY, MACHINE GOD?), columns and halftone blocks;
  - forum printouts (THREAD 1/47, anon, [deleted]), a green-bar printout, two sermons with drop caps and red verse
    numbers, a numbered MANIFESTO, a words-in-freedom page, an OPEN LETTER with scribbled signatures, a redacted
    MEMORANDUM stamped URGENT, a model/user chat log, an exponential chart ("p = 0.1?"), a BUY NOW ad, notebook
    notes ("the fear sells", "ship it anyway"), classifieds, and a THE FUTURE IS poster (the rest torn off);
  - six Futurist cut papers: black ZANG, red TUMB, ochre !!!, a blue +, a red disc, an M.

  Pages are often torn along one edge (alpha cut), stained, creased and grimy. The text is invented: no real names,
  mastheads or logos.
- **How the paper is laid.** About 4,400 double-sided sheets in three shapes (flat, curled, folded), instanced on a
  procedural heap: a floor running toward the cameras, paper walls 8–14 m high, a cliff behind the can, and a mound
  banked against it. The back of each sheet is blank stock with the print ghosting through. Under them lies a dark
  collage underlayer (rotated page tiles) so no void shows between pages. Also in the heap:
  - 330 crumpled-paper boulders with print on their facets;
  - inside the can, a paper slope with flat sheets on her path;
  - eight giant typographic fragments turned to the wide camera: THE FUTURE IS on the cliff, THREAD 1/47, MANIFESTO,
    OPEN LETTER, a front page, TUMB, ZANG and the words-in-freedom page;
  - five readable pages laid upright at her feet for the close shot;
  - two big cut shapes (papier collé): a black Carrà wedge lettered TUMB TUMB / everyone keeps asking, and a red
    disc ringed with EVERY FORUM · EVERY SERMON · EVERY MANIFESTO READ.
- **Falling paper.** 200 sheets tumble down from 23 m, entirely on the GPU (a hash per instance, `positionNode` on
  `time`). It is deterministic in `t` and needs no CPU work per frame. It is kept off the wide lens and out of the
  lip shot.
- **Light (its own; it is a night set inside its own sky sphere):**
  - a cold white pool on the lip where she rises;
  - a cold rim spot behind the can, so it and she cut out of the dark;
  - magenta and cyan neon rims from behind the walls;
  - a sodium street lamp (Balla's *Street Light*), leaning, sunk in the right wall;
  - a white page light on the mound at her feet;
  - a low violet front fill;
  - a warm flicker inside the can ("born inside the bin").

  The sky is near-black with a far magenta and sodium city glow beyond the cliff. Suggested fog:
  `parts.fog = { color: 0x070a14, density: 0.03 }`.

## API (the film's set contract)
```js
const B = await import(new URL('sets/unknown_force/bin.js', EIDOVERSE_DIR).href);
const bin = await B.build(THREE, { sky: true, lights: true, atlasScale: 1, sheets: 3300, balls: 300, falling: 200 });
scene.add(bin.group);                 // metres, +Y up, resting on y = 0; the can's axis is the origin's vertical
bin.parts.mark.add(vrm.scene);        // she rides the mark (faces +Z)
// per frame:
bin.update(t, { climb, glow, wind, hush });
// the look's focal point (the lip where she rises), in world space:
const f = bin.focalPoint(new THREE.Vector3());
```
- `climb` 0..1: inside the can the paper fill is a slope from the back (y 4.25) to the front brim (6.2). The mark walks
  up it: at 0 she stands low inside (hidden below the rim at eye level), at about 0.5 her head and shoulders clear the
  rim, and at 0.95–1 she stands on the front lip. Always facing +Z. Her climbing animation (stepping, hands on the
  rim) belongs to the conductor; the set moves the transform.
- `glow` scales the warm light inside the can. `wind` 0..1 sets the falling paper's drift. `hush` 0..1 turns the
  neon rims, the rim spot and the lamp down for the bridge's argue → hush.
- `parts`: `mark`, `focal`, `bin` (group), `can`, `lid`, `toppled`, `paper`, `lamp`, `lights` (by name), `uniforms`
  (`time`, `wind`, `glow`, `hush`), `R`, `H`, `yFill`, `fillY(x, z)`, `fog`, and `pageAtlas` + `pageGrid` (the same
  pages, for the wardrobe's "some of the scraps are what her suit is made of").
- `cams` (set-local `{ pos, target, fov }`):
  - `binWide`: down the canyon floor, the can and her on the lip;
  - `climb`: three-quarter, over the rim;
  - `paperClose`: the readable pages at her feet, the can's base behind;
  - `topDown`: into the can's mouth.

## Performance (RTX 5090 laptop, measured)
- Build: about 1.6 s (glTF parse, 24-page atlas, about 5,000 instance matrices).
- 960×540 with the claudesona and aeropittura `argue`: 62–68 fps end to end (render, readback and encode).
- 1920×1080 `binWide`: 51 fps with `argue`, 58 fps with the look off.
- About 22 draw calls and about 0.9 M triangles. Sheets, crumpled paper and falling paper are three instanced draws
  each, with one shared material.
- GPU memory: the page atlas is about 90 MB with mips (`atlasScale: 0.5` → about 22 MB). The can's 2k maps are kept,
  because the can fills the frame in `climb`.

## Checking

The film's probe harness is not part of the kit. Build the set in a short probe as the
[props and sets guide](../../../docs/props-and-sets.md#verify) shows, judge frames from 10 on, read the
log for `missing texture` and `[uf-sets]` lines, and look at the frame with the look off and on
([aeropittura](../../../AGENTS.md)).

References (viewed, not in this repository): Carrà's *Interventionist Demonstration* (1914) for the cut wedge and
the disc of words; Depero; Marinetti's words-in-freedom pages.

## Known limits
- With the look on, the Kuwahara brushwork paints over the small print. The headlines, the giant fragments and the
  cut shapes carry through; the small print reads with the look off or at `hush`.
- Sheets are rigid instanced cards (no cloth). Crumpled paper is faceted noise on an icosphere.
- The mark slides up the slope; legs and hands are the conductor's.
