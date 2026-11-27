"""eidoblend.sets.same_seed.desk.models: the Poly Haven pieces, placed (Blender). Each imported AS IT SHIPS (its glTF
from the shared library, fetched by ID on first use: ns['LIB'].model), measured on arrival, turned and SEATED on the
surface it stands on (by its own lowest point, or by rays for the shelves' boards), each under one empty cc0_<name>
tagged with its id. CC0-1.0, Poly Haven:
  desk_lamp_arm_01 2k      the architect's lamp clamped on the desk's back edge (near (250, 550))
  steel_frame_shelves_01   the wide shelving (black steel, oak boards; it ships at 10x: scaled 0.1) on the left wall
  steel_frame_shelves_02   the narrow one on the back wall right of the window
  potted_plant_02          the plant on the floor left of the window; potted_plant_04 a small one on the window board
  dining_chair_02          the chair at the desk (Poly Haven has no task chair): pulled out, turned
  modern_ceiling_lamp_01   the pendant (off at 2 a.m.), hung shorter; wall_clock at four minutes past two;
                           hanging_picture_frame_01 on the back wall
  stationery_supplies      the pencil on the lyrics and the pencil cup with its pens; boombox on the wide shelf's top

    models.build(ns)         # after things (PAGE_AT, PAGE_YAW, RUG_T); adds cc0 (the placer), B1, B2 (the shelves' boards)
"""


