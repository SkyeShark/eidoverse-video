"""The graph: nodes, typed ports, edges, evaluation order (Ekigar's src/graph/model.js).

A directed acyclic graph where an output can feed many inputs, branches merge, and one mask drives several consumers:
the thing a linear stack cannot express.

    g = create_graph()
    a = add_node(g, 'fbm', params={'frequency': 4})
    b = add_node(g, 'phacelle')
    connect(g, {'node': a, 'port': 'out'}, {'node': b, 'port': 'in'}, graph_ports)
    order, missing = evaluation_order(g, b, graph_ports)

PORT MODEL: data inputs on the left, an optional mask input on the bottom, outputs on the right. Ports are typed and
connections are checked (a field may drive a mask port; a mask cannot stand in for a field; a material stack connects
only to a material port). The graph is serialised as the `graph` half of an ekigar-project/3 file (to_json /
from_json), and migrate_project upgrades older project formats.
"""
from __future__ import annotations

import copy
import json
import re

PORT_TYPES = {
    'field': {'label': 'Field', 'colour': '#d99a4e', 'doc': 'height + analytic gradient + aux'},
    'mask': {'label': 'Mask', 'colour': '#6b7c8c', 'doc': 'scalar 0..1'},
    'colour': {'label': 'Colour', 'colour': '#b5643c', 'doc': 'RGB, e.g. a surfaced result'},
    'material': {'label': 'Material', 'colour': '#7fa87a', 'doc': 'layered PBR material stack'},
}

DEFAULT_TAB = {'index': 0, 'name': 'Graph 1', 'colour': '#d99a4e', 'zoom': 1, 'panX': 0, 'panY': 0}


def can_connect(from_type, to_type):
    """A mask port accepts a field (its height reads as a scalar); nothing else crosses types."""
    if from_type is None or to_type is None:
        return False
    if from_type == to_type:
        return True
    if to_type == 'material' or from_type == 'material':
        return False
    if to_type == 'mask' and from_type == 'field':
        return True
    return False


_ID = [0]


def _next_id(prefix):
    _ID[0] += 1
    return f'{prefix}{_ID[0]}'


def create_graph():
    return {'nodes': {}, 'edges': {}, 'version': 0, 'portals': {}, 'groups': {}, 'notes': {},
            'tabs': [dict(DEFAULT_TAB)], 'jsonExtras': {}}


def add_node(graph, op, at=None, params=None):
    """Add an operator node; returns its id. `at` is the canvas position {x, y}."""
    at = at or {'x': 0, 'y': 0}
    nid = _next_id('n')
    graph['nodes'][nid] = {'id': nid, 'op': op, 'params': dict(params or {}), 'x': at.get('x', 0),
                           'y': at.get('y', 0), 'title': None, 'disabled': False, 'preview': None}
    graph['version'] += 1
    return nid


def remove_node(graph, nid):
    graph['nodes'].pop(nid, None)
    for eid in [e for e, ed in graph['edges'].items() if ed['from']['node'] == nid or ed['to']['node'] == nid]:
        del graph['edges'][eid]
    graph['version'] += 1


def connect(graph, frm, to, ports):
    """Connect frm {node, port} -> to {node, port}: type-checked, single writer per input, acyclic.
    Returns {'ok': True, 'id'} or {'ok': False, 'reason'}."""
    out_type = ports.output_type(graph['nodes'][frm['node']]['op'], frm.get('port'))
    in_type = ports.input_type(graph['nodes'][to['node']]['op'], to.get('port'))
    if not can_connect(out_type, in_type):
        return {'ok': False, 'reason': f'{out_type} cannot drive a {in_type} port'}
    if _would_cycle(graph, frm['node'], to['node']):
        return {'ok': False, 'reason': 'that would create a cycle'}
    for eid in [e for e, ed in graph['edges'].items()
                if ed['to']['node'] == to['node'] and ed['to'].get('port') == to.get('port')]:
        del graph['edges'][eid]
    eid = _next_id('e')
    graph['edges'][eid] = {'id': eid, 'from': dict(frm), 'to': dict(to)}
    graph['version'] += 1
    return {'ok': True, 'id': eid}


def disconnect(graph, edge_id):
    graph['edges'].pop(edge_id, None)
    graph['version'] += 1


def _would_cycle(graph, from_node, to_node):
    if from_node == to_node:
        return True
    seen = set()
    stack = [from_node]
    while stack:
        n = stack.pop()
        if n == to_node:
            return True
        if n in seen:
            continue
        seen.add(n)
        for e in graph['edges'].values():
            if e['to']['node'] == n:
                stack.append(e['from']['node'])
    return False


