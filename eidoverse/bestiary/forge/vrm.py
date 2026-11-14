"""THE VRM VIEW WRITER (H4, the rig builder, 11-01; HUMAN_PLAN §4.5, decisions 2 and 18): the VRMC_vrm 1.0 extension for a
forge glb whose skeleton is a humanoid, so the eidoverse's VRM systems (three-vrm 3.5.2's VRMLoaderPlugin, the dialed-in
controller, VRMA clips, the talk driver) run a Bestiary creature. H0's probe 2 (work/bestiary/human/h0/vrm_stub.py and
probe2_vrm.mjs) proved the path: three-vrm loads this extension on forge.gltf.GLB, the controller walks it, the
expressions with no binds are set and read back through expressionManager, lookAt of type 'bone' turns the eye joints;
a missing required bone is refused at load (so grafts keep the names).

WHAT IT WRITES (the spec's required fields, and what the plan asks):
  * meta: name, version, authors, licenseUrl (VRM's own licence page), the permissions (avatarPermission, the usage
    flags, commercialUsage, creditNotation, allowRedistribution, modification), copyrightInformation and
    thirdPartyLicenses: every exported human head derives from GNM Head v3's identity basis, Apache-2.0, so the
    attribution is written here and in the glTF asset's copyright (decision 1). The permission values are a DEFAULT the
    project has not ruled on (the plan: "sets those fields to the project's licence, by Skye's word"): open, credited,
    non-commercial, until she says;
  * humanoid.humanBones {bone: {node}}: the required set checked here (hips, spine, head, both upper / lower arms and
    hands, both upper / lower legs and feet) before writing (three-vrm refuses a VRM without them);
  * expressions.preset: the 18 VRM presets with NO binds (the one-driver rule: the runtime reads each expression's value
    and the creature's own control table drives the joints, so the morph budget stays for correctives and no morph
    leaves the tangent frame behind); 'custom' takes more names the same way (the ARKit controls of the face rig);
  * lookAt: type 'bone', offsetFromHeadBone, the four range maps 1:1 up to the eye's gated extreme (inputMaxValue =
    outputScale: the eye turns toward its target exactly, never past what the creature's lid gate proved; 11-01, was
    90 deg of input, which turned the eyes a quarter of the way);
  * firstPerson: no annotations (the eidoverse renders third person).

    ext = vrmc_vrm(human_bones, meta, look_at, custom_expressions=())   glb.j['extensions'] = {'VRMC_vrm': ext}
"""

REQUIRED = ('hips', 'spine', 'head', 'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightUpperArm', 'rightLowerArm',
            'rightHand', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot')
PRESETS = ('aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight', 'happy', 'angry', 'sad', 'relaxed',
           'surprised', 'neutral', 'lookUp', 'lookDown', 'lookLeft', 'lookRight')
GNM_ATTRIBUTION = ('GNM Head v3 (c) Google LLC, Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0): this '
                   'head derives from GNM\'s identity basis and joints, re-expressed on the Bestiary cage (the topology, '
                   'rings, rig, materials and measured conditioning are the Bestiary\'s). The body\'s reference and joint '
                   'placement use MakeHuman / MPFB2 core assets (CC0 1.0).')


def meta(name, version, authors=('the Bestiary forge (Claude), with Skye',), copyright_='the Bestiary',
         third_party=GNM_ATTRIBUTION, **perm):
    """the VRM 1.0 meta; perm overrides the default permissions (module docstring: not yet ruled on)"""
    m = {'name': name, 'version': version, 'authors': list(authors), 'copyrightInformation': copyright_,
         'references': [], 'thirdPartyLicenses': third_party, 'licenseUrl': 'https://vrm.dev/licenses/1.0/',
         'avatarPermission': 'everyone', 'allowExcessivelyViolentUsage': False, 'allowExcessivelySexualUsage': False,
         'commercialUsage': 'personalNonProfit', 'allowPoliticalOrReligiousUsage': False,
         'allowAntisocialOrHateUsage': False, 'creditNotation': 'required', 'allowRedistribution': True,
         'modification': 'allowModificationRedistribution', 'otherLicenseUrl': ''}
    m.update(perm)
    return m


def range_map(out_deg, in_deg=90.0):
    return {'inputMaxValue': float(in_deg), 'outputScale': float(out_deg)}


def look_at(offset_from_head_m, outer_deg, inner_deg, up_deg, down_deg, input_max_deg=None):
    """lookAt of type bone. The range maps are linear from 0 to inputMaxValue: with input_max_deg None (the default since
    11-01) each map's input max IS its gated extreme, so the eye turns exactly toward a target inside the lids' proven
    range and stops at its edge (with 90 deg inputs, the VRM habit, an eye turned 25/90 of the way to its target: a
    camera 13 deg off moved the eyes 3.6 deg, and the gaze missed it)"""
    rm = lambda d: range_map(d, d if input_max_deg is None else input_max_deg)  # noqa: E731
    return {'type': 'bone', 'offsetFromHeadBone': [float(x) for x in offset_from_head_m],
            'rangeMapHorizontalInner': rm(inner_deg), 'rangeMapHorizontalOuter': rm(outer_deg),
            'rangeMapVerticalDown': rm(down_deg), 'rangeMapVerticalUp': rm(up_deg)}


def _expr():
    return {'morphTargetBinds': [], 'materialColorBinds': [], 'textureTransformBinds': [], 'isBinary': False,
            'overrideBlink': 'none', 'overrideLookAt': 'none', 'overrideMouth': 'none'}


def vrmc_vrm(human_bones, meta_, look_at_, custom_expressions=()):
    """the extension (module docstring); human_bones {VRM bone name: node index}"""
    miss = [b for b in REQUIRED if b not in human_bones]
    if miss:
        raise ValueError(f'the humanoid lacks required VRM bones {miss} (three-vrm refuses it at load)')
    ext = {'specVersion': '1.0', 'meta': meta_,
           'humanoid': {'humanBones': {b: {'node': int(n)} for b, n in human_bones.items()}},
           'expressions': {'preset': {e: _expr() for e in PRESETS}},
           'lookAt': look_at_, 'firstPerson': {'meshAnnotations': []}}
    custom = [c for c in custom_expressions if c not in PRESETS]
    if custom:
        ext['expressions']['custom'] = {c: _expr() for c in custom}
    return ext
