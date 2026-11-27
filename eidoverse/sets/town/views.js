// eidoverse/sets/town/views.js — lenses on a built town, in its own metres (+Z up), as the Blender edition frames them:
// [name, pos, target, lens mm] (target null: straight down, the image's top toward -x). aim() points a three.js camera
// through the town's root (the Blender lens's horizontal field on a 36 mm sensor, as a vertical fov for the aspect).
//
//   over_the_main_road_24mm      from 71 m over the main road, looking ahead and down along it
//   straight_down_70m_30mm       straight down from 70 m onto roofs, yards and washing
//   pull_back_35mm               from 82 m, the town opening out under a long slant
//   across_to_the_edge_40mm      from 79 m at the west end, low over the roofs toward the far side
//   street_level_main_road_28mm  standing on the main road's pavement
//   roofs_at_a_slant_45mm        from 32 m over a block, its roofs and what lives on them
//   the_edge_from_60m_35mm       the town's edge thinning out along its tracks
//   a_road_end_into_the_plain_35mm   the main road's east end, where its asphalt goes under the track and the plain
// and, found where the town put them: a block of shops from across the road, a roof and what is on it, a low house and
// its yard.
const BASE = [['over_the_main_road_24mm', [150.0, 2.0, 71.0], [118.0, 0.0, 0.0], 24],
    ['straight_down_70m_30mm', [60.0, 1.0, 70.0], null, 30],
    ['pull_back_35mm', [40.0, -30.0, 82.0], [5.0, 0.0, 60.0], 35],
    ['across_to_the_edge_40mm', [-225.0, -13.0, 79.0], [-200.0, 0.2, 71.1], 40],
    ['street_level_main_road_28mm', [130.0, -17.5, 1.7], [95.0, -11.0, 4.0], 28],
    ['roofs_at_a_slant_45mm', [30.0, -48.0, 32.0], [4.0, -8.0, 8.0], 45],
    ['the_edge_from_60m_35mm', [300.0, 60.0, 60.0], [420.0, 190.0, 0.0], 35]];

// [[name, pos, target, lens]] for a town plan (layout.plan's result)
export function views(plan) {
    const [ex, ey] = plan.extent;
    const sx = ex / 840.0, sy = ey / 300.0;
    const s = (p) => (p === null ? null : [p[0] * sx, p[1] * sy, p[2]]);
    const out = BASE.map(([n, p, t, L]) => [n, s(p), s(t), L]);
    const px = plan.paved[0];                                        // the main road where its asphalt ends in the plain
    const ym = plan.ystreets.reduce((m, q) => (q[1] > m[1] ? q : m))[0];
    out.push(['a_road_end_into_the_plain_35mm', [px - 70.0, ym - 24.0, 16.0], [px - 8.0, ym, 0.0], 35]);
    const blds = plan.placements.filter((o) => o.kind === 'buildings' && o.tn.in);
    const nearest = (prefix, x, y) => {
        let best = null, bd = Infinity;
        for (const o of blds) {
            if (!o.mesh.startsWith(prefix)) continue;
            const d = Math.hypot(o.loc[0] - x, o.loc[1] - y);
            if (d < bd) { bd = d; best = o; }
        }
        return best;
    };
    const frame = (o) => {                                           // a building's middle, its front's direction, its size
        const f = Math.abs(o.rot[2]) < 0.1 ? -1.0 : 1.0;
        const { w, d, h } = o.tn;
        return [[o.loc[0] - f * w / 2, o.loc[1] - f * d / 2, 0.0], f, w, d, h];
    };
    let o = nearest('town_A_', 30.0 * sx, -6.0);
    if (o) {
        const [c, f, w, d, h] = frame(o);
        out.push(['shop_fronts_from_across_the_road_30mm', [c[0] + 5.0, c[1] + f * (d / 2 + 13.0), 2.6], [c[0], c[1] + f * d / 2, 3.0], 30]);
        out.push(['a_roof_and_what_is_on_it_40mm', [c[0] + w / 2 + 5.0, c[1] + f * (d / 2 + 6.0), h + 8.5], [c[0], c[1], h + 0.6], 40]);
    }
    o = nearest('town_C_', 20.0 * sx, 60.0 * sy);
    if (o) {
        const [c, f, w, d, h] = frame(o);
        out.push(['a_low_house_and_its_yard_35mm', [c[0] - w / 2 - 9.0, c[1] + f * (d / 2 + 12.0), h + 9.0], [c[0], c[1], h * 0.5], 35]);
    }
    return out;
}

// a three.js camera through the town's root (root: the town's group, carrying its +Z-up metres into the world)
export function aim(THREE, camera, root, pos, target, lens, aspect = camera.aspect) {
    root.updateMatrixWorld(true);
    const M = root.matrixWorld;
    const p = new THREE.Vector3(...pos).applyMatrix4(M);
    camera.position.copy(p);
    const hf = 2 * Math.atan(18.0 / lens);
    camera.fov = 2 * Math.atan(Math.tan(hf / 2) / aspect) * 180 / Math.PI;
    camera.updateProjectionMatrix();
    if (target === null) {
        camera.up.set(-1, 0, 0).transformDirection(M);               // straight down, the image's top toward -x
        camera.lookAt(new THREE.Vector3(pos[0], pos[1], 0.0).applyMatrix4(M));
    } else {
        camera.up.set(0, 0, 1).transformDirection(M);
        camera.lookAt(new THREE.Vector3(...target).applyMatrix4(M));
    }
    camera.up.set(0, 1, 0);
}