def inputs_of(graph, nid):
    """Every edge feeding a node, as {port_name: {node, port}}."""
    out = {}
    for e in graph['edges'].values():
        if e['to']['node'] == nid:
            out[e['to'].get('port')] = e['from']
    return out


def consumers_of(graph, nid):
    return [e['to'] for e in graph['edges'].values() if e['from']['node'] == nid]


def evaluation_order(graph, target_id, ports):
    """Kahn's algorithm over the subgraph that reaches target_id. Returns (order, missing): `missing` lists required
    inputs with no wire, {node, port}."""
    needed = []
    seen = set()

    def walk(i):
        if i in seen:
            return
        seen.add(i)
        needed.append(i)
        for src in inputs_of(graph, i).values():
            walk(src['node'])

    walk(target_id)
    indeg = {}
    for i in needed:
        indeg[i] = sum(1 for src in inputs_of(graph, i).values() if src['node'] in seen)
    ready = [i for i in needed if indeg[i] == 0]
    order = []
    while ready:
        i = ready.pop(0)
        order.append(i)
        for c in consumers_of(graph, i):
            if c['node'] not in seen:
                continue
            indeg[c['node']] -= 1
            if indeg[c['node']] == 0:
                ready.append(c['node'])
    if len(order) != len(needed):
        raise ValueError('graph contains a cycle; evaluation order is undefined')
    missing = []
    for i in order:
        node = graph['nodes'].get(i)
        if node is None:
            continue
        wired = inputs_of(graph, i)
        for p in ports.required_inputs(node['op']):
            if p not in wired:
                missing.append({'node': i, 'port': p})
    return order, missing


def to_json(graph):
    """The serialisable graph half of a project (unknown fields preserved; runtime preview/timing dropped)."""
    out = dict(graph.get('jsonExtras') or {})
    nodes = []
    for n in graph['nodes'].values():
        saved = {k: v for k, v in n.items() if k not in ('preview', 'buildMs', 'buildTotalMs')}
        saved['tab'] = n.get('tab', 0) or 0
        nodes.append(saved)
    out['nodes'] = nodes
    out['edges'] = [{k: v for k, v in e.items() if k != 'id'} for e in graph['edges'].values()]
    out['portals'] = list((graph.get('portals') or {}).values())
    out['groups'] = list((graph.get('groups') or {}).values())
    out['notes'] = list((graph.get('notes') or {}).values())
    out['tabs'] = graph.get('tabs') or [dict(DEFAULT_TAB)]
    return out


def from_json(data):
    g = create_graph()
    for n in data.get('nodes') or []:
        node = {'preview': None, 'disabled': False, 'title': None}
        node.update(n)
        g['nodes'][n['id']] = node
        num = re.sub(r'\D', '', str(n['id']))
        if num and int(num) > _ID[0]:
            _ID[0] = int(num)
    for e in data.get('edges') or []:
        eid = _next_id('e')
        saved = {k: v for k, v in e.items() if k != 'id'}
        saved.update({'id': eid, 'from': dict(e.get('from') or {}), 'to': dict(e.get('to') or {})})
        g['edges'][eid] = saved
    g['portals'] = {x['name']: x for x in data.get('portals') or []}
    g['groups'] = {x['id']: x for x in data.get('groups') or []}
    g['notes'] = {x['id']: x for x in data.get('notes') or []}
    g['tabs'] = data.get('tabs') or [dict(DEFAULT_TAB)]
    known = {'nodes', 'edges', 'portals', 'groups', 'notes', 'tabs'}
    g['jsonExtras'] = {k: v for k, v in data.items() if k not in known}
    return g


# ------------------------------------------------------------------- project format 3: material-band migration ---

PROJECT_FORMAT = 'ekigar-project/3'


def _finite(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float('inf'), float('-inf'))


def ensure_band_ids(layers, node_id='material'):
    used = set()
    out = []
    for i, source in enumerate(layers or []):
        layer = dict(source or {})
        fallback = f'band-{node_id}-{i + 1}'
        lid = layer.get('id').strip() if isinstance(layer.get('id'), str) and layer.get('id').strip() else fallback
        base = lid
        suffix = 2
        while lid in used:
            lid = f'{base}-{suffix}'
            suffix += 1
        used.add(lid)
        layer['id'] = lid
        out.append(layer)
    return out