def build(ns):
    (DCY, DD, DTOP, HT, LIB, Matrix, PAGE_AT, PAGE_YAW, RUG_T, Vector, WCX, X0, Y1, bpy, hs, math) = (
        ns[k] for k in ('DCY', 'DD', 'DTOP', 'HT', 'LIB', 'Matrix', 'PAGE_AT', 'PAGE_YAW', 'RUG_T', 'Vector', 'WCX', 'X0', 'Y1', 'bpy', 'hs', 'math'))
    def cc0(mid, res, name, at, yaw=0.0, scale=1.0, seat=None, seat_top=None, keep=None, edit=None, tilt=None):
        """import Poly Haven `mid` as it ships under an empty cc0_<name> at `at` (m), turned `yaw` degrees about z (after
        `tilt` (deg, axis) if given), scaled; seat: put its lowest point at this z (m); seat_top: its highest at this z"""
        path = LIB.model(mid, res)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        if keep:
            for o in list(new):
                if o.type == 'MESH' and not any(k_ in o.name for k_ in keep):
                    new.remove(o)
                    bpy.data.objects.remove(o, do_unlink=True)
        if edit:
            edit(new)
        e = bpy.data.objects.new('cc0_' + name, None)
        hs.col.objects.link(e)
        for o in new:
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            hs.col.objects.link(o)
            if o.parent is None:
                o.parent = e
            o['cc0'] = mid
        R = Matrix.Rotation(math.radians(yaw), 4, 'Z')
        if tilt is not None:
            R = R @ Matrix.Rotation(math.radians(tilt[0]), 4, Vector(tilt[1]))
        e.matrix_world = Matrix.Translation(Vector(at)) @ R @ Matrix.Diagonal((scale, scale, scale, 1.0))
        bpy.context.view_layer.update()
        if seat is not None or seat_top is not None:
            zs = [(o.matrix_world @ v.co).z for o in new if o.type == 'MESH' for v in o.data.vertices]
            dz = (seat - min(zs)) if seat is not None else (seat_top - max(zs))
            e.location.z += dz
            bpy.context.view_layer.update()
        e['cc0'] = f'Poly Haven {mid} ({res}): CC0-1.0, imported as it ships'
        print('CC0', name, mid, res, 'at', tuple(round(v, 3) for v in e.location), 'parts', len(new), flush=True)
        return e, new


    def board_tops(objs, x, y, z_from=3.0):
        """the heights of every upward face under (x, y) on these meshes (m): a shelf's boards, by rays"""
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get()
        out = []
        for o in objs:
            if o.type != 'MESH':
                continue
            bvh = BVHTree.FromObject(o, dg)
            inv = o.matrix_world.inverted()
            z = z_from
            while z > -0.5:
                p0 = inv @ Vector((x, y, z))
                d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
                hit, nrm, _i, _d = bvh.ray_cast(p0, d, 10.0)
                if hit is None:
                    break
                hw_ = o.matrix_world @ hit
                nw = (o.matrix_world.to_3x3().inverted().transposed() @ nrm).normalized()
                if nw.z > 0.9:
                    out.append(round(hw_.z, 4))
                z = hw_.z - 0.002
        return sorted(set(out))


    # ---------------------------------------------------------------- the lamp: clamped on the desk's back edge at x 250
    # (its origin is the clamp's seat on the top face; the arm and shade reach toward its own +y: turned to the room)
    LAMP, _ = cc0('desk_lamp_arm_01', '2k', 'desk_lamp', (0.25, DCY * hs.MM + DD * hs.MM / 2 + 0.012, DTOP * hs.MM), yaw=200.0)      # (its shade over the page; turned further, its arm crosses the close lens's right third)

    # ---------------------------------------------------------------- the shelves
    SH1, sh1 = cc0('steel_frame_shelves_01', '1k', 'shelves_wide', (X0 * hs.MM + 0.262, 2.18, 0.0), yaw=90.0, scale=0.1, seat=0.0)
    SH2, sh2 = cc0('steel_frame_shelves_02', '1k', 'shelves_narrow', (1.36, Y1 * hs.MM - 0.262, 0.0), seat=0.0)
    B1 = board_tops(sh1, X0 * hs.MM + 0.262, 2.18)
    B2 = board_tops(sh2, 1.36, Y1 * hs.MM - 0.262)
    print('SHELF BOARDS wide', B1, 'narrow', B2, flush=True)

    # ---------------------------------------------------------------- the plants
    cc0('potted_plant_02', '1k', 'plant_floor', (-1.78, 2.52, 0.0), yaw=35.0, seat=0.0)
    cc0('potted_plant_04', '1k', 'plant_sill', ((WCX + 420.0) * hs.MM, Y1 * hs.MM + 0.085, 0.9), yaw=-20.0, seat=0.9)

    # ---------------------------------------------------------------- the chair: pulled out from the desk, turned a little left
    cc0('dining_chair_02', '1k', 'chair', (0.9, -0.42, 0.0), yaw=205.0, seat=(RUG_T - 3.0) * hs.MM)      # (on the rug, its feet 3 into the pile)

    # ---------------------------------------------------------------- the pendant (off), the clock, the frame on the wall
    def hang_shorter(objs, drop=0.5):
        """the pendant ships on a 0.95 m drop: it would hang in the middle of the wide lenses and over a head by the desk.
        Hung shorter, as an electrician would, on the same flex: the flex (the stretch where the mesh is thinner than 8 mm about
        its axis) is shortened, the globe and its holder moved up by as much, the ceiling rose kept; its whole drop `drop`"""
        for o in objs:
            if o.type != 'MESH':
                continue
            vs = o.data.vertices
            zs = [v.co.z for v in vs]
            z_top, z_bot = max(zs), min(zs)
            thin = sorted(v.co.z for v in vs if math.hypot(v.co.x, v.co.y) < 0.008)
            band = [z for z in thin if z_bot + 0.2 < z < z_top - 0.02]
            if not band:
                return
            f0, f1 = min(band), max(band)                     # the flex runs from f0 (the holder's top) to f1 (the rose)
            cut = min((z_top - z_bot) - drop, (f1 - f0) - 0.04)
            for v in vs:
                if v.co.z <= f0:
                    v.co.z += cut
                elif v.co.z < f1:
                    v.co.z = f1 - (f1 - v.co.z) * (f1 - f0 - cut) / (f1 - f0)
            o.data.update()
            print('PENDANT flex', round(f1 - f0, 3), 'm shortened by', round(cut, 3), flush=True)


    cc0('modern_ceiling_lamp_01', '1k', 'pendant', (0.0, 0.85, 0.0), seat_top=HT * hs.MM, edit=hang_shorter)


    def clock_at_four_past_two(objs):
        """its hands ship at ten past ten: turned about the clock's axis (+y, clockwise as seen from the front) to 2:04
        and 47 s"""
        turn = {'hours_hand': 118.0, 'minute_hand': -26.0, 'second_hand': 105.0}
        for o in objs:
            for k_, deg in turn.items():
                if o.name.endswith(k_):
                    o.matrix_world = Matrix.Rotation(math.radians(deg), 4, 'Y') @ o.matrix_world


    cc0('wall_clock', '1k', 'wall_clock', (1.36, Y1 * hs.MM, 2.45), edit=clock_at_four_past_two)
    cc0('hanging_picture_frame_01', '1k', 'poster_frame', (2.25, Y1 * hs.MM, 1.62))

    # ---------------------------------------------------------------- on the desk: the pencil cup with its pens
    cc0('stationery_supplies', '1k', 'pencil_cup', (1.56, 0.56, DTOP * hs.MM), keep=['pencilcup'], seat=DTOP * hs.MM)


    for k_, (part, lean, turn, off) in enumerate((('pen_blue', 12.0, 20.0, (0.008, 0.0)), ('pencil_new_a', 9.0, 150.0, (-0.006, 0.006)), ('pen_red', 14.0, 260.0, (0.0, -0.008)))):
        def upright(objs, lean=lean, turn=turn):
            """three of the set's pens and pencils stood in the cup on their ends, leaning on its rim"""
            for o in objs:
                loc = o.matrix_world.translation.copy()
                o.matrix_world = Matrix.Rotation(math.radians(turn), 4, 'Z') @ Matrix.Rotation(math.radians(lean), 4, 'X') @ Matrix.Rotation(math.radians(90.0), 4, 'Y') @ Matrix.Translation(-loc) @ o.matrix_world
        cc0('stationery_supplies', '1k', f'cup_{part}', (1.56 + off[0], 0.56 + off[1], DTOP * hs.MM), keep=[part], edit=upright, seat=DTOP * hs.MM + 0.005)

    # ---------------------------------------------------------------- the pencil on the lyrics: the set's worn one, laid in
    # the page's fold (desk_things.py: PAGE_AT, PAGE_YAW), its own place in the set cleared first


    def pencil_alone(objs):
        for o in objs:
            o.matrix_world = Matrix.Identity(4)


    cc0('stationery_supplies', '1k', 'pencil_on_lyrics', ((PAGE_AT.x + 25.0) * hs.MM, (PAGE_AT.y - 6.0) * hs.MM, DTOP * hs.MM), yaw=math.degrees(PAGE_YAW) + 22.0,
        keep=['pencil_used'], edit=pencil_alone, seat=DTOP * hs.MM + 0.0004)

    # ---------------------------------------------------------------- the boombox on the wide shelf's top board
    if B1:
        cc0('boombox', '1k', 'boombox', (X0 * hs.MM + 0.30, 2.18, B1[-1]), yaw=90.0, seat=B1[-1])
    ns.update(cc0=cc0, B1=B1, B2=B2)
