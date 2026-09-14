# Cloth — createClothPanel

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Mass-spring cloth panels (verified): flags, banners, curtains, capes,
hanging fabric. Pin any edge or corners; wind + gravity + box/sphere/floor
collision; per-vertex normals, so lit fabric folds shade correctly.

```js
const { createClothPanel } = await import(globalThis.EIDOVERSE_DIR + 'cloth_sim.js');
const cloth = await createClothPanel(renderer, {
    width: 3, height: 2.2, cols: 36, rows: 28,
    pin: 'top',            // 'top' | 'top-corners' | 'left' | [vertexIds] | (c,r)=>bool
    wind: 0.0004,          // GUST strength — 0.001 is already a strong gale
    windBias: 0.15,        // constant-push fraction of wind (see recipes)
    windDir: [0, 0, 1],    // push direction (panel local; face = ±Z)
    settleSteps: 60,       // pre-roll so frame 0 shows DRAPED fabric
    map: bannerTextureOrCanvas,   // graphic ON the fabric (see below)
    floor: 0,                     // ground plane — fabric won't sink through
    material: new THREE.MeshStandardNodeMaterial({ side: THREE.DoubleSide }),
});
cloth.mesh.position.set(0, 2.2, 0);
scene.add(cloth.mesh);
cloth.collideWith([booth, table]);             // fabric respects scene geometry
cloth.collideWith([character], { asSphere: true });
// per frame: cloth.step()
// move a pinned point (waving flag / cape on a moving character):
//   cloth.setPinPosition(vertexIndex, [x,y,z])
```

**Collision is opt-in — a cloth collides with nothing until
`cloth.collideWith([...])` registers geometry.** If the fabric hangs near
anything — a wall, ribs/battens, a sign, a pole, a booth, a screen frame, a
character — register it, or the cloth sways and billows straight through
whatever is behind it (the single most common cloth defect). A top-pinned
cloth flutters several centimetres, so give it clearance *and* register the
collider — the skin margin then holds it proud. Silencing the clipping audit
(`userData.noClippingCheck` / `allowIntersect`) only hides the warning; the
physics clip is still there until `collideWith` is wired.

`collideWith` auto-derives box colliders (`{ asSphere: true }` for round
things), up to 8 boxes + 8 spheres. The cloth rests `opts.thickness`
(default 3 cm — the collision skin) proud of every collider, which is what
stops blowing fabric from clipping in; raise it for thick/heavy fabric or
coarse cloth that still pokes through. For a cape or flag on a moving
character or prop, pass `{ track: true }` — colliders re-derive every
`step()`, no re-registering per frame. Collision resolves at vertex
resolution, so for a thin protrusion (a pole) keep `cols`/`rows` high or
bump `thickness`.

**Text or a logo on the fabric goes on the cloth's `map`** — composite it
into a canvas and pass it as `map` (or set `mat.map`). It rides the folds
and sway because the UVs are intact. A separate rigid plane floated in front
of the cloth detaches, z-fights, and doesn't move with the fabric.

**Pick wind by what the fabric is doing** — a hanging banner is not a flag:
- hanging banner / tapestry / curtain: `wind 0.0003–0.0006, windBias 0–0.2,
  settleSteps 60` → drapes and sways. Cranking wind "to add life" blows it
  horizontal toward `windDir` — the banner streams at the viewer as
  stretched streaks.
- streaming flag: `wind 0.0006–0.001, windBias 0.8–1.0`, `windDir` pointed
  where it should stream.

**Place flags with the stream in mind.** `pin: 'left'` hangs the panel off
its pole; the wind carries the free end a full panel-length along `windDir`,
and the cloth also drapes to near ground level below the pin. Budget that
whole swept volume when placing — a pole 2 m upwind of a showpiece drapes
the flag over it. Frame it like any prop: a flag near the dwell camera fills
the shot with fabric, one parked behind the camera disappears from the
scene. If a shot needs the flag out of the way, move the pole (a scene
decision) rather than adjusting the sim.