def initialise_material_bands(layers, node_id='material'):
    """Fill missing band ranges with a contiguous partition of (0, 1]; authored ranges are never rewritten."""
    out = ensure_band_ids(layers, node_id)
    n = max(1, len(out))
    res = []
    for i, layer in enumerate(out):
        L = dict(layer)
        L['bandMin'] = float(L['bandMin']) if _finite(L.get('bandMin')) else i / n
        L['bandMax'] = float(L['bandMax']) if _finite(L.get('bandMax')) else (i + 1) / n
        L['bandFeather'] = float(L['bandFeather']) if _finite(L.get('bandFeather')) else min(0.08, 0.25 / n)
        res.append(L)
    return res


def _is_material_map(n):
    return bool(n) and n.get('op') in ('materialMap', 'surface')


def _material_port_rank(port):
    if port == 'mask':
        return 0
    if isinstance(port, str) and re.fullmatch(r'mask\d+', port):
        return int(port[4:])
    return float('inf')


def migrate_project(inp):
    """Upgrade a project to ekigar-project/3 without pretending legacy per-layer masks equal one value driver.
    Returns (project, warnings); the input is not modified."""
    project = copy.deepcopy(inp or {})
    warnings = []
    project.setdefault('graph', {'nodes': [], 'edges': []})
    project['graph'].setdefault('nodes', [])
    project['graph'].setdefault('edges', [])
    project['legacy'] = dict(project.get('legacy') or {})
    nodes = project['graph']['nodes']
    edges = project['graph']['edges']

    chain_nodes = [n for n in nodes if n.get('op') == 'layers']
    if chain_nodes:
        chain_ids = {n['id'] for n in chain_nodes}
        chain_edges = [e for e in edges if (e.get('from') or {}).get('node') in chain_ids
                       or (e.get('to') or {}).get('node') in chain_ids]
        mc = dict(project['legacy'].get('materialChains') or {})
        mc.update({'nodes': copy.deepcopy(chain_nodes), 'edges': copy.deepcopy(chain_edges)})
        project['legacy']['materialChains'] = mc
        project['graph']['nodes'] = [n for n in project['graph']['nodes'] if n['id'] not in chain_ids]
        edges = [e for e in edges if (e.get('from') or {}).get('node') not in chain_ids
                 and (e.get('to') or {}).get('node') not in chain_ids]
        project['graph']['edges'] = edges
        warnings.append('A legacy material chain was archived because its separate blend masks cannot be '
                        'represented by one Material Map driver.')

    maps = [n for n in project['graph']['nodes'] if _is_material_map(n)]
    for node in maps:
        conversion = dict(((node.get('legacy') or {}).get('materialConversion')) or {})
        node['legacy'] = dict(node.get('legacy') or {})
        node['legacy']['materialConversion'] = conversion
        if node.get('op') == 'surface':
            conversion['operator'] = 'surface'
            node['op'] = 'materialMap'
        field_in = next((e for e in edges if (e.get('to') or {}).get('node') == node['id']
                         and (e.get('to') or {}).get('port') == 'in'), None)
        field_out = [e for e in edges if (e.get('from') or {}).get('node') == node['id']
                     and (e.get('from') or {}).get('port') == 'out']
        title = node.get('title') or 'Material Map'
        if field_in:
            conversion['fieldInput'] = copy.deepcopy(field_in)
            for e in field_out:
                e['from'] = copy.deepcopy(field_in['from'])
            edges = [e for e in edges if e is not field_in]
            if project.get('target') == node['id']:
                project['target'] = (field_in.get('from') or {}).get('node')
                project['targetPort'] = (field_in.get('from') or {}).get('port', 'out')
        elif field_out:
            conversion['fieldOutputs'] = copy.deepcopy(field_out)
            edges = [e for e in edges if not any(e is x for x in field_out)]
            warnings.append(f'{title} had downstream field wiring but no field source; those wires were archived.')
        candidates = sorted([e for e in edges if (e.get('to') or {}).get('node') == node['id']
                             and _material_port_rank((e.get('to') or {}).get('port')) < float('inf')],
                            key=lambda e: _material_port_rank(e['to']['port']))
        live = {n['id'] for n in project['graph']['nodes']}
        usable = next((e for e in candidates if (e.get('from') or {}).get('node') in live), None)
        if candidates:
            conversion['maskEdges'] = copy.deepcopy(candidates)
        edges = [e for e in edges if not any(e is c for c in candidates)]
        if usable:
            nu = dict(usable)
            nu['to'] = dict(usable['to'])
            nu['to']['port'] = 'mask'
            edges.append(nu)
        if len(candidates) > 1 or (candidates and candidates[0]['to'].get('port') != 'mask'):
            warnings.append(f'{title} used per-slot masks; one usable mask now drives value bands and the original '
                            'wires were archived.')
        if candidates and not usable:
            warnings.append(f'{title} had mask wiring whose source no longer exists; it was archived and the driver '
                            'is now unwired.')
        source_layers = node.get('layers') if node.get('layers') is not None else (
            [node['layer']] if node.get('layer') else [])
        layer_masks = []
        clean = []
        for index, source in enumerate(source_layers):
            layer = dict(source or {})
            old = {'index': index}
            if isinstance(layer.get('maskStack'), list) and layer['maskStack']:
                old['maskStack'] = copy.deepcopy(layer['maskStack'])
            if isinstance(layer.get('rules'), list) and layer['rules']:
                old['rules'] = copy.deepcopy(layer['rules'])
            layer.pop('maskStack', None)
            layer.pop('rules', None)
            if len(old) > 1:
                layer_masks.append(old)
            clean.append(layer)
        if layer_masks:
            conversion['layerMasks'] = layer_masks
            warnings.append(f'{title} contained internal mask rules; they were archived and replaced by explicit '
                            'value bands.')
        if 'layer' in node:
            conversion['layer'] = copy.deepcopy(node['layer'])
            del node['layer']
        node['layers'] = initialise_material_bands(clean, node['id'])
    project['graph']['edges'] = edges
    live_map_ids = {n['id'] for n in maps}
    if not project.get('materialTarget') or project['materialTarget'] not in live_map_ids:
        project['materialTarget'] = maps[0]['id'] if maps else None
    project['format'] = PROJECT_FORMAT
    seen = []
    for w in list(project.get('conversionWarnings') or []) + warnings:
        if w not in seen:
            seen.append(w)
    project['conversionWarnings'] = seen
    return project, project['conversionWarnings']


