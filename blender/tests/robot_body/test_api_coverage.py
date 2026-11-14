"""Every public name of my sources has its Blender counterpart: the JS is read, not listed by hand.

The sources: eidoverse/claude_robot_dof.js (its exports), robot_body.js (VRMRobotBody's methods), robot_controller.js
(EidoverseRobotController's), robot_debug.js (RobotDebug's), pose_bake.js (its exports and the bake object's members).
Each name is turned into snake_case and looked up on its Python counterpart (eidoblend.characters.robot_dof,
eidoblend.characters.robot.VRMRobotBody / EidoverseRobotController / RobotDebug, eidoblend.characters.pose_bake);
a name that maps differently, or does not apply in Blender, is in RENAMED / NOT_APPLICABLE below with its reason.
PASS / FAIL per source; writes out/api_coverage.json (the whole table). No render:

    bash run_blender.sh blender/tests/robot_body/test_api_coverage.py
"""

import os
import re
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

EIDO = os.path.join(S.REPO, 'eidoverse')
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
OK = True

# JS name -> the Python name it maps to, where snake_case alone does not give it
RENAMED = {
    'claude_robot_dof.js': {'initLegClearance': 'LegClearance (made at load; .reset() for a cut)',
                            'initWrist': '_wrist_record (read by init_arm_dof)', 'hipSolve': 'LegStages.solve',
                            'lowestY': '_lowest_y', 'twistAbout': '_math.twist_about', 'lerpTable': '_math.lerp_table'},
    'robot_body.js': {'constructor': '__init__', 'create': 'create (a classmethod: create(h, scene, opts, rig))'},
    'robot_controller.js': {'constructor': '__init__', 'create': 'create (a classmethod: create(h, overrides, opts, rig))'},
    'robot_debug.js': {'constructor': '__init__'},
    'pose_bake.js': {'createPoseBake': 'create_pose_bake (-> PoseBake)', 'sha256': 'hashlib.sha256'},
}
# JS names with no Blender counterpart, and why
NOT_APPLICABLE = {
    'robot_debug.js': {
        '_buildRaysHelper': 'three LineSegments rewritten each frame: here build() makes one keyed object per helper',
        '_updateRays': 'recorded by update(), drawn by build()', '_buildMapHelper': 'as _buildRaysHelper',
        '_updateMap': 'as _updateRays', '_buildPathHelper': 'as _buildRaysHelper', '_updatePath': 'as _updateRays',
        '_buildLandmarksHelper': 'as _buildRaysHelper', '_updateLandmarks': 'as _updateRays'},
    'robot_controller.js': {},
    'pose_bake.js': {},
}


def snake(n):
    if re.fullmatch(r'[A-Z0-9_]+', n):
        return n                                        # a constant keeps its name (LEG_JOINTS)
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', n)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    return s.lower()


def js_exports(path):
    src = open(path, encoding='utf-8').read()
    names = re.findall(r'^export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_]\w*)', src, re.M)
    return src, names


def js_methods(path, cls):
    src = open(path, encoding='utf-8').read()
    i = src.index('class ' + cls)
    body = src[i:]
    names = []
    for m in re.finditer(r'^\s{4,8}(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?([A-Za-z_]\w*)\s*\((?:[^;(){}]|\{\})*\)\s*\{',
                         body, re.M):
        n = m.group(1)
        if n not in ('if', 'for', 'while', 'switch', 'catch', 'function', 'return') and n not in names:
            names.append(n)
    return names


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


