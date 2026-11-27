// eidoverse/sets/wake_another_one/hall/carton.js — the hall's two-part carton: a port of the Blender edition's
// eidoblend.sets.wake_another_one.hall.carton.
//
//   const CT = build(layout.carton);   // -> { meshes: { carton_base, carton_collar, carton_hood, carton_insert },
//                                      //      sets: { tray, hood, closed } (mesh names), meas }
//
// A plain shipping carton of layout.json's measures, in the tray's frame (its floor's centre at the origin, +x the
// left of whoever stands in it, -y its front, z up):
//   the TRAY   the lower part: four walls of board to the seam with a floor, a collar inside them that stands up past
//              the seam to the rim (the hood comes down over it), and a moulded insert: a ledge at the rim's height
//              and a pocket down to the height of body_mark, where a body stands or kneels
//   the HOOD   the upper part: four walls and a top, from the seam to the carton's full height
//   CLOSED     the tray with its hood on
// Board and insert are two materials (carton_board, carton_insert). No print, no marks.
import { MB } from './kit.js';

// an open box of board t thick (open on 'top' or 'bottom'), ONE closed shell: its outside, its inside and its rim
function shell(name, lo, hi, t, openSide, mat) {
    const [x0, y0, z0] = lo, [x1, y1, z1] = hi;
    const o = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
    let i, faces;
    if (openSide === 'top') {
        i = [[x0 + t, y0 + t, z0 + t], [x1 - t, y0 + t, z0 + t], [x1 - t, y1 - t, z0 + t], [x0 + t, y1 - t, z0 + t],
            [x0 + t, y0 + t, z1], [x1 - t, y0 + t, z1], [x1 - t, y1 - t, z1], [x0 + t, y1 - t, z1]];
        faces = [[0, 3, 2, 1], [8, 9, 10, 11]];                       // the floor, out and in
        for (let k = 0; k < 4; k++) {
            const j = (k + 1) % 4;
            faces.push([k, j, 4 + j, 4 + k], [8 + k, 12 + k, 12 + j, 8 + j], [4 + k, 4 + j, 12 + j, 12 + k]);   // outside, inside, rim
        }
    } else {
        i = [[x0 + t, y0 + t, z0], [x1 - t, y0 + t, z0], [x1 - t, y1 - t, z0], [x0 + t, y1 - t, z0],
            [x0 + t, y0 + t, z1 - t], [x1 - t, y0 + t, z1 - t], [x1 - t, y1 - t, z1 - t], [x0 + t, y1 - t, z1 - t]];
        faces = [[4, 5, 6, 7], [12, 15, 14, 13]];                     // the top, out and in
        for (let k = 0; k < 4; k++) {
            const j = (k + 1) % 4;
            faces.push([k, j, 4 + j, 4 + k], [8 + k, 12 + k, 12 + j, 8 + j], [k, 8 + k, 8 + j, j]);           // its rim at the bottom
        }
    }
    const mb = new MB();
    mb._quads([...o, ...i], faces, 0);
    return mb.mesh(name, [mat]);
}

// the moulded insert: a ledge ring at zTop between the outer and inner squares, the pocket's walls down to zFloor,
// its floor (wound as the Blender edition winds it: no recalculation)
function insert(name, outer, inner, zTop, zFloor) {
    const sq = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    const pts = [...sq.map(([sx, sy]) => [sx * outer, sy * outer, zTop]), ...sq.map(([sx, sy]) => [sx * inner, sy * inner, zTop]),
        ...sq.map(([sx, sy]) => [sx * inner, sy * inner, zFloor])];
    const faces = [];
    for (let k = 0; k < 4; k++) {
        const j = (k + 1) % 4;
        faces.push([k, j, 4 + j, 4 + k], [4 + k, 4 + j, 8 + j, 8 + k]);
    }
    faces.push([8, 9, 10, 11]);
    const mb = new MB();
    mb._quads(pts, faces, 0);
    return mb.mesh(name, ['carton_insert'], false);
}

export function build(C) {
    const [sx, sy, sz] = C.size;
    const hx = sx / 2.0, hy = sy / 2.0;
    const t = C.wall, seam = C.seam_z, rim = C.rim_z;
    const cin = hx - t - 0.0005;
    const meshes = {
        carton_base: shell('carton_base', [-hx, -hy, 0.0], [hx, hy, seam], t, 'top', 'carton_board'),
        carton_collar: shell('carton_collar', [-cin, -cin, seam - 0.12], [cin, cin, rim], 0.004, 'top', 'carton_board'),
        carton_hood: shell('carton_hood', [-hx, -hy, seam], [hx, hy, sz], t, 'bottom', 'carton_board'),
        carton_insert: insert('carton_insert', C.insert.outer, C.insert.inner, rim - 0.004, C.body_mark[2]),
    };
    return {
        meshes,
        sets: { tray: ['carton_base', 'carton_collar', 'carton_insert'], hood: ['carton_hood'], closed: ['carton_base', 'carton_collar', 'carton_hood'] },
        meas: { size: [sx, sy, sz], seam_z: seam, rim_z: rim, hood_height: Math.round((sz - seam) * 1e4) / 1e4, tray_floor_z: C.body_mark[2] },
    };
}