# ----------------------------------------------------------------------- portals, groups, notes, tabs ---

def create_portal(graph, frm, name):
    """A wireless output -> input link drawn as a labelled tab; the edge it carries is an ordinary edge."""
    graph.setdefault('portals', {})
    if frm['node'] not in graph['nodes']:
        return {'ok': False, 'reason': 'source node does not exist'}
    if name in graph['portals']:
        return {'ok': False, 'reason': f"a portal named '{name}' already exists"}
    graph['portals'][name] = {'name': name, 'node': frm['node'], 'port': frm.get('port')}
    graph['version'] += 1
    return {'ok': True, 'name': name}


def remove_portal(graph, name):
    (graph.get('portals') or {}).pop(name, None)
    for e in graph['edges'].values():
        if e.get('viaPortal') == name:
            del e['viaPortal']
    graph['version'] += 1


def connect_via_portal(graph, name, to, ports):
    p = (graph.get('portals') or {}).get(name)
    if not p:
        return {'ok': False, 'reason': f"no portal named '{name}'"}
    r = connect(graph, {'node': p['node'], 'port': p['port']}, to, ports)
    if r['ok']:
        graph['edges'][r['id']]['viaPortal'] = name
        graph['version'] += 1
    return r


def convert_to_portal(graph, edge_id, name):
    e = graph['edges'].get(edge_id)
    if not e:
        return {'ok': False, 'reason': 'no such connection'}
    made = {'ok': True, 'name': name} if name in (graph.get('portals') or {}) else create_portal(graph, e['from'], name)
    if not made['ok']:
        return made
    e['viaPortal'] = name
    graph['version'] += 1
    return {'ok': True, 'name': name}


def available_portals(graph, to_node, to_port, ports):
    out = []
    target = graph['nodes'].get(to_node)
    if not target:
        return out
    for p in (graph.get('portals') or {}).values():
        if p['node'] == to_node or _would_cycle(graph, p['node'], to_node):
            continue
        src = graph['nodes'].get(p['node'])
        if not src:
            continue
        t = ports.output_type(src['op'], p['port'])
        if not can_connect(t, ports.input_type(target['op'], to_port)):
            continue
        out.append(dict(p, type=t))
    return out


def add_group(graph, name, children=(), **opts):
    graph.setdefault('groups', {})
    gid = _next_id('gr')
    graph['groups'][gid] = {'id': gid, 'name': name, 'children': list(children),
                            'colour': opts.get('colour', '#6b7c8c'), 'icon': opts.get('icon'),
                            'collapsed': False, 'locked': False, 'x': opts.get('x', 0), 'y': opts.get('y', 0),
                            'w': opts.get('w', 320), 'h': opts.get('h', 200), 'tab': opts.get('tab', 0)}
    graph['version'] += 1
    return gid


