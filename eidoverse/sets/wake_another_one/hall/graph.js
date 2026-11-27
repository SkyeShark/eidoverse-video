// eidoverse/sets/wake_another_one/hall/graph.js — the little of Blender's object model the hall's layout is written
// in: objects (a mesh by name, or none: an empty) with a parent, a place, a turn (Euler XYZ, radians) and a scale;
// collections; collection instances; point instancers (Geometry Nodes' Instance on Points, the source in its own
// space); and COPY_TRANSFORMS as a node whose world is another's. No three.js: the layout and its machines run here
// (the tests read them in plain deno), and hall.js flattens what is drawn into InstancedMeshes.
//
// Matrices are 4 x 4, column-major (three.js' Matrix4.elements order), in the hall's own frame (+Z up, metres).

export const M4 = {
    I: () => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    mul(a, b) {
        const o = new Array(16);
        for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
            o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
        return o;
    },
    // T x Rz Ry Rx x S (Blender's matrix_basis from location, rotation_euler XYZ, scale)
    compose(loc, rot, s) {
        const [x, y, z] = rot;
        const cx = Math.cos(x), sx = Math.sin(x), cy = Math.cos(y), sy = Math.sin(y), cz = Math.cos(z), sz = Math.sin(z);
        const r00 = cz * cy, r01 = cz * sy * sx - sz * cx, r02 = cz * sy * cx + sz * sx;
        const r10 = sz * cy, r11 = sz * sy * sx + cz * cx, r12 = sz * sy * cx - cz * sx;
        const r20 = -sy, r21 = cy * sx, r22 = cy * cx;
        return [r00 * s[0], r10 * s[0], r20 * s[0], 0, r01 * s[1], r11 * s[1], r21 * s[1], 0, r02 * s[2], r12 * s[2], r22 * s[2], 0, loc[0], loc[1], loc[2], 1];
    },
    // a frame from its three axes (columns) and its origin
    frame(x, y, z, o) { return [x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, z[0], z[1], z[2], 0, o[0], o[1], o[2], 1]; },
    T: (p) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, p[0], p[1], p[2], 1],
    apply: (m, p) => [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13], m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]],
    dir: (m, p) => [m[0] * p[0] + m[4] * p[1] + m[8] * p[2], m[1] * p[0] + m[5] * p[1] + m[9] * p[2], m[2] * p[0] + m[6] * p[1] + m[10] * p[2]],
    pos: (m) => [m[12], m[13], m[14]],
};

export class Node {
    constructor(name, { mesh = null, loc = [0, 0, 0], rot = [0, 0, 0], scale = [1, 1, 1], parent = null } = {}) {
        this.name = name; this.mesh = mesh; this.parent = parent;
        this.loc = [...loc]; this.rot = [...rot]; this.scale = [...scale];
        this.props = {}; this.inst = null; this.points = null; this.copy = null; this.driven = false;
        this.colls = []; this.hidden = false; this.shadowOnly = false; this.noShadow = false; this.outdoor = false;
        this._w = null; this._tick = -1;
    }
    local() { return M4.compose(this.loc, this.rot, this.scale); }
}

export class Scene {
    constructor() { this.objects = new Map(); this.colls = new Map(); this.tick = 0; this.drivers = []; }

    coll(name, parent = null) {
        if (!this.colls.has(name)) this.colls.set(name, { name, nodes: [], children: [], parent, excluded: false });
        if (parent && !this.colls.get(parent).children.includes(name)) this.colls.get(parent).children.push(name);
        return name;
    }

    add(node, coll) {
        let name = node.name, k = 0;
        while (this.objects.has(name)) name = `${node.name}.${String(++k).padStart(3, '0')}`;   // (Blender's .001)
        node.name = name;
        this.objects.set(name, node);
        this.colls.get(coll).nodes.push(node);
        node.colls.push(coll);
        return node;
    }

    remove(node) {
        this.objects.delete(node.name);
        for (const c of node.colls) { const l = this.colls.get(c).nodes; l.splice(l.indexOf(node), 1); }
    }

    get(name) { return this.objects.get(name); }

    // a driver: fn(state) sets node fields from the controls; run in the order they were added
    drive(node, fn) { node.driven = true; this.drivers.push([node, fn]); }

    evaluate(state) {
        this.tick++;
        for (const [, fn] of this.drivers) fn(state);
    }

    world(node) {
        if (node._tick === this.tick && node._w) return node._w;
        let w;
        const tgt = node.copy ? node.copy() : null;                    // (COPY_TRANSFORMS at influence 1: its target's)
        if (tgt) w = this.world(tgt);
        else w = node.parent ? M4.mul(this.world(node.parent), node.local()) : node.local();
        node._w = w; node._tick = this.tick;
        return w;
    }

    // whether a node's world can change with the controls (it, a parent or what it copies is driven)
    dynamic(node) {
        for (let n = node; n; n = n.parent) {
            if (n.driven) return true;
            if (n.copy) return true;
        }
        return false;
    }

    // every node of a collection and its children
    allNodes(coll) {
        const c = this.colls.get(coll);
        return [...c.nodes, ...c.children.flatMap((k) => this.allNodes(k))];
    }

    // what is drawn: [{ mesh, chain, dynamic }] from the collections given, through collection instances and point
    // instancers (an instanced collection's objects at their own world matrices; a point instancer's object source in
    // its own space). chain: the factors of the drawn matrix, left to right, each a node (its world, read when drawn:
    // an instancer the controls move carries what it instances) or a fixed matrix; matrixOf(leaf) multiplies them
    flatten(colls) {
        const out = [];
        const visit = (node, chain, depth) => {
            if (depth > 8 || node.hidden) return;
            if (node.mesh) out.push({ mesh: node.mesh, chain: [...chain, node], shadowOnly: node.shadowOnly, noShadow: node.noShadow, outdoor: node.outdoor });
            if (node.inst) for (const n of this.allNodes(node.inst)) visit(n, [...chain, node], depth + 1);
            if (node.points) {
                const { pts, rz, source } = node.points;
                const R = M4.compose([0, 0, 0], [0, 0, rz], [1, 1, 1]);
                for (const p of pts) {
                    const m = M4.mul(M4.T(p), R);
                    if (source.coll) for (const n of this.allNodes(source.coll)) visit(n, [...chain, node, m], depth + 1);
                    else {
                        const s = this.objects.get(source.node);
                        out.push({ mesh: s.mesh, chain: [...chain, node, m], shadowOnly: s.shadowOnly, noShadow: s.noShadow, outdoor: node.outdoor || s.outdoor });
                    }
                }
            }
        };
        for (const c of colls) for (const n of this.allNodes(c)) visit(n, [], 0);
        for (const leaf of out) leaf.dynamic = leaf.chain.some((f) => f instanceof Node && this.dynamic(f));
        return out;
    }

    // a drawn leaf's matrix: the product of its chain (nodes' worlds, fixed matrices)
    matrixOf(leaf) {
        let m = null;
        for (const f of leaf.chain) {
            const k = f instanceof Node ? this.world(f) : f;
            m = m ? M4.mul(m, k) : k;
        }
        return m;
    }
}