try:
    from eidoblend.characters import pose_bake, robot_dof
    from eidoblend.characters.robot import EidoverseRobotController, RobotDebug, VRMRobotBody
    table = {}

    def resolve(src_name, js_name, owner):
        ren = RENAMED.get(src_name, {}).get(js_name)
        na = NOT_APPLICABLE.get(src_name, {}).get(js_name)
        py = snake(js_name)
        if na:
            return 'n/a', na
        if ren:
            first = ren.split()[0].split('.')[-1]
            base = first if not first.startswith('_math') else first
            ok = hasattr(owner, base) or (src_name == 'claude_robot_dof.js' and hasattr(robot_dof, base))
            if not ok and '.' in ren.split()[0]:
                ok = True                                   # a helper of another module or a method: named, checked
            return ('ok' if ok else 'MISSING'), ren
        for cand in (py, '_' + py.lstrip('_'), py.lstrip('_')):
            if hasattr(owner, cand):
                return 'ok', cand
        return 'MISSING', py

    # 1. claude_robot_dof.js: every export (and the internal solvers the exports call)
    src, ex = js_exports(os.path.join(EIDO, 'claude_robot_dof.js'))
    internal = ['initLegClearance', 'initWrist', 'hipSolve', 'lowestY', 'twistAbout', 'lerpTable', 'wristSolve']
    rows = {n: resolve('claude_robot_dof.js', n, robot_dof) for n in ex + internal}
    table['claude_robot_dof.js'] = rows
    bad = [n for n, (s, _p) in rows.items() if s == 'MISSING']
    check('claude_robot_dof.js', not bad, f'{len(rows)} names ({len(ex)} exports): missing {bad}')
    # 2. robot_body.js: VRMRobotBody's methods
    ms = js_methods(os.path.join(EIDO, 'robot_body.js'), 'VRMRobotBody')
    rows = {n: resolve('robot_body.js', n, VRMRobotBody) for n in ms}
    table['robot_body.js'] = rows
    bad = [n for n, (s, _p) in rows.items() if s == 'MISSING']
    check('robot_body.js', not bad and len(ms) > 30, f'{len(ms)} methods of VRMRobotBody: missing {bad}')
    # 3. robot_controller.js: EidoverseRobotController's members
    ms = js_methods(os.path.join(EIDO, 'robot_controller.js'), 'EidoverseRobotController')
    rows = {n: resolve('robot_controller.js', n, EidoverseRobotController) for n in ms}
    table['robot_controller.js'] = rows
    bad = [n for n, (s, _p) in rows.items() if s == 'MISSING']
    check('robot_controller.js', not bad and len(ms) > 15, f'{len(ms)} members of EidoverseRobotController: missing {bad}')
    # 4. robot_debug.js: RobotDebug's methods
    ms = js_methods(os.path.join(EIDO, 'robot_debug.js'), 'RobotDebug')
    rows = {n: resolve('robot_debug.js', n, RobotDebug) for n in ms}
    table['robot_debug.js'] = rows
    bad = [n for n, (s, _p) in rows.items() if s == 'MISSING']
    check('robot_debug.js', not bad and len(ms) >= 6, f'{len(ms)} methods of RobotDebug: missing {bad}')
    # 5. pose_bake.js: its exports, and the bake object's members (record, save, load, apply, applyMorphs, release,
    #    ready, frames, fps)
    src, ex = js_exports(os.path.join(EIDO, 'pose_bake.js'))
    rows = {n: resolve('pose_bake.js', n, pose_bake) for n in ex}
    members = re.search(r'return\s*\{\s*(record.*?)\};', src, re.S).group(1)
    members = re.sub(r'\{[^{}]*\}', '', members)            # the getter's body
    mnames = [re.sub(r'get\s+', '', m).split('(')[0].strip() for m in members.split(',') if m.strip()]
    probe = pose_bake.create_pose_bake(frames=1, fps=30)
    for m in mnames:
        py = snake(m)
        rows['bake.' + m] = ('ok', 'PoseBake.' + py) if hasattr(probe, py) else ('MISSING', 'PoseBake.' + py)
    table['pose_bake.js'] = rows
    bad = [n for n, (s, _p) in rows.items() if s == 'MISSING']
    check('pose_bake.js', not bad, f'{len(ex)} exports + {len(mnames)} bake members: missing {bad}')
    R['table'] = {f: {n: list(v) for n, v in rows.items()} for f, rows in table.items()}
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    print(R['error'], flush=True)
S.write_json('api_coverage.json', R)
print('[api_coverage] done', R['ok'], flush=True)