def add_note(graph, markdown, at=None, **opts):
    graph.setdefault('notes', {})
    at = at or {'x': 0, 'y': 0}
    nid = _next_id('nt')
    graph['notes'][nid] = {'id': nid, 'markdown': markdown, 'x': at.get('x', 0), 'y': at.get('y', 0),
                           'w': opts.get('w', 240), 'h': opts.get('h', 120), 'colour': opts.get('colour', '#d99a4e'),
                           'tab': opts.get('tab', 0)}
    graph['version'] += 1
    return nid


def add_tab(graph, name=None, **opts):
    graph.setdefault('tabs', [dict(DEFAULT_TAB)])
    index = len(graph['tabs'])
    graph['tabs'].append({'index': index, 'name': name or f'Graph {index + 1}', 'colour': opts.get('colour', '#6b7c8c'),
                          'zoom': 1, 'panX': 0, 'panY': 0})
    graph['version'] += 1
    return index


def move_to_tab(graph, node_id, tab_index):
    """Move a node to another tab, auto-creating portals for every connection that now crosses tabs."""
    n = graph['nodes'].get(node_id)
    if not n:
        return {'ok': False, 'reason': 'no such node'}
    n['tab'] = tab_index
    made = []
    for e in list(graph['edges'].values()):
        a = graph['nodes'].get(e['from']['node'])
        b = graph['nodes'].get(e['to']['node'])
        if not a or not b or e.get('viaPortal'):
            continue
        if (a.get('tab') or 0) == (b.get('tab') or 0):
            continue
        base = f"{a.get('title') or a['op']}.{e['from'].get('port')}"
        name, i = base, 2
        while name in (graph.get('portals') or {}):
            name = f'{base} {i}'
            i += 1
        r = convert_to_portal(graph, e['id'], name)
        if r['ok']:
            made.append(name)
    graph['version'] += 1
    return {'ok': True, 'portals': made}


def nodes_on_tab(graph, tab_index=0):
    return [n for n in graph['nodes'].values() if (n.get('tab') or 0) == tab_index]


# ------------------------------------------------- wiring heuristics (src/graph/wire.js): where a new wire lands ---

def connection_target_rank(from_type, to_type, input_required=False):
    """0 a required same-type input, 1 an optional same-type input, 2 a legal conversion, 3 refused."""
    if not can_connect(from_type, to_type):
        return 3
    if from_type != to_type:
        return 2
    return 0 if input_required else 1


def choose_connection_target(candidates):
    """The best of several candidate ports ({fromType, toType, inputRequired, distanceSq, ...}): lowest rank, then
    nearest. Incompatible ports stay candidates (ok=False) so the refusal can be reported."""
    best = None
    for c in candidates:
        rank = connection_target_rank(c['fromType'], c['toType'], c.get('inputRequired', False))
        if best and (rank > best['rank'] or (rank == best['rank'] and c['distanceSq'] >= best['distanceSq'])):
            continue
        best = dict(c, rank=rank, ok=rank < 3)
    return best


def choose_input_port(ports, wired_names, src_type='field'):
    """Which input of a node a new wire from a `src_type` output should land on (wire.js chooseInputPort): a free
    accepting input, else the free mask port, else an accepting input (replacing its wire), else any input."""
    taken = set(wired_names or ())
    inputs = ports.get('inputs') or []
    free = [p for p in inputs if p['name'] not in taken]
    for p in free:
        if can_connect(src_type, p.get('type') or 'field'):
            return p['name']
    if ports.get('mask') and 'mask' not in taken and can_connect(src_type, 'mask'):
        return 'mask'
    for p in inputs:
        if can_connect(src_type, p.get('type') or 'field'):
            return p['name']
    if free:
        return free[0]['name']
    return inputs[0]['name'] if inputs else None


def downstream_terminal(graph, nid, can_preview=lambda node: True):
    """Follow first consumers from `nid` to the end of the chain; the last previewable node on the way."""
    cur = nid
    best = cur if can_preview(graph['nodes'].get(cur)) else None
    seen = {nid}
    while True:
        cons = consumers_of(graph, cur)
        nxt = cons[0]['node'] if cons else None
        if not nxt or nxt in seen:
            break
        seen.add(nxt)
        cur = nxt
        if can_preview(graph['nodes'].get(cur)):
            best = cur
    return best


def target_after_add(graph, nid, required_inputs, can_preview=lambda node: True):
    """The preview target after `nid` was added: None until its required inputs are wired, then the end of its
    chain. `required_inputs(op)` is graph_ports.required_inputs."""
    node = graph['nodes'].get(nid)
    if not node:
        return None
    wired = inputs_of(graph, nid)
    if any(p not in wired for p in required_inputs(node['op'])):
        return None
    return downstream_terminal(graph, nid, can_preview)


def dumps(graph) -> str:
    return json.dumps(to_json(graph), indent=2)
