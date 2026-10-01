"""The claudesona's petal-ring pivot: keeps the ring around the face off the jacket when the neck bends.

The ring is split-skinned: its top arc rides the head (`petals base`), its bottom arc a twin bone,
`petals base lower`. On the neck, the twin swung that bottom arc down into the collar and lapels on every nod
or tilt (29 mm deep at a 35-degree nod), and the lapels showed through the orange. This hangs the twin from a
node on the CHEST at the neck joint, `petals base lower pivot`, with a VRMC_node_constraint that follows only
the neck's turn about the body's vertical (the pivot rests aligned with the rest pose's world axes, which are the
axes VRM animation rotates the normalized neck about). Nods and tilts no longer drive the arc into the jacket, and
a turn moves the ring exactly as it always did. three-vrm applies the constraint inside vrm.update(), so every
scene that loads the VRM gets it; the rest pose is unchanged.

Applied to ../claude_suit.vrm and ../claude_suit_wardrobe.vrm; export_wardrobe_vrm.py re-applies it after
every export. Re-running it on a patched file is safe.

Following less of the turn was tried and measured: none of it stretches the ring into folds on a 45-degree turn,
60% of it breaks the lapel tip into jagged fragments. Big turns (past about 20 degrees) still bring a lapel tip
through the side of the ring, exactly as before.

  python ring_pivot.py <in.vrm> <out.vrm>
"""
import argparse, json, struct


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def qrot(q, v):
    x, y, z, w = q
    p = qmul(qmul(q, [v[0], v[1], v[2], 0]), [-x, -y, -z, w])
    return p[:3]


def add_ring_pivot(src, dst):
    data = open(src, 'rb').read()
    magic, version, _ = struct.unpack('<4sII', data[:12])
    assert magic == b'glTF' and version == 2, 'not a GLB'
    jlen, jtype = struct.unpack('<I4s', data[12:20])
    assert jtype == b'JSON'
    j = json.loads(data[20:20 + jlen])
    rest = data[20 + jlen:]                               # the BIN chunk (header included), unchanged

    nodes = j['nodes']
    idx = {n.get('name'): i for i, n in enumerate(nodes)}
    twin, neck = idx['petals base lower'], idx['neck']
    parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    PIVOT = 'petals base lower pivot'
    if PIVOT in idx:                                      # undo a previous run: twin back under the neck
        piv = idx[PIVOT]
        tw = nodes[twin]
        if 'twin_neck_local' in nodes[piv].get('extras', {}):
            tw.update(nodes[piv]['extras']['twin_neck_local'])
        nodes[piv]['children'] = []
        nodes[parent[piv]]['children'] = [c for c in nodes[parent[piv]]['children'] if c != piv]
        nodes[neck].setdefault('children', []).append(twin)
        parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    else:
        piv = len(nodes)
        nodes.append({'name': PIVOT})
    assert parent.get(twin) == neck, f"'petals base lower' is not on the neck (parent {parent.get(twin)})"
    chest = parent[neck]
    chest_world = [0, 0, 0, 1]                            # the chest's rest rotation in the model's space
    k = chest
    while k is not None:
        assert 'matrix' not in nodes[k], 'expects TRS nodes'
        chest_world = qmul(nodes[k].get('rotation', [0, 0, 0, 1]), chest_world)
        k = parent.get(k)
    n, tw = nodes[neck], nodes[twin]
    for nd in (n, tw):
        assert 'matrix' not in nd and all(abs(s - 1) < 1e-6 for s in nd.get('scale', [1, 1, 1])), 'expects TRS, unit scale'
    t_n, r_n = n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1])
    t_tw, r_tw = tw.get('translation', [0, 0, 0]), tw.get('rotation', [0, 0, 0, 1])
    saved = {'translation': t_tw, 'rotation': r_tw}
    # the pivot sits at the neck joint and rests on the model's axes; the twin keeps its rest pose under it
    cw_inv = [-chest_world[0], -chest_world[1], -chest_world[2], chest_world[3]]
    pv = {'translation': t_n, 'rotation': cw_inv}
    new_tw = {'translation': qrot(chest_world, qrot(r_n, t_tw)), 'rotation': qmul(chest_world, qmul(r_n, r_tw))}
    cons = {'roll': {'source': neck, 'rollAxis': 'Y', 'weight': 1.0}}
    nodes[piv] = {'name': PIVOT, **pv, 'children': [twin], 'extras': {'twin_neck_local': saved},
                  'extensions': {'VRMC_node_constraint': {'specVersion': '1.0', 'constraint': cons}}}
    tw.update(new_tw)
    nodes[neck]['children'] = [c for c in nodes[neck]['children'] if c != twin]
    if piv not in nodes[chest].setdefault('children', []):
        nodes[chest]['children'].append(piv)
    used = j.setdefault('extensionsUsed', [])
    if 'VRMC_node_constraint' not in used:
        used.append('VRMC_node_constraint')

    js = json.dumps(j, separators=(',', ':')).encode('utf-8')
    js += b' ' * ((4 - len(js) % 4) % 4)
    out = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + len(rest)) + struct.pack('<I4s', len(js), b'JSON') + js + rest
    open(dst, 'wb').write(out)
    return piv, cons


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    a = ap.parse_args()
    piv, cons = add_ring_pivot(a.src, a.dst)
    print(f'{a.dst}: pivot node {piv} on the chest, constraint {cons}')
