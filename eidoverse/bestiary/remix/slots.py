"""SLOTS: the cyborg mutation's slot vocabulary and its CLOSED TABLE (work/bestiary/research/CYBORG_PLAN.md §4.1, §7;
the lead's decisions on its §9.1 and the plan check's four amendments, work/bestiary/PLAN.md 10-21; stage C0).

SKYE'S STANDING RULE (said twice): a cyborg part MATCHES ITS BODY SLOT. "a robot arm for a head? an antenna probe for a
hand?? doesn't make sense"; the old cyborg wolf wore a folded arm "as a huge sombrero hat". A head slot takes a head or
sensor module, a limb a limb, a back a mount.

A mismatch is impossible to write, by construction (CYBORG_PLAN §7.1):
  1. KINDS are DATA from anatomy. Each socket node carries extras.slot = {kind, side, interface, joint}, written by its
     generator (slot_extras()); the scene's extras.bestiary.chains hold the joint chains (chain_record()). A kind is
     NEVER read from a name: the octopus's socket_crown is its ARM crown, DESIGN.md's socket_crown a hat seat. A glb
     without slot extras takes no cyborg part (cyborg.untyped).
  2. FAMILIES declare the kinds they fit in one closed table (FAMILIES[f]['fits']). check_table() runs at IMPORT and
     refuses a table that breaks it, so the data cannot even be written wrong.
  3. SEATS are typed. A mount family seats only under its seat_<archetype> node with a validated entry; a seat archetype
     is allowed only under sockets of its kinds (SEAT_KINDS); a socket kind only on its anatomy's joints, per base
     (BASES[base]['joints']: the old bug was a back slot on a neck bone); a chain record on its base's chain joints, a
     head_region record on its base's HEAD REGION joints only (a machine head on an arm is "a robot head for a limb"),
     no joint in two chain records and no label twice (one limb, one replacement); a typed glb of a base with no slot
     table is refused, never left unchecked. check_manifest() errs on every breach.
  4. The resolver keys by KIND: plan() builds a placement only from (kind, site, row), and refuses a row whose part
     does not fit the kind of the table it sits in (amendment 1: the row is tested, not only a named site).
  5. SKYE'S RULE is its own data, apart from the closed table (KIND_REGION x PART_CLASS against NEVER): limb parts never
     on head-region kinds, head parts never on limb kinds, mounts never on head-region or limb kinds (her "antenna probe
     for a hand" was the old 0.16-scale TURRET on a wrist), and the thruster nozzle (a mount by its seat, class
     'siphon': the funnel's own replacement) likewise never on either; and a BACK takes only mounts (head, limb and
     siphon parts never on a back kind: C0b). Widening FITS cannot pass it: check_table()
     refuses such a table at import, and plan() refuses the pair (cyborg.never).
  6. G5, THE HAT PROBE, per base: a back mount must not ride a joint of the base's HEAD REGION, and its WHOLE reach
     envelope (the reach its seat's validated entry declares, not only its rest pose) must clear that region
     (head_probe()). The sombrero was a back module that reached a hat's position through its fit. A seat the probe
     cannot place (no world point; an offset seat without the socket's frame) or a head region with a joint lacking its
     position is refused, never measured from a stand-in (the old system's fallback to the mount point).

THE LEAD'S DECISIONS (10-21) built in:
  - the OCTOPUS takes NO back mount. Its mantle dome reads as its head (the hat sits there), so a turret or folded arm
    there is "a robot arm for a head" by perception even when every coded check passes. Its mantle apex is kind
    'mantle' (a head-region kind), the octopus has no 'back' slot at all, and its G5 head region holds the head, the
    whole mantle, the eyes and the funnel. Back mounts are for bases with a real back (the wolf, the beetle);
  - a head module and a hat are EXCLUSIVE on one socket in v1, and seat_shared covers EVERY accessory seated on the
    socket (the hat and the helmet on the head seat, the glasses and the mask on the face seat), not only the hat;
  - 'pronotum' and 'hips' are kinds with no family.

THE LEAD'S C0b CALLS (10-21; CYBORG_PLAN A.6, A.8, A.9) built in:
  - a socket is a PORT, as the robotics kit's are: its extras.slot also carries a FRAME (Z the outward normal, X the
    tangent: unit vectors in its joint's frame) and the DIMS of its interface (a mount's radius, bolt circle, bolts and
    pilot; an eye's radius and axis). slot_extras() refuses a degenerate frame or a mount without dims at export;
    check_manifest() errs on them (manifest.slot_frame, manifest.slot_dims);
  - cyborg.covered is an ERROR: a covering layer (growths and veins, plates, a cyborg surface region, an organic part, an
    accessory) left on a chain a part replaces, or seated on a socket a mount covers, floats (check_covered());
  - a kind table may hold a 'none' row: a level band picks no part, explicitly and by the seeded pick;
  - a BACK takes only mounts: head, limb and siphon parts never on a back kind (Skye's rule, its third clause);
  - for seat_shared, a base's SEAT GROUP is one seat (the octopus's head top and mantle apex: the dome reads as one
    head), and an ENCLOSING accessory claims every socket it encloses (the space helmet: the face as well as its head
    seat; recipe.py's accessory seats); an eye implant (a ball, no seat) stays allowed under either.

Pure Python (no numpy, no warp): the forge's exports (t13) and the recipe (recipe.validate, recipe.resolve_cyborg) both
read it. The recipe's cyborg section (CYBORG_PLAN §6.1): {level, seed, size, surface, parts: {kind: [rows]}, limbs:
[rows], glow, affixes}; a parts row {part, variant, level: [lo, hi], weight, side, site}; a limbs row {kind, chain (a
chain record's name or anatomical label), cut_joint, part, variant, level}.

    python eidoverse/bestiary/remix/slots.py      prints the closed table, Skye's rule and the per-base tables
"""
import math
import numbers
import re

# ============================================================================================ the vocabulary
# how a part attaches (CYBORG_PLAN §4.1): ball = rides its own joint inside an envelope (eyes); dome = replaces a fixed
# shell on its joint (the beetle's compound eye); mount = seats under a typed seat_<archetype> node; chain = replaces a
# chain record from a cut joint to the tip; region = a region swap at a generator (the machine head). 'none': a socket
# that takes no part (the crown centre inside the body, growth sites, the FX contract)
INTERFACES = ('ball', 'dome', 'mount', 'chain', 'region', 'none')
_M, _N = ('mount',), ('none',)
# SOCKET KINDS: {kind: (the interfaces a socket of this kind may declare, what it is)}. 31 from the plan plus 'mantle'
SOCKET_KINDS = {
    'head': (_M, "the head's dorsal seat: the hat's and the head module's (octopus socket_head_top on the collar joint "
                 "mantle_0; wolf and beetle socket_crown)"),
    'face': (_M, 'the bridge between the eyes (socket_eyes): glasses, mask, visor'),
    'eye': (('ball', 'dome'), "an eye: 'ball' rides its own joint (octopus, wolf), 'dome' is a fixed shell on the head "
                              "joint (the beetle's compound eye)"),
    'antenna': (_M, "an antenna's insertion (beetle socket_antenna_L/R): antenna swaps"),
    'horn': (_M, "a horn seat on the head (wolf and beetle socket_horn_*; the beetle's thoracic socket_pronotum_horn "
                 "is kind pronotum, CYBORG_PLAN §4.1)"),
    'ear': (_M, 'an ear root (wolf socket_ear_L/R): ear swaps'),
    'mouth': (_M, 'between the jaws: the beak (octopus socket_mouth, on the crown centre), FX'),
    'jaw': (_M, 'between the lower canines (wolf socket_jaw)'),
    'snout': (_M, 'mid-muzzle (wolf socket_snout): the mask seat, the beak swap'),
    'nose': (_M, 'the planum (wolf socket_nose)'),
    'mandible': (_M, "a mandible's condyle axis (beetle socket_mandible_L/R)"),
    'head_centre': (_M, 'the head centre (wolf socket_head)'),
    'neck': (_M, 'mid-neck (wolf socket_neck_collar): collars. A head-region kind: a mount on the neck stands over the '
                 'head (the sombrero: the old back slot resolved into the neck)'),
    'mantle': (_M, "a cephalopod's mantle dome (octopus socket_mantle_apex). It reads as the HEAD (the hat sits on it): "
                   "a head-region kind with no cyborg family (the lead, 10-21: no back mount on the octopus)"),
    'crown_centre': (_N, "the arm crown's centre, inside the body (octopus socket_crown; DESIGN.md's socket_crown is a "
                         "hat seat: a kind is never read from a name)"),
    'back': (_M, "a real back's dorsal midline (wolf socket_back_0..5 on spine_0..5; beetle socket_back_* on the elytra "
                 "and the scutellum): the back mount's seat"),
    'chest': (_M, "over the sternum or the prosternum: the tie's seat. Never a back mount (the old 'chest' anchor was a "
                  "BACK alias on a neck bone)"),
    'hips': (_M, 'the pelvis (wolf socket_hips): no family in v1 (the lead, 10-21)'),
    'pronotum': (_M, "the beetle's pronotum (socket_pronotum_top, a second hat seat for small-headed morphs; "
                     "socket_pronotum_horn, a thoracic horn): no family in v1 (the lead, 10-21)"),
    'siphon': (_M, "the funnel's exit (octopus socket_funnel): the thruster nozzle"),
    'abdomen_tip': (_M, 'the pygidium (beetle socket_abdomen_tip): tails, stingers'),
    'wing': (_M, 'a wing base (wolf socket_wing_* on the scapulae; beetle socket_wing_* on wing_0_*): remix wings'),
    'limb_tip': (_M, "a limb chain's tip (octopus socket_arm<j>_tip): a gripper, only on a replaced chain"),
    'paw': (_M, 'under the MCP or MTP (wolf socket_forepaw_*, socket_hindpaw_*): foot replacement'),
    'foot': (_M, "a tibia's distal end (beetle socket_foot_*): tarsus swaps"),
    'claw': (_M, 'a claw base (wolf socket_claw_*, socket_footclaw_*; beetle socket_claw_*)'),
    'wrist': (_M, 'the carpus (wolf socket_wrist_*)'),
    'ankle': (_M, 'the tarsus (wolf socket_ankle_*)'),
    'tail_base': (_M, 'the tail root (wolf socket_tail_base)'),
    'tail_tip': (_M, 'the tail tip (wolf socket_tail_tip)'),
    'growth': (_N, "a sculpt plan's growth site (socket_growth_*): never a cyborg part"),
    'fx': (_N, "the FX contract's sockets (socket_fx_*, socket_affix_*): never a cyborg part"),
    # HUMAN H4 (HUMAN_PLAN §6.7 item 2, the rig builder's staged patch, 11-01): the human's new kinds
    'back_limb': (_M, "a port for an ADDED limb on a back (the human's socket_back_upper_L/R over each scapula's "
                      "medial border, socket_back_lower_L/R on each posterior flank over the iliac crest): a ring where "
                      "the sisters' tentacles, wings or extra arms seat. Not a 'back' (a back takes only mounts, "
                      "Skye's rule): its own kind, region 'limb'"),
    'scalp': (_M, "a scalp plug (the human's socket_scalp_*): antennae (SOCKET on soft skin); hair cards ride it"),
    # (AXOLOTL AX11 + AX12, AXOLOTL_PLAN §6.2, §7.1, §10: the same kind for the axolotl's own gill ports, one meaning;
    # patches/axolotl_ax12_recipe.md's block for a tree where this human patch landed first)
    'gill': (_M, "a gill port: the axolotl's socket_gill_{1,2,3}_L/R on each ramus's root ring (its gill_r_0 joint), "
                 "a gill plug on the side of the human's neck behind the jaw angle (its socket_gill_*_L/R): "
                 "gill_graft's rami seat here"),
}
# CHAIN KINDS: the joint chains a chain part replaces from a listed cut to the tip (scene extras bestiary.chains)
CHAIN_KINDS = {
    'tentacle': 'an octopus arm (arm<j>_00..23)',
    'leg_fore': 'a forelimb (wolf: the scapula to the digits; human: the clavicle to the fingers)',
    'leg_hind': 'a hindlimb (wolf: the femur to the digits; human: the thigh to the ball of the foot)',
    'leg': 'an arthropod leg (beetle: the coxa to the claw)',
    'tail': 'a tail (wolf tail_0..7)',
    'antenna_chain': "an arthropod antenna (beetle: the scape, the funicle, the club's lamellae)",
    # AXOLOTL AX11 (the staged patch): a gill ramus's chain (gill_r_0..3), cut at its root ring (§6.2 gill root). The
    # plan named it 'gill', the socket kind's name: KINDS is one namespace (check_table), so it is 'gill_chain', as the
    # beetle's 'antenna' socket and 'antenna_chain' chain
    'gill_chain': "an axolotl gill ramus (gill_{r}_0..3_L/R, a child of neck_0): gill_graft swaps it from its root ring",
}
# REGION KINDS: regions swapped at a generator (scene extras bestiary.regions, written at C13)
REGION_KINDS = {'head_region': 'the head region, swapped for a machine head that keeps the jaw (C13)',
                'body_region': "the lower body under a waist ring (the human's): Mr. Hege's machine lower body, a "
                               "naga's tail, Scylla's crown (HUMAN_PLAN §6.2, §10; families later)"}
KINDS = {}
for _k, (_ifs, _doc) in SOCKET_KINDS.items():
    KINDS[_k] = dict(cls='socket', interfaces=_ifs, doc=_doc)
for _k, _doc in CHAIN_KINDS.items():
    KINDS[_k] = dict(cls='chain', interfaces=('chain',), doc=_doc)
for _k, _doc in REGION_KINDS.items():
    KINDS[_k] = dict(cls='region', interfaces=('region',), doc=_doc)

# ============================================================================================ the closed table
# FAMILIES (CYBORG_PLAN §7.2): each family's interfaces, the kinds it FITS (nothing else), its seat archetype (mounts),
# its variants (the first is the default; an unknown variant is an error, never a fallback: G2), what it requires, and
# the stage that builds it (§8). The catalog (status, triangles, forge capabilities) is recipe.CYBORG_PARTS
FAMILIES = {
    'eye_implant': dict(
        interfaces=('ball', 'dome'), fits=('eye',), seat=None, variants=('lens', 'lamp', 'compound'),
        variant_interface=dict(lens='ball', lamp='ball', compound='dome'), requires=(), stage='C4',
        doc="replaces the eye part on its own joint inside the eyeball's envelope (§4.3.1): 'lens' (a camera lens's "
            "rings) and 'lamp' (Pepper's lit field) on a ball eye; 'compound' (a sensor dome or lens cluster in the "
            "eye's sphere) on the beetle's dome eye (G8)"),
    'sensor_module': dict(
        interfaces=('mount',), fits=('head',), seat='module',
        variants=('dome', 'lens_cluster', 'lidar', 'dish', 'pan_tilt', 'mast'), requires=(), stage='C6',
        doc="a sensor module on a head seat (§4.3.3; K6, K12); exclusive with every accessory on that seat in v1"),
    'antenna_probe': dict(
        interfaces=('mount',), fits=('head', 'antenna', 'horn'), seat='module', variants=('whip',), requires=(),
        stage='C6', doc='a whip antenna with a glowing tip (§4.3.3; K6), on head, antenna and horn seats only'),
    'visor': dict(
        interfaces=('mount',), fits=('face',), seat='visor', variants=('slit', 'lens'), requires=(), stage='C6',
        doc="a visor on the face's bridge, fitted as glasses are (§4.3.4); exclusive with the glasses and the mask"),
    'back_mount': dict(
        interfaces=('mount',), fits=('back',), seat='mount', variants=('turret', 'folded_arm', 'mast'),
        requires=('mount_plate', 'reach'), stage='C10',
        doc="a mount on a REAL back (§4.5; her rule: 'back -> mounted arm/turret'): a turret, a folded arm (at least 3 "
            "segments and a tool, folded at rest: N10) or a mast, on a conforming mount plate (no pedestal: N6); G5's "
            "hat probe clears its whole reach envelope of the head region"),
    'thruster_nozzle': dict(
        interfaces=('mount',), fits=('siphon',), seat='nozzle', variants=('jet',), requires=(), stage='C10',
        doc='a jet nozzle where the funnel is (§4.5)'),
    'gripper': dict(
        interfaces=('mount',), fits=('limb_tip',), seat='tip', variants=('claw',), requires=('chain_replaced',),
        stage='C5', doc="a gripper on a MECH chain's tip (§4.4.3; K10): never on an organic tip"),
    'mech_tentacle': dict(
        interfaces=('chain',), fits=('tentacle',), seat=None, variants=('knuckled',), requires=('listed_cut',),
        stage='C5', doc='rigid knuckled segments on the same joints from a listed cut to the tip (§4.4; K9); v1: '
        'ONE per creature (the lead\'s C5c call: the runtime carries one replaced arm\'s ground line and AO floor; '
        'plan() refuses a second, cyborg.limit)'),
    'mech_leg': dict(
        interfaces=('chain',), fits=('leg_fore', 'leg_hind', 'leg'), seat=None, variants=('rigid',),
        requires=('listed_cut',), stage='C11', doc='a leg replaced from a listed cut through the paw or tarsus (G6)'),
    'mech_arm': dict(
        interfaces=('chain',), fits=('leg_fore',), seat=None, variants=('robot_hand',),
        requires=('listed_cut', 'ring_record', 'chain_role_arm'), stage='C3',
        doc="an ARM replaced from a listed cut (the wrist ring: my robot's hand; C5: the elbow and the shoulder) on a "
            "leg_fore chain whose ROLE is arm (the human's arm_L / arm_R: chain anatomy 'mech_arm' once grafted), so a "
            "quadruped's fore LEG never takes it (mech_leg's); a SOCKET collar in the base skin, the part's own set "
            "(cyborg_robot/c3)"),
    'mech_tail': dict(
        interfaces=('chain',), fits=('tail',), seat=None, variants=('segmented',), requires=('listed_cut',),
        stage='C11', doc='a tail replaced from a listed cut to its tip'),
    'mech_antenna': dict(
        interfaces=('chain',), fits=('antenna_chain',), seat=None, variants=('segmented',),
        requires=('listed_cut',), stage='C12', doc='an antenna chain replaced from its cut (scape, funicle, club)'),
    'machine_head': dict(
        interfaces=('region',), fits=('head_region',), seat=None,
        variants=('industrial', 'military', 'utility', 'scout'), requires=('keeps_jaw',), stage='C13',
        doc="a head-region swap that KEEPS the jaw joint and the talk (K7, N4, G6)"),
    # ORGAN FAMILIES (research/CROSSBREED_DESIGN.md §1.2; the lead's decision 6: ONE closed table, the organic half
    # beside the cyborg one): their parts are GRAFTS, forged for their socket and assembled (forge/graft.py,
    # graft_socket.py, assemble.py), never cyborg rows (check_recipe refuses them in cyborg.limbs: cyborg.organ). FITS
    # stay one to one until Skye says which crosses make sense (decision 12); M2's: a limb for a limb
    'leg_graft': dict(
        interfaces=('chain',), fits=('tentacle',), seat=None, variants=('stag_beetle_fore',),
        requires=('listed_cut', 'ring_record'), stage='M2', organ=True,
        doc="an arthropod LEG from its knee on (the donor's tibia, tarsomeres and claws at its author scale) in a "
            "SOCKET seam, a membrane collar on a listed cut's ring (CROSSBREED §8 M2), posed by the arthropod step "
            "solver"),
}

# ============================================================================================ Skye's rule (apart from FITS)
# The kinds' anatomical region and the families' part class, kept APART from the closed table: no FITS pair may break
# NEVER (check_table refuses the table at import), and plan() refuses a never pair whatever FITS says (cyborg.never).
# Written from her words: "a robot arm for a head? an antenna probe for a hand??" and the sombrero (a folded arm worn
# over the head); 'back -> mounted arm/turret (a mount, not a replacement, is fine there)'
KIND_REGION = dict(
    # what reads as the head (the octopus's mantle dome, where the hat sits; the neck, which a mount stands over)
    head='head', face='head', eye='head', antenna='head', horn='head', ear='head', mouth='head', jaw='head',
    snout='head', nose='head', mandible='head', head_centre='head', neck='head', mantle='head', antenna_chain='head',
    head_region='head',
    # AXOLOTL AX11 (the staged patch; AXOLOTL_PLAN §7.1: KIND_REGION gill = head): the gill chain (the gill port's
    # gill='head' is the human patch's line below: one keyword, never two)
    gill_chain='head',
    # the limbs, their distal ends and the tail
    wing='limb', limb_tip='limb', paw='limb', foot='limb', claw='limb', wrist='limb', ankle='limb', tail_base='limb',
    tail_tip='limb', tentacle='limb', leg_fore='limb', leg_hind='limb', leg='limb', tail='limb',
    # a real back takes a MOUNT and nothing else (her rule's third clause; the lead's C0b call)
    back='back',
    # HUMAN H4: an added limb's port on the back is a limb kind (a limb part there is a limb on a limb port, never
    # "a limb part on the back"); the scalp and the gills read as the head; the lower body as the body
    back_limb='limb', scalp='head', gill='head', body_region='body',
    # the rest of the body takes the families FITS lists, or none
    chest='body', hips='body', pronotum='body', siphon='body', abdomen_tip='body', crown_centre='body',
    growth='none', fx='none')
PART_CLASS = dict(
    eye_implant='head', sensor_module='head', antenna_probe='head', visor='head', machine_head='head',
    mech_antenna='head',                                   # an antenna is the head's sensor, not a limb
    mech_tentacle='limb', mech_leg='limb', mech_arm='limb', mech_tail='limb', gripper='limb',
    leg_graft='limb',                                      # an organ family's leg: a limb for a limb (CROSSBREED M2)
    back_mount='mount',
    thruster_nozzle='siphon')                              # the funnel's own replacement
NEVER = {('limb', 'head'): 'a limb part on the head ("a robot arm for a head?")',
         ('head', 'limb'): 'a head part on a limb ("an antenna probe for a hand??")',
         ('mount', 'head'): 'a mount on the head (the sombrero: a folded arm worn as a hat)',
         ('mount', 'limb'): 'a mount on a limb (the "antenna probe for a hand" was a 0.16-scale TURRET on a wrist)',
         # the thruster nozzle seats on seat_nozzle (a mount by its seat); its own class keeps it on the funnel it
         # replaces, and like any mount it never stands on the head or a limb (the C0 check: FITS widened to
         # head / limb_tip / neck / mantle passed every gate before these two rows)
         ('siphon', 'head'): 'a jet nozzle on the head (a mount by its seat; a head slot takes a head or sensor part)',
         ('siphon', 'limb'): 'a jet nozzle on a limb (a mount by its seat; a limb slot takes a limb)',
         # "a back -> mounted arm/turret (a mount, not a replacement, is fine there)": a back takes ONLY mounts (the
         # lead's C0b call), so every other class is never on a back kind; the nozzle is the funnel's own replacement,
         # not a back mount
         ('head', 'back'): 'a head part on the back (a head or sensor module, an eye, an antenna: a back takes only '
                           'mounts)',
         ('limb', 'back'): 'a limb part on the back (a limb or a gripper: a back takes only mounts)',
         ('siphon', 'back'): 'a jet nozzle on the back (the funnel\'s own replacement: a back takes only back mounts)'}


def never(family, kind, part_class=None, kind_region=None):
    """Skye's rule for a (family, kind) pair: the reason it is never allowed, or None"""
    pc, kr = (part_class or PART_CLASS).get(family), (kind_region or KIND_REGION).get(kind)
    return NEVER.get((pc, kr))


# ============================================================================================ typed seats
# the kinds each seat archetype may hang under (amendment 2). The cyborg seats follow FAMILIES (a family's seat goes
# under the kinds it fits, nowhere else); the accessories' seats (work/bestiary/patches/accessories_fit.md) are listed
CYBORG_SEATS = {}
for _f, _d in FAMILIES.items():
    if _d['seat']:
        CYBORG_SEATS.setdefault(_d['seat'], [])
        CYBORG_SEATS[_d['seat']] += [k for k in _d['fits'] if k not in CYBORG_SEATS[_d['seat']]]
CYBORG_SEATS = {a: tuple(v) for a, v in CYBORG_SEATS.items()}
ACCESSORY_SEATS = dict(
    hat=('head', 'pronotum'),        # pronotum: BEETLE_PLAN §6.5's second seat_hat on socket_pronotum_top (small heads)
    helmet=('head',), glasses=('face',), monocle=('eye',),
    mask=('face', 'snout'),          # snout: WOLF_PLAN §6.4's seat_mask on socket_snout
    tie=('chest',))
SEAT_KINDS = dict(ACCESSORY_SEATS, **CYBORG_SEATS)

# ============================================================================================ per base
# Each base's slot table, from its GENERATOR's joint names (the validator checks a typed kind against them; it never
# infers a kind from a name): joints = {socket kind: the joints a socket of that kind may hang on}; chains = {chain
# kind: the joints its records may hold}; a kind the base lacks has no entry, and 'lacks' says why where it matters.
# head_region (G5): the joints whose bones read as the head, and head_margin the region's radius about them [E: set from
# the anatomy; C10 replaces the capsules with the block-out's surface]
BASES = {
    'octopus': dict(
        src='forge/species/octopus_rig.py build(): root, body, head, mantle_0..3, eye_L/R, funnel_0/1, arm<j>_00..23',
        joints=dict(eye=r'eye_[LR]', face=r'head', head=r'head|mantle_0', mantle=r'mantle_[0-3]',
                    siphon=r'funnel_[01]', mouth=r'body', crown_centre=r'body', limb_tip=r'arm[0-7]_23',
                    growth=r'.+', fx=r'.+'),
        chains=dict(tentacle=r'arm[0-7]_\d\d'), interfaces=dict(eye='ball'),
        lacks=dict(back='the octopus takes NO back mount: its mantle dome reads as its head (the hat sits there), so a '
                        'turret or folded arm on it is "a robot arm for a head" by perception (the lead, 10-21)'),
        head_region=r'head|mantle_[0-3]|eye_[LR]|funnel_[01]',
        # the mantle's p50 section radius, 56.9 mm (CYBORG_PLAN §3.4 [D-pl])
        head_margin=0.057,
        # SEAT GROUPS (the lead's C0b call): the head top and the mantle apex are ONE seat for module-xor-hat, the dome
        # reads as one head (a hat explicitly on the apex beside a head module is cyborg.seat_shared)
        seat_groups=[('head', 'mantle')],
        # cyborg.covered: each chain kind's region in the recipe's layer masks (recipe.SPECIES regions), and where the
        # forge roots growths along it by default (forge/growth.py octopus_sites: the reference arm's grid from s 0.04,
        # rooted below s_max 0.75 and replicated onto all eight arms; c00_slots.py G10 reads it back from the source)
        chain_regions=dict(tentacle='arm'), growth_s=dict(tentacle=(0.04, 0.75))),
    'wolf': dict(
        src='forge/families/limbed.py skeleton() (118 joints, work/bestiary/wolf/skeleton.json); WOLF_PLAN §6.4',
        joints=dict(head=r'head', head_centre=r'head', face=r'head', eye=r'eye_[LR]', snout=r'head', nose=r'head',
                    jaw=r'jaw', mouth=r'head', ear=r'ear_0_[LR]', horn=r'head', neck=r'neck_[0-2]', chest=r'spine_5',
                    back=r'spine_[0-5]', wing=r'scapula_[LR]', hips=r'pelvis', tail_base=r'tail_0',
                    tail_tip=r'tail_\d+', paw=r'meta(carpus|tarsus)_[LR]',
                    claw=r'[fh]_digit\d_1_[LR]|f_dewclaw_[LR]', wrist=r'carpus_[LR]', ankle=r'tarsus_[LR]',
                    growth=r'.+', fx=r'.+'),
        chains=dict(
            leg_fore=r'(scapula|humerus|humerus_twist|radius|radius_twist|carpus|metacarpus|f_digit\d_[01]|'
                     r'f_dewclaw)_[LR]',
            leg_hind=r'(femur|femur_twist|tibia|tibia_twist|tarsus|metatarsus|h_digit\d_[01])_[LR]',
            tail=r'tail_\d+'), interfaces=dict(eye='ball'),
        notes=['a back slot rides spine_0..5 only: neck_* and the head are the head region (the old bug: a back slot '
               'on a neck bone, the sombrero)'],
        head_region=r'head|jaw|tongue_\d|eye_[LR]|lid_(up|lo)_[LR]|ear_[01]_[LR]|snout|nose|brow_[LR]|'
                    r'lip_(up|lo)_[LR]|neck_[0-2]',
        # about half the skull's zygomatic breadth and the neck's radius [E: WOLF_PLAN's ZyB / CbL 0.58-0.62]
        head_margin=0.07,
        # (no growth planner yet: a growth covers a whole chain until one exists)
        chain_regions=dict(leg_fore='limb', leg_hind='limb', tail='tail')),
    'beetle': dict(
        src='forge/families/arthropod.py skeleton() (104 joints at x10, work/bestiary/beetle/skeleton.json); '
            'BEETLE_PLAN §6.5',
        joints=dict(head=r'head', face=r'head', eye=r'head', mandible=r'mandible_[LR]', horn=r'head',
                    antenna=r'head', mouth=r'head', pronotum=r'pronotum', chest=r'pronotum',
                    claw=r'claw_[fmh]_[LR]', foot=r'tibia_[fmh]_[LR]', back=r'elytron_[LR]|body',
                    wing=r'wing_0_[LR]', abdomen_tip=r'abdomen_1', growth=r'.+', fx=r'.+'),
        chains=dict(leg=r'(coxa|trochanter|femur|tibia|tarsus_[1-5]|claw)_[fmh]_[LR]',
                    antenna_chain=r'(antenna_[0-3]|lamella_[0-3])_[LR]'),
        interfaces=dict(eye='dome'),          # the compound eye rides the head joint: a fixed shell (G8)
        notes=['the pronotum is kind pronotum, with no family (the lead, 10-21); a back slot rides the elytra or the '
               'scutellum (body) only'],
        head_region=r'head|mandible_[LR]|antenna_[0-3]_[LR]|lamella_[0-3]_[LR]|palp_(max_[01]|lab_0)_[LR]',
        # about half the head's width at x10 [E]
        head_margin=0.05,
        # (the antennae are no region of the beetle's layer masks: 'antenna' is what its anatomy:antennae sites reach)
        chain_regions=dict(leg='leg', antenna_chain='antenna')),
    # HUMAN H4 (HUMAN_PLAN §6.1, §6.7 item 1; the rig builder's staged patch, 11-01): the skeleton of
    # forge/species/human_skeleton.py (94 joints: the UE mannequin's stems with the house's side suffix) and the face
    # rig of human_face.py (22 joints on the head and the jaw)
    'human': dict(
        src='forge/species/human_skeleton.py joint_table() (94 joints) + human_face.py (22 face joints); HUMAN_PLAN §4',
        joints=dict(head=r'head', face=r'head', eye=r'eye_[LR]', horn=r'head', ear=r'head', mouth=r'head|jaw',
                    neck=r'neck_0[12]', chest=r'spine_0[45]', back=r'spine_0[1-5]', back_limb=r'spine_0[1-5]',
                    tail_base=r'pelvis', wrist=r'lowerarm_[LR]|lowerarm_twist_0[12]_[LR]|hand_[LR]',
                    ankle=r'calf_[LR]|calf_twist_0[12]_[LR]|foot_[LR]', hips=r'pelvis',
                    claw=r'(thumb|index|middle|ring|pinky)_03_[LR]|ball_[LR]', scalp=r'head', gill=r'neck_0[12]|head',
                    growth=r'.+', fx=r'.+'),
        chains=dict(
            leg_fore=r'(clavicle|upperarm|upperarm_twist_0[12]|lowerarm|lowerarm_twist_0[12]|hand|thumb_0[1-3]|'
                     r'(index|middle|ring|pinky)_(metacarpal|0[1-3])|helper_(shoulder|elbow|wrist))_[LR]',
            leg_hind=r'(thigh|thigh_twist_0[12]|calf|calf_twist_0[12]|foot|ball|helper_knee)_[LR]'),
        interfaces=dict(eye='ball'),
        notes=['a back MOUNT rides spine_01..05 (the cyborg back mounts, under G5); the four back-limb PORTS are kind '
               'back_limb on the same spine joints (a ring for an added limb, never a mount)',
               'the waist ring is a body_region record (the lower body: Hege, a naga), pelvis staying its root'],
        head_region=r'head|jaw|tongue_0[1-3]|eye_[LR]|neck_0[12]|lid_(upper|lower)_[LR]|brow_(inner|mid|outer)_[LR]|'
                    r'cheek_[LR]|nostril_[LR]|lip_(upper|lower)_[CLR]|lip_corner_[LR]',
        # HUMAN_PLAN §6.1: about 0.10 m [E]
        head_margin=0.10,
        chain_regions=dict(leg_fore='limb', leg_hind='limb')),
    # AXOLOTL AX11 (AXOLOTL_PLAN §6, §10; the builder's staged patch, 11-01; AX12 folded it in, 11-02): the sprawl
    # skeleton at x4 (forge/families/sprawl.py skeleton(): the plan's 124 joints and AX10b's 8 helpers, 132)
    'axolotl': dict(
        src='forge/families/sprawl.py skeleton() (132 joints at x4, work/bestiary/axolotl/skeleton.json); '
            'AXOLOTL_PLAN §10',
        joints=dict(head=r'head', face=r'head', eye=r'eye_[LR]', horn=r'head', mouth=r'head', jaw=r'jaw',
                    gill=r'gill_[123]_0_[LR]', back=r'spine_[0-6]', wing=r'scapula_[LR]', chest=r'spine_6',
                    hips=r'pelvis', tail_base=r'tail_0', tail_tip=r'tail_\d+', paw=r'meta(carpus|tarsus)_[LR]',
                    wrist=r'carpus_[LR]', ankle=r'tarsus_[LR]', growth=r'.+', fx=r'.+'),
        chains=dict(
            leg_fore=r'(scapula|humerus|humerus_twist|radius|radius_twist|carpus|metacarpus|f_digit\d_[01])_[LR]',
            leg_hind=r'(femur|femur_twist|tibia|tibia_twist|tarsus|metatarsus|h_digit\d_[01])_[LR]',
            tail=r'tail_\d+', gill_chain=r'gill_[123]_[0-3]_[LR]'),
        interfaces=dict(eye='ball'),
        notes=['a back slot rides spine_0..6 only (the back ports over spine_1, spine_3, spine_4); the gills hang under '
               'neck_0, ahead of no head joint, so a head swap at the poll keeps them (§6.3)',
               'the hat seat (seat_hat on socket_crown) carries its validation against the gill fan\'s swept volume '
               '(the study-G frog lesson as data, §10)'],
        # §6.3: the head region for G5 holds head, its descendants, neck_0 and the gill chains (a turret's reach
        # must clear the gill fan)
        head_region=r'head|jaw|tongue|eye_[LR]|neck_0|throat|gill_[123]_[0-3]_[LR]',
        # about half the head's width at x4 (HW 151.6 mm) [E]
        head_margin=0.076,
        chain_regions=dict(leg_fore='limb', leg_hind='limb', tail='tail', gill_chain='gill')),
}

# the cyborg section's keys (CYBORG_PLAN §6.1) and its rows' keys; an unknown key is an error, never skipped (G2: the
# old cyborg() skipped unknown slot keys silently)
CYBORG_KEYS = ('level', 'seed', 'size', 'surface', 'parts', 'limbs', 'glow', 'affixes')
ROW_KEYS = ('part', 'variant', 'level', 'weight', 'side', 'site', 'note')
LIMB_KEYS = ('kind', 'chain', 'cut_joint', 'part', 'variant', 'level', 'hose', 'note')
# a limb row's HOSE (C5b, the lead's decision 4; A.9 decision 6: both ends on a plate or a mount, never a free
# end): 'plates' runs one braided hose from the section's plated region (its plates row) to the part's flange
# (forge/cyborg_hose.py: its own mesh, never paint); absent or None: no hose
HOSE_FROM = ('plates',)
AFFIXES = ('seam_glow', 'scan', 'overheat')       # the cyborg runtime affixes (§6.3; C8 draws them)
SIDES = ('', 'L', 'R')
# the explicit NO-PART row of a kind table (CYBORG_PLAN A.6, A.8; study T gives every appearance class a Null entry): the
# seeded weighted pick takes it like any row, and the site then stays empty, deterministically (the lead's C0b call)
NONE = 'none'
assert NONE not in FAMILIES, 'the none row\'s name is reserved'

# ============================================================================================ the surface layer (C1)
# PLATE REGIONS per base (CYBORG_PLAN §4.2.6; the lead's C1 call: plates on UNIQUE texels; the octopus's arms set is
# STACKED, so plates go on the mantle first). A surface row names one by `region`, a name of its base's own regions
# (recipe.SPECIES 'regions'); each carries the chart forge/cyborg.py lays it out on, its texture set, whether that set
# is stacked, the canonical low's region ids it may cover (the forge refuses a row that leaves them: nothing is clipped
# silently), its default extent, and s_max, the share past which its chart's strip leaves those texels. A STACKED
# region takes plates on every arm that shares its texels or none: its row says arms='all' (cyborg.stacked). A row
# without a region covers every UNIQUE region of its base (K1's whole-creature plating; a stacked one only by name). A
# base without an entry takes no plates yet (cyborg.surface; C11, C12). [D] on the canonical low (work/bestiary/octopus/
# low.npz, tests/c01_layout.py prints it): arm 0's aboral strip is the head set's crown top (region 1, its own texels)
# to s 0.33, the stacked arms set (region 3) from 0.34; the mantle region is §4.2.3's.
# ROWS AND SIZES ARE THE REGION'S RULE (the lead's C2 call 1; the layout keeps every plate inside its plate_R by
# construction and c01 gates exactly that, no tolerance past it): rows=<int> rows along the chart, each row's plates
# sized inside plate_R (no sliver at a row's end: its remainder spreads over the row's plates); rows='joints' ONE ROW PER
# JOINT SEGMENT (A.2.2 "plates follow segments": no plate spans a bend; a partial segment at the region's end too short
# for one row of heads stays bare). THE ARM (the lead's C3 call 1): per_row=1, ONE PLATE PER JOINT SEGMENT across its
# strip (about 40 x 55 mm on the crown top: the armour lames' read, each rigid segment one plate, the joints the seams),
# 'ends' heads at both of its joint ends; its plate_R is the rows' own size (C2's 0.8-1.4 R cut each segment into 3
# staves of 3.7-11.5 : 1 that held no heads)
JOINT_ROWS = 'joints'
PLATE_REGIONS = dict(
    octopus=dict(
        body=dict(chart='mantle', set='head', stacked=False, low_regions=(0,), s=(0.14, 0.47), theta_deg=70.0, rows=3,
                  plate_R=(0.45, 0.70), s_max=0.54,
                  doc='the dorsal mantle on the body loft\'s chart (the head set: unique texels); the first target\'s '
                      'plates, the plan\'s 0.45-0.70 R (about 13 plates; study G\'s median 0.91 R about 5)'),
        crown_top=dict(chart='arm', set='head', stacked=False, low_regions=(1,), s=(0.06, 0.32), theta_deg=50.0,
                       rows=JOINT_ROWS, per_row=1, plate_R=(2.00, 2.50), s_max=0.33,
                       doc='an arm\'s proximal aboral strip on the head set\'s crown top (every arm\'s texels its own, '
                           'so a row may name arms); ONE PLATE PER JOINT SEGMENT across the strip, \'ends\' heads at '
                           'both joint ends: the arm\'s rule (the lead\'s C3 call 1), its band the rows\' own size'),
        arm=dict(chart='arm', set='arms', stacked=True, low_regions=(3,), s=(0.36, 0.47), theta_deg=50.0,
                 rows=JOINT_ROWS, per_row=1, plate_R=(2.00, 2.50), s_max=1.0,
                 doc='the arms set beyond the crown top: STACKED (all eight arms on arm 0\'s texels), so plates there '
                     'print on every arm or none; the arm\'s rule as on the crown top')))
# the arms an arm-chart region's row may name, per base (the C1 check: unknown labels passed check_surface, against G2):
# chain j = arm<j> carries the anatomical label PLATE_ARMS[base][j], recipe.SPECIES[base]['arm_labels'] (this module
# stays pure Python, so the labels are written here; work/bestiary/tests/c01_layout.py L6 asserts the two equal)
PLATE_ARMS = dict(octopus=('R1', 'R2', 'R3', 'R4', 'L4', 'L3', 'L2', 'L1'))
# the surface row's keys (CYBORG_PLAN §6.1 as A.8 changes it: seams in TEXELS, 3 by default and 4 'chunky'; their depth
# a ratio of the width, 0.5; fasteners 'ends', 2-4 heads per plate at its fastened ends in groups pitched 1.8-3.5 head
# diameters, 'riveted' the plan's corners and edges at 3.4 D; heads 10 texels; plate sizes in local radii R). Unknown
# keys are errors (G2), and the old absolute widths are gone (seam_depth_mm: the depth is a ratio now)
SURFACE_KEYS = ('kind', 'region', 'chart', 'arms', 's', 'theta_deg', 'plate_R', 'rows', 'seams', 'seam_tx',
                'seam_depth', 'fasteners', 'heads', 'pitch_D', 'inset_D', 'fastener_tx', 'plate_t_mm', 'junction', 'scar',
                'finish', 'paint', 'paint_type', 'accent', 'accent_share', 'fastener_finish', 'glow_seams', 'glow_finish',
                'seed', 'note')
SEAM_TX = dict(standard=3, chunky=4)
RIVET_PITCH_D = 3.4
# the two PLATE LOOKS for Skye (CYBORG_PLAN §4.2.3, §9.2 item 1; C3 builds each its own run): the region's own sizes
# (the octopus mantle: the plan's 0.45-0.70 R in 3 rows, about 13-15 plates), and 'large', study G's median 0.91 R
# (0.80-1.05 in 2 rows, about 5 plates): surface-row overrides
PLATE_LOOKS = dict(default=dict(), large=dict(plate_R=(0.80, 1.05), rows=2))
SURFACE_DEFAULTS = dict(plate_R=(0.45, 0.70), seams='standard', seam_depth=0.5, fasteners='ends', heads=(2, 4),
                        pitch_D=(1.8, 3.5), inset_D=2.0, fastener_tx=10.0, plate_t_mm=1.2, junction='crease',
                        scar='band', finish='paint', paint='#e8e4dc', paint_type='white', accent=None, accent_share=0.0,
                        fastener_finish='black_oxide', glow_seams=False, glow_finish='glazed', seed=None)
SURFACE_CHOICES = dict(seams=tuple(SEAM_TX), fasteners=('ends', 'riveted', 'none'), junction=('crease', 'ridge'),
                       scar=('band', 'none'), finish=('paint', 'titanium', 'anodised', 'carbon'),
                       paint_type=('white', 'metallic', 'colour'), fastener_finish=('black_oxide', 'bare'),
                       glow_finish=('glazed', 'bare'))
_RETIRED_SURFACE = dict(seam_depth_mm='the depth is seam_depth, a ratio of the width (A.8: 0.5)',
                        fastener_mm='heads are sized in texels (fastener_tx, 10)', seam_mm='seams are sized in texels '
                        '(seams / seam_tx)')
# THE FEED LINES (the lead's C3b; CYBORG_PLAN A.2.2 "feed lines", the lead's A.9 decision 6: "a surface-region kind
# `feed` whose two ends must land on a plate or a mount (the contact gate: never a free end)"): a surface row of kind
# 'feed' lays cables over a PLATED region: LINKS between two of its plates (crossing the seams between them under
# clamps) and DIVES from one of its plates into the skin through a GROMMET (the line's own mount, sunk into the skin).
# Its ends land on its region's plates (or, from C10, a mount), so a feed row needs a plates row of the same section on
# that region: alone it has nowhere to land (cyborg.feed); one feed row per region (two would route over each other).
# forge/cyborg.py feed_layout routes the lines; in C3b on the mantle only (FEED_REGIONS: an arm's strip is one plate per
# joint segment, and its cables are the mech arm's hose, C5). A plates row may say kind='plates' (the default)
SURFACE_KINDS = ('plates', 'feed')
FEED_KEYS = ('kind', 'region', 'links', 'dives', 'sleeve', 'seed', 'note')
FEED_DEFAULTS = dict(links=2, dives=3, sleeve='ribbed', seed=None)
FEED_CHOICES = dict(sleeve=('ribbed', 'smooth'))
FEED_REGIONS = dict(octopus=('body',))
FEED_MAX = 6                 # lines of each kind (links, dives) per feed row


class SlotError(ValueError):
    """resolve_cyborg's refusal: every error problem, each naming its slot and its part"""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('the cyborg slot rule refuses this recipe:\n' + '\n'.join(
            f'  {p["code"]} {p["where"]}: {p["message"]}' for p in self.problems))


def _P(severity, code, where, message):
    return dict(severity=severity, code=code, where=where, message=message)


def _match(rx, name):
    return bool(name) and re.fullmatch(rx, str(name)) is not None


# ============================================================================================ the table's own check
def check_table(families=None, kind_region=None, part_class=None):
    """the closed table's consistency (run at import; the arguments let a test check a WIDENED table): every family's
    kinds known, its interfaces in INTERFACES and matching its kinds' class, its variants and default present, its
    seat's kinds all its own; Skye's rule data covering every kind and family; and NO fits pair breaking NEVER.
    Returns problem strings ([] = consistent)"""
    fam = families if families is not None else FAMILIES
    kr = kind_region if kind_region is not None else KIND_REGION
    pc = part_class if part_class is not None else PART_CLASS
    bad = []
    for k in KINDS:
        if k not in kr:
            bad.append(f'kind {k!r} has no region in KIND_REGION (Skye\'s rule cannot judge it)')
    for k, d in SOCKET_KINDS.items():
        if not d[0] or any(i not in INTERFACES for i in d[0]):
            bad.append(f'socket kind {k!r}: interfaces {d[0]} not in {INTERFACES}')
    for f, d in fam.items():
        if f not in pc:
            bad.append(f'family {f!r} has no part class in PART_CLASS')
        if not d.get('variants'):
            bad.append(f'family {f!r} has no variants (its default is the first)')
        for i in d['interfaces']:
            if i not in INTERFACES:
                bad.append(f'{f}: unknown interface {i!r}')
        for k in d['fits']:
            if k not in KINDS:
                bad.append(f'{f} fits unknown kind {k!r}')
                continue
            if not set(d['interfaces']) & set(KINDS[k]['interfaces']):
                bad.append(f'{f} ({d["interfaces"]}) fits {k!r}, a {KINDS[k]["cls"]} kind ({KINDS[k]["interfaces"]})')
            why = never(f, k, pc, kr)
            if why:
                bad.append(f'{f} fits {k!r}: Skye\'s rule refuses it ({why})')
        if (d.get('seat') is None) == ('mount' in d['interfaces']):
            bad.append(f'{f}: a mount family needs a seat archetype, any other none (seat {d.get("seat")!r})')
        vi = d.get('variant_interface')
        if vi and (set(vi) != set(d['variants']) or any(v not in d['interfaces'] for v in vi.values())):
            bad.append(f'{f}: variant_interface {vi} does not cover its variants with its interfaces')
    for (c, r) in NEVER:
        if c not in set(pc.values()) or r not in set(kr.values()):
            bad.append(f'NEVER names an unused class or region: {(c, r)}')
    for base, B in BASES.items():
        for k in list(B['joints']) + list(B['chains']) + list(B.get('lacks') or {}):
            if k not in KINDS:
                bad.append(f'BASES[{base!r}] names unknown kind {k!r}')
        for k in B.get('lacks') or {}:
            if k in B['joints'] or k in B['chains']:
                bad.append(f'BASES[{base!r}] both has and lacks {k!r}')
        for k, i in (B.get('interfaces') or {}).items():
            if k not in SOCKET_KINDS or i not in SOCKET_KINDS[k][0]:
                bad.append(f'BASES[{base!r}].interfaces: {k!r} cannot be {i!r}')
        for k in B['joints']:
            if k in KINDS and KINDS[k]['cls'] != 'socket':
                bad.append(f'BASES[{base!r}].joints lists {k!r}, not a socket kind')
        for k in B['chains']:
            if k in KINDS and KINDS[k]['cls'] != 'chain':
                bad.append(f'BASES[{base!r}].chains lists {k!r}, not a chain kind')
        for grp in B.get('seat_groups') or ():
            for k in grp:
                if k not in B['joints'] or KINDS.get(k, {}).get('cls') != 'socket':
                    bad.append(f'BASES[{base!r}].seat_groups names {k!r}, not a socket kind the {base} has')
        for k in B.get('chain_regions') or {}:
            if k not in B['chains']:
                bad.append(f'BASES[{base!r}].chain_regions names {k!r}, not a chain kind the {base} has')
        for k, sr in (B.get('growth_s') or {}).items():
            if k not in B['chains'] or not (isinstance(sr, tuple) and len(sr) == 2 and 0.0 <= sr[0] < sr[1] <= 1.0):
                bad.append(f'BASES[{base!r}].growth_s[{k!r}] = {sr!r}: a chain kind it has and (lo, hi) shares in 0..1')
    for a, ks in SEAT_KINDS.items():
        for k in ks:
            if k not in SOCKET_KINDS:
                bad.append(f'seat_{a} names {k!r}, not a socket kind')
    return bad


def allowed_pairs(families=None):
    """the closed table's allowed (family, kind) pairs"""
    fam = families if families is not None else FAMILIES
    return [(f, k) for f, d in fam.items() for k in d['fits']]


_TABLE = check_table()
if _TABLE:                                   # the data cannot even be written wrong (CYBORG_PLAN §7.1 #2)
    raise ImportError('remix/slots.py: the closed table is inconsistent:\n  ' + '\n  '.join(_TABLE))
# the table's two halves (decision 6): the CYBORG families (recipe.CYBORG_PARTS' catalog, the cyborg rows) and the ORGAN
# families (recipe.GRAFT_PARTS' catalog, the recipe's grafts: never a cyborg row)
ORGAN_FAMILIES = tuple(f for f, d in FAMILIES.items() if d.get('organ'))
CYBORG_FAMILIES = tuple(f for f in FAMILIES if f not in ORGAN_FAMILIES)


# ============================================================================================ sockets as ports
# A socket is a PORT, as the robotics kit's are (CYBORG_PLAN A.6, A.7 U1; the lead's C0b call): besides its kind,
# side, interface and joint, its extras.slot carries a FRAME, Z the outward normal and X the tangent, unit vectors IN
# ITS JOINT'S FRAME (the kit's frameMatrix: eidoverse/robotics/index.js:55-71), and the DIMS of its interface in the
# kit's port pattern (research/cyborg_work/games/kit_body/NOTES.md §2.3: radius_m, bolt_circle_radius_m, bolt_count,
# pilot_radius_m): a mount's radius, bolt circle radius, bolts and pilot radius (m); an eye's radius (m) and optical
# axis (in the same joint frame, along the frame's normal); a 'none' socket takes no part and carries none. So G3's
# "fit from socket data" has its data: a part's base is sized and clocked by its socket, never by a bounding box
SLOT_KEYS = ('kind', 'side', 'interface', 'joint', 'frame', 'dims')
FRAME_KEYS = ('normal', 'tangent')
DIMS_KEYS = dict(mount=('radius', 'bolt_circle', 'bolts', 'pilot'), ball=('radius', 'axis'), dome=('radius', 'axis'),
                 none=())
assert set(DIMS_KEYS) == set(INTERFACES) - {'chain', 'region'}, 'every socket interface has its dims vocabulary'
# the kit's flange PATTERN on a socket's radius, "the pattern, not the sizes" (A.7 U1): TC70, its most used interface
# (r 35, bolt circle r 27.5, 6 bolts, pilot r 12 mm; 204 of its 239 records carry them). KS 1.5's "6 screws at 60 deg on
# PCD 0.76-0.81 x OD" holds on it, and A.4.3 reads the same ratios on the plan's collar (PCD 0.764-0.787, pilot
# 0.219-0.344 of the OD)
KIT_FLANGE = dict(bolt_circle=27.5 / 35.0, pilot=12.0 / 35.0, bolts=6)
UNIT_TOL = 1e-3            # a frame's vectors are unit and perpendicular to this (t13 writes them to 1e-6)
AXIS_TOL_DEG = 1.0         # an eye's axis lies along its frame's normal within this
MAX_LENGTH = 1.0           # metres: a socket dimension of a metre or more is millimetres written as metres


def _vec3(v):
    """v as three finite floats, or None (a string, a dict, a bool or a NaN is no vector)"""
    if isinstance(v, (str, bytes, dict)):
        return None
    try:
        xs = list(v)
    except TypeError:
        return None
    if len(xs) != 3 or any(isinstance(x, bool) or not isinstance(x, numbers.Real) for x in xs):
        return None
    xs = [float(x) for x in xs]
    return xs if all(math.isfinite(x) for x in xs) else None


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return [x / n for x in v]


def port_frame(normal, side='', joint=None):
    """a socket's FRAME from its outward normal (a direction in the creature's bind pose): the unit normal (the kit's Z)
    and the TANGENT (its X), the creature's lateral axis made perpendicular to the normal: +X (the creature's left) on a
    left or unsided socket, -X on a right one, so paired sockets are mirror images; -Z (backward) where the normal lies
    within 25.8 deg of the lateral axis (|n.x| > 0.9). That is the kit's own default tangent (frameMatrix, RI:55-71),
    mirrored on the right; on the midline it is +X, the axis t13's glasses socket and hat seat already carry. joint: the
    socket's joint's bind-pose rotation (3 x 3, its columns the joint's axes in the creature's frame), and the frame is
    returned in that joint's frame (A.6), rounded to 1e-6"""
    n = _vec3(normal)
    if n is None or _dot(n, n) < 1e-20:
        raise ValueError(f'port_frame: the normal {normal!r} is not a nonzero finite 3-vector')
    n = _unit(n)
    ref = [0.0, 0.0, -1.0] if abs(n[0]) > 0.9 else ([-1.0, 0.0, 0.0] if side == 'R' else [1.0, 0.0, 0.0])
    d = _dot(ref, n)
    t = _unit([ref[k] - d * n[k] for k in range(3)])
    if joint is not None:
        R = [[float(joint[i][k]) for k in range(3)] for i in range(3)]
        n = [sum(R[i][k] * n[i] for i in range(3)) for k in range(3)]          # R^T n: in the joint's frame
        t = [sum(R[i][k] * t[i] for i in range(3)) for k in range(3)]
    return dict(normal=[round(x, 6) + 0.0 for x in n], tangent=[round(x, 6) + 0.0 for x in t])


def mount_dims(radius):
    """a MOUNT socket's dims: its radius (m) and the kit's flange pattern on it (KIT_FLANGE)"""
    r = float(radius)
    return dict(radius=round(r, 6), bolt_circle=round(r * KIT_FLANGE['bolt_circle'], 6), bolts=int(KIT_FLANGE['bolts']),
                pilot=round(r * KIT_FLANGE['pilot'], 6))


def eye_dims(radius, axis):
    """an EYE socket's dims ('ball' or 'dome'): the eye's radius (m) and its optical axis (unit, in the frame's joint
    frame: the frame's normal)"""
    a = _vec3(axis)
    if a is None or _dot(a, a) < 1e-20:
        raise ValueError(f'eye_dims: the axis {axis!r} is not a nonzero finite 3-vector')
    return dict(radius=round(float(radius), 6), axis=[round(x, 6) + 0.0 for x in _unit(a)])


def frame_problems(frame):
    """what makes a socket's frame unusable, as the kit refuses one (a missing or non-finite vector, a zero normal, a
    tangent parallel to it), or ambiguous (vectors not unit, a tangent not perpendicular, an unknown key): [] = sound"""
    if not isinstance(frame, dict):
        return [f'the frame must be {{normal, tangent}}, not {frame!r}'[:160]]
    bad = [f'unknown frame key {k!r} (have: {", ".join(FRAME_KEYS)})' for k in frame if k not in FRAME_KEYS]
    vs = {}
    for k in FRAME_KEYS:
        v = _vec3(frame.get(k))
        if v is None:
            bad.append(f'its {k} {frame.get(k)!r} is not three finite numbers'[:160])
            continue
        n = math.sqrt(_dot(v, v))
        if n < 1e-10:
            bad.append(f'its {k} is zero: a degenerate frame')
        elif abs(n - 1.0) > UNIT_TOL:
            bad.append(f'its {k} is not a unit vector (length {n:.6f})')
        else:
            vs[k] = v
    if len(vs) == 2:
        c = _dot(vs['normal'], vs['tangent'])
        if abs(c) > 1.0 - UNIT_TOL:
            bad.append(f'its tangent is parallel to its normal (n.t {c:+.5f}): a degenerate frame (no clocking about '
                       'the normal)')
        elif abs(c) > UNIT_TOL:
            bad.append(f'its tangent is not perpendicular to its normal (n.t {c:+.5f})')
    return bad


def dims_problems(interface, dims, frame=None):
    """what is wrong with a socket's dims for its interface (DIMS_KEYS): a mount or an eye without them, a key the
    interface does not take or lacks, a length that is not a positive finite number of metres under MAX_LENGTH, a bolt
    circle outside the radius or a pilot outside the bolt circle, fewer than 3 bolts, an eye's axis not along its frame's
    normal (when the frame is sound). [] = right"""
    keys = DIMS_KEYS.get(interface)
    if keys is None:
        return [f'no dims vocabulary for the interface {interface!r}']
    if not keys:
        return [] if dims in (None, {}) else [f'a {interface!r} socket takes no part and carries no dims, not '
                                               f'{dims!r}'[:160]]
    if dims is None:
        return [f'a {interface!r} socket carries no dims ({", ".join(keys)}): a part on it is sized by nothing (G3)']
    if not isinstance(dims, dict):
        return [f'its dims must be a dict of {", ".join(keys)}, not {dims!r}'[:160]]
    bad = [f'unknown dims key {k!r} for a {interface!r} socket (have: {", ".join(keys)})' for k in dims
           if k not in keys]
    bad += [f'its dims lack {k!r}' for k in keys if k not in dims]

    def length(k):
        v = dims.get(k)
        if isinstance(v, bool) or not isinstance(v, numbers.Real) or not math.isfinite(v) or v <= 0.0:
            bad.append(f'its {k} {v!r} is not a positive length (m)'[:160])
            return None
        if v >= MAX_LENGTH:
            bad.append(f'its {k} {v!r} m is {MAX_LENGTH:g} m or more (millimetres written as metres?)')
            return None
        return float(v)

    r = length('radius') if 'radius' in dims else None
    if interface == 'mount':
        bc = length('bolt_circle') if 'bolt_circle' in dims else None
        pl = length('pilot') if 'pilot' in dims else None
        nb = dims.get('bolts')
        if 'bolts' in dims and (isinstance(nb, bool) or not isinstance(nb, numbers.Integral) or nb < 3):
            bad.append(f'its bolts {nb!r} must be a whole count of 3 or more (the kit\'s flanges carry 6)')
        if r is not None and bc is not None and bc >= r:
            bad.append(f'its bolt circle (r {bc:.4f}) does not lie inside its radius ({r:.4f})')
        if bc is not None and pl is not None and pl >= bc:
            bad.append(f'its pilot (r {pl:.4f}) does not lie inside its bolt circle ({bc:.4f})')
    elif 'axis' in dims:
        a = _vec3(dims['axis'])
        if a is None or abs(math.sqrt(_dot(a, a)) - 1.0) > UNIT_TOL:
            bad.append(f'its axis {dims["axis"]!r} is not a unit 3-vector'[:160])
        elif isinstance(frame, dict) and not frame_problems(frame):
            ang = math.degrees(math.acos(max(-1.0, min(1.0, _dot(a, _unit(_vec3(frame['normal'])))))))
            if ang > AXIS_TOL_DEG:
                bad.append(f'its axis is {ang:.2f} deg off its frame\'s normal (an eye looks along its socket\'s normal)')
    return bad


# ============================================================================================ what generators write
def slot_extras(kind, side, interface, joint, *, frame, dims=None):
    """the extras.slot a generator writes on a socket node, checked against the vocabulary: it raises on a kind or an
    interface the table does not know, a degenerate frame, or dims its interface does not take (a mount or an eye
    without them), so a typo in a generator fails at export, not at seat time. frame: {normal, tangent} in the joint's
    frame (port_frame()); dims: mount_dims() or eye_dims(), None for a 'none' socket"""
    if kind not in SOCKET_KINDS:
        raise ValueError(f'slot_extras: {kind!r} is not a socket kind (have: {", ".join(SOCKET_KINDS)})')
    if interface not in SOCKET_KINDS[kind][0]:
        raise ValueError(f'slot_extras: a {kind!r} socket declares {SOCKET_KINDS[kind][0]}, not {interface!r}')
    if side not in SIDES:
        raise ValueError(f'slot_extras: side {side!r} not in {SIDES}')
    bad = frame_problems(frame) + dims_problems(interface, dims, frame)
    if bad:
        raise ValueError(f'slot_extras: the {kind!r} socket on {joint}: ' + '; '.join(bad))
    out = dict(kind=kind, side=side, interface=interface, joint=str(joint),
               frame={k: [float(x) for x in frame[k]] for k in FRAME_KEYS})
    if DIMS_KEYS[interface]:
        out['dims'] = {k: ([float(x) for x in v] if k == 'axis' else (int(v) if k == 'bolts' else float(v)))
                       for k, v in dims.items()}
    return out


def chain_record(name, kind, joints, s, radius, cuts, tip=None, side='', label=None):
    """a chain record for the scene extras' bestiary.chains (CYBORG_PLAN §4.4.1): the joints from the root to the tip,
    each joint's anatomical share s and radius (m), the LISTED cuts [{joint: k, s: the share where the weight ramp gives
    joint k - 1 the whole weight}] (a cut not listed is cyborg.cut: no ring, no pinning), the tip socket, the side and
    the anatomical label (the octopus's R1..L1)"""
    if kind not in CHAIN_KINDS:
        raise ValueError(f'chain_record: {kind!r} is not a chain kind (have: {", ".join(CHAIN_KINDS)})')
    joints = [str(j) for j in joints]
    if len(s) != len(joints) or len(radius) != len(joints):
        raise ValueError(f'chain_record {name}: {len(joints)} joints, {len(s)} s, {len(radius)} radii')
    s = [float(x) for x in s]
    if not all(_share_ok(x) for x in s) or any(s[i] > s[i + 1] for i in range(len(s) - 1)):
        raise ValueError(f'chain_record {name}: the shares s are not numbers 0..1 rising from the root to the tip')
    out_cuts = []
    for c in cuts:
        k = int(c['joint'])
        if not 1 <= k < len(joints):
            raise ValueError(f'chain_record {name}: cut joint {k} outside 1..{len(joints) - 1}')
        if 's' in c and not (_share_ok(c['s']) and s[k - 1] <= c['s'] <= s[k]):
            raise ValueError(f'chain_record {name}: cut {k}\'s share {c["s"]!r} is not between joints {k - 1} and {k} '
                             f'({s[k - 1]:.4f}-{s[k]:.4f})')
        out_cuts.append(dict(c, joint=k))
    if side not in SIDES:
        raise ValueError(f'chain_record {name}: side {side!r}')
    rec = dict(name=str(name), kind=kind, joints=joints, s=[round(float(x), 6) for x in s],
               radius=[round(float(x), 6) for x in radius], cuts=out_cuts, side=side)
    if tip:
        rec['tip'] = str(tip)
    if label:
        rec['label'] = str(label)
    return rec


def _share_ok(x):
    """a share along a chain: a finite number in 0..1 (a bool is no number)"""
    return not isinstance(x, bool) and isinstance(x, numbers.Real) and math.isfinite(x) and 0.0 <= x <= 1.0


# ============================================================================================ the recipe's rows
def _level_ok(lv):
    return isinstance(lv, (list, tuple)) and len(lv) == 2 and all(isinstance(x, int) and not isinstance(x, bool)
                                                                  for x in lv) and lv[0] <= lv[1]


def _in_band(row, level):
    lv = row.get('level')
    return lv is None or (_level_ok(lv) and lv[0] <= level <= lv[1])


def _real(v):
    return not isinstance(v, bool) and isinstance(v, numbers.Real) and math.isfinite(v)


def _pair(v, lo, hi, ints=False):
    """v as [a, b] with lo <= a <= b <= hi (ints when asked), or None"""
    if isinstance(v, (str, bytes, dict)) or not isinstance(v, (list, tuple)) or len(v) != 2:
        return None
    if not all(_real(x) and (not ints or isinstance(x, numbers.Integral)) for x in v):
        return None
    return (v[0], v[1]) if lo <= v[0] <= v[1] <= hi else None


def _hex_colour(v):
    return isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', v) is not None


def surface_regions(row, base):
    """the plate regions a surface row covers on a base: its region, or every UNIQUE region when it names none"""
    regs = PLATE_REGIONS.get(base) or {}
    r = row.get('region')
    if r is None:
        return [k for k, d in regs.items() if not d['stacked']]
    return [r] if r in regs else []


def check_surface(rows, base=None):
    """the cyborg section's SURFACE rows (C1): every key known (G2; the old absolute widths retired), every value in its
    range; with the base: its region one of the base's PLATE_REGIONS (cyborg.surface), the row's chart that region's,
    arms='all' on a STACKED region (cyborg.stacked: plates there print on every arm), arms only on an arm chart, and the
    s range inside the region's texels (s_max: past it the strip leaves them, onto the stacked arms set on the crown
    top). forge/cyborg.py's panel_layout runs this first and refuses on any error"""
    out = []
    if rows is None:
        return out
    if not (isinstance(rows, list) and all(isinstance(x, dict) for x in rows)):
        return [_P('error', 'cyborg.schema', 'cyborg.surface', 'surface is a list of plate-region rows (C1)')]
    regs = PLATE_REGIONS.get(base) if base is not None else None
    covered = {}                       # (region, arm index or None) -> the first row laying plates there
    feeds = []                         # (row index, the feed row's region) for the landing check after the loop
    for i, row in enumerate(rows):
        where = f'cyborg.surface[{i}]'

        def bad(code, msg):
            out.append(_P('error', code, where, msg[:300]))
        kind = row.get('kind', 'plates')
        if not isinstance(kind, str) or kind not in SURFACE_KINDS:
            bad('cyborg.unknown', f'kind {kind!r} not in {SURFACE_KINDS}')
            continue
        if kind == 'feed':
            feeds.append((i, _check_feed_row(row, base, bad)))
            continue
        for k in row:
            if k not in SURFACE_KEYS:
                why = _RETIRED_SURFACE.get(k)
                bad('cyborg.unknown', f'unknown surface key {k!r}' + (f': {why}' if why else
                                                                      f' (have: {", ".join(SURFACE_KEYS)})'))
        for k, opts in SURFACE_CHOICES.items():
            if row.get(k) is not None and (not isinstance(row[k], str) or row[k] not in opts):
                bad('cyborg.unknown', f'{k} {row[k]!r} not in {opts}')
        checks = (('theta_deg', lambda v: _real(v) and 0.0 < v <= 180.0, 'a half-angle in (0, 180] deg'),
                  ('plate_R', lambda v: _pair(v, 0.2, 4.5) is not None, '[lo, hi] local radii, 0.2-4.5 (study G\'s '
                                                                         'machines 0.55-2.23, its Guardian 4.27)'),
                  ('rows', lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1, 'an int >= 1'),
                  ('seam_tx', lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 3,
                   'an int >= 3 (texels: a baked groove needs 3 to read as depth, A.2.3)'),
                  ('seam_depth', lambda v: _real(v) and 0.25 <= v <= 1.0, 'the depth over the width, 0.25-1.0 (study G '
                                                                          '0.35-0.90, A.8\'s 0.5)'),
                  ('heads', lambda v: _pair(v, 1, 8, ints=True) is not None, '[lo, hi] heads per plate, ints 1-8'),
                  ('inset_D', lambda v: _real(v) and 0.2 <= v <= 5.0, 'head diameters from an edge, 0.2-5'),
                  ('fastener_tx', lambda v: _real(v) and 6.0 <= v <= 20.0, 'texels, 6-20 (study T\'s heads 6.6-15.5)'),
                  ('plate_t_mm', lambda v: _real(v) and 0.3 <= v <= 2.0, 'mm, 0.3-2.0 (the implant tier\'s relief)'),
                  ('accent_share', lambda v: _real(v) and 0.0 <= v <= 1.0, 'a share 0-1'),
                  ('glow_seams', lambda v: isinstance(v, bool), 'True or False'),
                  ('seed', lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0, 'an int >= 0'),
                  ('note', lambda v: isinstance(v, str), 'text'),
                  ('paint', _hex_colour, '#rrggbb'), ('accent', _hex_colour, '#rrggbb'))
        for k, ok, what in checks:
            if row.get(k) is not None and not ok(row[k]):
                bad('cyborg.schema', f'{k} {row[k]!r}: {what}')
        pd = row.get('pitch_D')
        if pd is not None and not ((_real(pd) and 1.5 <= pd <= 8.0) or _pair(pd, 1.5, 8.0) is not None):
            bad('cyborg.schema', f'pitch_D {pd!r}: head diameters, [lo, hi] for ends groups or one number, 1.5-8')
        if row.get('seams') in SEAM_TX and isinstance(row.get('seam_tx'), int) and \
                row['seam_tx'] != SEAM_TX[row['seams']]:
            bad('cyborg.schema', f'seams {row["seams"]!r} is {SEAM_TX[row["seams"]]} texels, and seam_tx says '
                                 f'{row["seam_tx"]}')
        s = row.get('s')
        sp = _pair(s, 0.0, 1.0) if s is not None else None
        if s is not None and (sp is None or sp[0] == sp[1]):
            bad('cyborg.schema', f's {s!r}: a share range [lo, hi], 0 <= lo < hi <= 1')
            sp = None
        reg = row.get('region')
        if reg is not None and not isinstance(reg, str):
            bad('cyborg.schema', f'region {reg!r}: one of the base\'s plate regions, by name')
            continue
        arms = row.get('arms')
        if arms is not None and arms != 'all' and not (isinstance(arms, list) and arms and
                                                       all(isinstance(a, str) for a in arms)):
            bad('cyborg.schema', f'arms {arms!r}: \'all\' or a list of chain labels / names')
        if base is None:
            continue
        if regs is None:
            bad('cyborg.surface', f'the {base} has no plate regions yet (its charts come at C11 / C12)')
            continue
        if reg is not None and reg not in regs:
            bad('cyborg.surface', f'no plate region {reg!r} on the {base} (have: {", ".join(regs)})')
            continue
        # the arms a row names: each a chain name arm<j> or its anatomical label, known on this base, none twice (G2)
        labs = PLATE_ARMS.get(base, ())
        arm_of = dict({f'arm{j}': j for j in range(len(labs))}, **{lab: j for j, lab in enumerate(labs)})
        named = None
        if isinstance(arms, list) and arms and all(isinstance(a, str) for a in arms):
            unknown = [a for a in arms if a not in arm_of]
            if unknown:
                bad('cyborg.unknown', f'arms {unknown}: no such arm on the {base} (have: {", ".join(labs)}, or '
                                      f'arm0-arm{len(labs) - 1})')
            named = [arm_of[a] for a in arms if a in arm_of]
            if len(set(named)) < len(named):
                bad('cyborg.schema', f'arms {arms!r} names one arm twice')
        for rn in ([reg] if reg is not None else surface_regions(row, base)):
            R = regs[rn]
            if row.get('chart') is not None and row['chart'] != R['chart']:
                bad('cyborg.surface', f'region {rn!r} lays out on chart {R["chart"]!r}, not {row["chart"]!r}')
            if R['stacked'] and arms != 'all':
                bad('cyborg.stacked', f'{rn!r} is a STACKED set ({R["set"]}: every arm on one arm\'s texels): plates '
                                      'there print on all of them; say arms=\'all\', or keep to a unique region')
            if R['chart'] != 'arm' and arms is not None:
                bad('cyborg.surface', f'arms {arms!r} on {rn!r}, which is no arm chart')
            if R.get('rows') == JOINT_ROWS and row.get('rows') is not None:
                bad('cyborg.surface', f'rows {row["rows"]!r} on {rn!r}: its rows follow the joints (one row per joint '
                                      'segment, the region\'s rule), never a count')
            if sp is not None and sp[1] > R['s_max'] + 1e-9:
                bad('cyborg.stacked' if (rn == 'crown_top') else 'cyborg.surface',
                    f's {list(s)} runs past {rn!r}\'s own texels at s {R["s_max"]}' +
                    (' (beyond it the strip is the stacked arms set)' if rn == 'crown_top' else ''))
            # ONE layout per region (and per arm on an arm chart): two rows on the same texels would lay two plate sets
            # over each other (the C1 check: two mantle rows, or a whole-creature row beside a region row, passed)
            keys = ([(rn, j) for j in (named if named is not None else range(len(labs)))] if R['chart'] == 'arm' else
                    [(rn, None)])
            twice = sorted({covered[k] for k in keys if k in covered})
            if twice:
                bad('cyborg.surface', f'{rn!r} is already plated by surface row(s) {twice}: one plate layout per region'
                                      + (' and arm' if R['chart'] == 'arm' else ''))
            for k in keys:
                covered.setdefault(k, i)
    # THE FEED ROWS' LANDING (A.9 decision 6, the contact gate): a feed line's two ends land on a plate or a mount, never
    # free, so its region must be plated by a plates row of this section (the octopus takes no mount: its ends are its
    # plates and its own grommets); one feed row per region
    seen = {}
    for i, rn in feeds:
        if base is None or rn is None:
            continue
        where = f'cyborg.surface[{i}]'
        if (rn, None) not in covered:
            out.append(_P('error', 'cyborg.feed', where, f'feed lines on {rn!r} have nowhere to land: no plates row of '
                                                          'this section plates it (a feed line\'s two ends land on a plate '
                                                          'or a mount, never free: A.9)'))
        if rn in seen:
            out.append(_P('error', 'cyborg.feed', where, f'{rn!r} already carries the feed lines of surface row '
                                                          f'{seen[rn]}: one feed row per region'))
        seen.setdefault(rn, i)
    return out


def _check_feed_row(row, base, bad):
    """one FEED row's keys and values (check_surface, kind 'feed'): every key known (G2), links and dives 0-FEED_MAX
    with at least one line, the sleeve one of FEED_CHOICES, the region one of the base's FEED_REGIONS. Returns the
    region the row lays its lines on (None when it cannot say)"""
    for k in row:
        if k not in FEED_KEYS:
            bad('cyborg.unknown', f'unknown feed key {k!r} (have: {", ".join(FEED_KEYS)})')
    n_ok = lambda v: isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= FEED_MAX
    for k in ('links', 'dives'):
        if row.get(k) is not None and not n_ok(row[k]):
            bad('cyborg.schema', f'{k} {row[k]!r}: an int 0-{FEED_MAX}')
    nl = row.get('links', FEED_DEFAULTS['links'])
    nd = row.get('dives', FEED_DEFAULTS['dives'])
    if n_ok(nl) and n_ok(nd) and nl + nd < 1:
        bad('cyborg.schema', 'a feed row lays at least one line (links + dives >= 1)')
    for k, opts in FEED_CHOICES.items():
        if row.get(k) is not None and (not isinstance(row[k], str) or row[k] not in opts):
            bad('cyborg.unknown', f'{k} {row[k]!r} not in {opts}')
    if row.get('seed') is not None and not (isinstance(row['seed'], int) and not isinstance(row['seed'], bool) and
                                            row['seed'] >= 0):
        bad('cyborg.schema', f'seed {row["seed"]!r}: an int >= 0')
    if row.get('note') is not None and not isinstance(row['note'], str):
        bad('cyborg.schema', f'note {row["note"]!r}: text')
    rn = row.get('region')
    if rn is not None and not isinstance(rn, str):
        bad('cyborg.schema', f'region {rn!r}: one of the base\'s feed regions, by name')
        return None
    if base is None:
        return rn
    allowed = FEED_REGIONS.get(base, ())
    rn = rn if rn is not None else (allowed[0] if allowed else None)
    if rn not in allowed:
        bad('cyborg.feed', f'feed lines on the {base} run on {list(allowed) or "no region yet"} (C3b: the mantle; an '
                           f'arm strip\'s cables are the mech arm\'s hose, C5), not {rn!r}')
        return None
    return rn


def check_recipe(cyb, base=None):
    """the cyborg section alone, no manifest (amendment 1: EVERY kind-keyed row is tested against its part's fits at
    validate time, not only a row that names a site): unknown keys, kinds, families, variants (cyborg.unknown); a row
    whose part does not fit its table's kind (cyborg.kind); a part on a kind of the wrong class (cyborg.interface: a
    chain part named in a kind table, a mount in a chain's); Skye's rule (cyborg.never); malformed bands, sides, cuts;
    the surface rows (check_surface, by the base when given: C1)"""
    out = []
    if cyb is None:
        return out
    if not isinstance(cyb, dict):
        return [_P('error', 'cyborg.schema', 'cyborg', f'the cyborg section is a dict (CYBORG_PLAN sec. 6.1), not '
                                                       f'{type(cyb).__name__}')]
    for k in cyb:
        if k not in CYBORG_KEYS:
            out.append(_P('error', 'cyborg.unknown', f'cyborg.{k}', f'unknown cyborg key {k!r} (have: '
                                                                    f'{", ".join(CYBORG_KEYS)}): never skipped (G2)'))
    for k in ('level', 'seed'):
        v = cyb.get(k)
        if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
            out.append(_P('error', 'cyborg.schema', f'cyborg.{k}', f'{k} must be an int >= 0: {v!r}'))
    parts = cyb.get('parts') or {}
    if not isinstance(parts, dict):
        out.append(_P('error', 'cyborg.schema', 'cyborg.parts', 'parts is {kind: [rows]}, keyed by KIND'))
        parts = {}
    for K, rows in parts.items():
        if K not in KINDS:
            out.append(_P('error', 'cyborg.unknown', f'cyborg.parts.{K}',
                          f'unknown kind {K!r}: kinds are slots.KINDS, never a socket name (no fallback)'))
            continue
        if not isinstance(rows, list):
            out.append(_P('error', 'cyborg.schema', f'cyborg.parts.{K}', 'a kind table is a list of rows'))
            continue
        for i, row in enumerate(rows):
            where = f'cyborg.parts.{K}[{i}]'
            if not isinstance(row, dict):
                out.append(_P('error', 'cyborg.schema', where, f'a row is a dict, not {row!r}'))
                continue
            for rk in row:
                if rk not in ROW_KEYS:
                    out.append(_P('error', 'cyborg.unknown', where, f'unknown row key {rk!r} (have: '
                                                                    f'{", ".join(ROW_KEYS)})'))
            # every row's band, weight, side and site, whatever its part (a malformed row is reported in full)
            if 'level' in row and not _level_ok(row['level']):
                out.append(_P('error', 'cyborg.level', where, f'level band {row["level"]!r} must be [lo, hi] ints'))
            w = row.get('weight', 1.0)
            if not (isinstance(w, (int, float)) and not isinstance(w, bool) and math.isfinite(w) and w > 0):
                out.append(_P('error', 'cyborg.schema', where, f'weight {w!r} must be a finite number > 0 (an infinite '
                                                               'weight breaks the seeded pick)'))
            if row.get('side') not in (None,) + SIDES:
                out.append(_P('error', 'cyborg.side', where, f'side {row.get("side")!r} not in {SIDES}'))
            if row.get('site') is not None and not isinstance(row['site'], str):
                out.append(_P('error', 'cyborg.schema', where, f'site {row["site"]!r} must be a socket name'))
            F = row.get('part')
            kc = KINDS[K]['cls']
            if F == NONE:
                # the explicit no-part row: the band may pick nothing (no variant, nothing seated, no table to fit)
                if row.get('variant') is not None:
                    out.append(_P('error', 'cyborg.unknown', where, f'the {NONE!r} row places nothing and takes no '
                                                                    f'variant ({row["variant"]!r})'))
                if kc == 'chain':
                    out.append(_P('error', 'cyborg.interface', where,
                                  f'{K!r} is a chain kind: its table takes no rows, not even {NONE!r} (a limb is '
                                  'replaced through cyborg.limbs)'))
                continue
            if not isinstance(F, str) or F not in FAMILIES:          # a list or a dict is refused, never a crash
                out.append(_P('error', 'cyborg.unknown', where, f'unknown cyborg family {F!r} (have: '
                                                                f'{", ".join(FAMILIES)}, or {NONE!r} for no part): no '
                                                                'fallback family (G2)'))
                continue
            d = FAMILIES[F]
            v = row.get('variant')
            if v is not None and v not in d['variants']:
                out.append(_P('error', 'cyborg.unknown', where, f'{F} has no variant {v!r} (have: '
                                                                f'{", ".join(d["variants"])}): no stand-in (G2)'))
            if 'chain' in d['interfaces']:
                out.append(_P('error', 'cyborg.interface', where,
                              f'{F} is a CHAIN part: it replaces a chain from a listed cut (cyborg.limbs), never a '
                              f'{kc} kind\'s table ({K!r})'))
            elif kc == 'chain':
                out.append(_P('error', 'cyborg.interface', where,
                              f'{K!r} is a chain kind: its table takes no {F} ({"/".join(d["interfaces"])} part); '
                              'only a chain part replaces it, through cyborg.limbs'))
            elif (kc == 'region') != ('region' in d['interfaces']):
                out.append(_P('error', 'cyborg.interface', where,
                              f'{F} ({"/".join(d["interfaces"])}) cannot take the {kc} kind {K!r}'))
            if K not in d['fits']:
                out.append(_P('error', 'cyborg.kind', where,
                              f'{F} does not fit kind {K!r}: it fits {list(d["fits"])} only, so the {K!r} table cannot '
                              f'hold it (a part matches its body slot)'))
            why = never(F, K)
            if why:
                out.append(_P('error', 'cyborg.never', where, f'{F} on kind {K!r}: Skye\'s rule, {why}'))
    limbs = cyb.get('limbs') or []
    if not isinstance(limbs, list):
        out.append(_P('error', 'cyborg.schema', 'cyborg.limbs', 'limbs is a list of rows'))
        limbs = []
    for i, row in enumerate(limbs):
        where = f'cyborg.limbs[{i}]'
        if not isinstance(row, dict):
            out.append(_P('error', 'cyborg.schema', where, f'a limb row is a dict, not {row!r}'))
            continue
        for rk in row:
            if rk not in LIMB_KEYS:
                out.append(_P('error', 'cyborg.unknown', where, f'unknown limb key {rk!r} (have: '
                                                                f'{", ".join(LIMB_KEYS)})'))
        K, F = row.get('kind'), row.get('part')
        if not isinstance(K, str) or K not in KINDS:
            out.append(_P('error', 'cyborg.unknown', where, f'unknown kind {K!r}'))
            K = None                                      # unknown or unhashable: judged no further, never a crash
        elif KINDS[K]['cls'] != 'chain':
            out.append(_P('error', 'cyborg.interface', where, f'a limb replacement takes a CHAIN kind, and {K!r} is a '
                                                              f'{KINDS[K]["cls"]} kind'))
        if F == NONE:
            out.append(_P('error', 'cyborg.interface', where, f'a limb row replaces its chain, so it takes a chain part: '
                                                              f'{NONE!r} is a kind table\'s row (a limb row out of its '
                                                              'band replaces nothing)'))
        elif not isinstance(F, str) or F not in FAMILIES:
            out.append(_P('error', 'cyborg.unknown', where, f'unknown cyborg family {F!r}'))
        else:
            d = FAMILIES[F]
            if d.get('organ'):
                out.append(_P('error', 'cyborg.organ', where, f'{F} is an ORGAN family: a graft (the recipe\'s graft '
                                                              'parts, forged for its socket), never a cyborg limb'))
            if 'chain' not in d['interfaces']:
                out.append(_P('error', 'cyborg.interface', where, f'{F} is a {"/".join(d["interfaces"])} part, not a '
                                                                  'chain replacement'))
            if K in KINDS and K not in d['fits']:
                out.append(_P('error', 'cyborg.kind', where, f'{F} does not fit kind {K!r}: it fits {list(d["fits"])}'
                                                             ' only'))
            if K in KINDS:
                why = never(F, K)
                if why:
                    out.append(_P('error', 'cyborg.never', where, f'{F} on kind {K!r}: Skye\'s rule, {why}'))
            v = row.get('variant')
            if v is not None and v not in d['variants']:
                out.append(_P('error', 'cyborg.unknown', where, f'{F} has no variant {v!r}'))
        if not isinstance(row.get('chain'), str):
            out.append(_P('error', 'cyborg.unknown', where, f'chain {row.get("chain")!r}: a chain record\'s name or '
                                                            'anatomical label'))
        cj = row.get('cut_joint')
        if not (isinstance(cj, int) and not isinstance(cj, bool)):
            out.append(_P('error', 'cyborg.cut', where, f'cut_joint {cj!r} must be one of the chain\'s listed cuts'))
        hz = row.get('hose')
        if hz is not None and hz not in HOSE_FROM:
            out.append(_P('error', 'cyborg.unknown', where, f'hose {hz!r} not in {HOSE_FROM} (or None: no hose)'))
        elif hz == 'plates' and not any(isinstance(s, dict) and s.get('kind', 'plates') == 'plates'
                                        for s in (cyb.get('surface') if isinstance(cyb.get('surface'), list) else [])):
            out.append(_P('error', 'cyborg.feed', where, 'a hose from the plates needs a plates row in cyborg.surface: '
                                                         'alone it has nowhere to land (never a free end, A.9)'))
        if 'level' in row and not _level_ok(row['level']):
            out.append(_P('error', 'cyborg.level', where, f'level band {row["level"]!r} must be [lo, hi] ints'))
    out += check_surface(cyb.get('surface'), base)
    glow = cyb.get('glow')
    if glow is not None and not isinstance(glow, dict):
        out.append(_P('error', 'cyborg.schema', 'cyborg.glow', 'glow is a dict (C8)'))
    aff = cyb.get('affixes')
    if aff is not None:
        if not isinstance(aff, list):
            out.append(_P('error', 'cyborg.schema', 'cyborg.affixes', 'affixes is a list'))
        else:
            for a in aff:
                if a not in AFFIXES:
                    out.append(_P('error', 'cyborg.unknown', f'cyborg.affixes.{a}',
                                  f'unknown cyborg affix {a!r} (have: {", ".join(AFFIXES)})'))
    return out


# ============================================================================================ the manifest's typing
def check_manifest(man, base, base_data=None):
    """amendment 2 on a manifest's typing: every socket typed or none; each slot's kind, interface and side from the
    vocabulary, its joint the node's own, its keys known, its FRAME sound and its interface's DIMS present and
    consistent (the lead's C0b call: a degenerate frame and a mount without dims are errors); the KIND ON ITS ANATOMY (the base's joints for that kind: a back slot on a
    neck bone, a back slot on the octopus are errors); each seat archetype only under sockets of its kinds; the chain
    records' kinds, joints (a parent chain on the base's joints), shares (rising 0..1; each cut's between its two
    joints': cyborg.covered reads them), cuts and tips; the region records. An untyped
    manifest (an old glb) passes here, and its cyborg parts fail cyborg.untyped; a cyborg seat under an untyped socket
    still errs"""
    out = []
    B = base_data if base_data is not None else BASES.get(base)
    socks = man.get('sockets') or {}
    bones = list(man.get('bones') or [])
    bone_set = set(bones)
    parent = man.get('bone_parent') or {}
    chains = man.get('chains') or {}
    regions = man.get('regions') or {}
    typed = sorted(s for s, d in socks.items() if d.get('slot') is not None)
    if not typed and not chains and not regions:
        for s, d in sorted(socks.items()):
            for arch in sorted(d.get('seats') or {}):
                if arch in CYBORG_SEATS:
                    out.append(_P('error', 'manifest.seat_kind', f'{s}.seat_{arch}',
                                  f'seat_{arch} under the untyped {s}: a cyborg seat hangs only under a typed socket of '
                                  f'kind {list(CYBORG_SEATS[arch])}'))
        return out
    if B is None:                # an error, not a note: unchecked kinds would seat parts by whatever the glb claims
        out.append(_P('error', 'manifest.slot_base', 'manifest',
                      f'no slot joint table for base {base!r} (slots.BASES): its kinds cannot be checked against its '
                      'anatomy, so no cyborg part seats on it until it has one'))
    for s, d in sorted(socks.items()):
        slot = d.get('slot')
        bone = d.get('bone')
        if slot is None:
            out.append(_P('error', 'manifest.slot_missing', s,
                          f'{s} carries no slot extras while {len(typed)} sockets do: a generator types every socket '
                          '(a half-typed glb seats cyborg parts by whatever happened to be typed)'))
            continue
        if not isinstance(slot, dict):
            out.append(_P('error', 'manifest.slot', s, f'{s}: extras.slot must be {{kind, side, interface, joint}}, '
                                                       f'not {slot!r}'))
            continue
        kind = slot.get('kind')
        if not isinstance(kind, str) or kind not in SOCKET_KINDS:     # a list in the glb's extras: refused, no crash
            what = f'a {KINDS[kind]["cls"]} kind' if isinstance(kind, str) and kind in KINDS else 'unknown'
            out.append(_P('error', 'manifest.slot', s, f'{s} is typed {kind!r} ({what}): a socket carries one of '
                                                       'slots.SOCKET_KINDS (G2: no unknown kind is guessed)'))
            continue
        side = slot.get('side', '')
        if side not in SIDES:
            out.append(_P('error', 'manifest.slot', s, f'{s}: side {side!r} not in {SIDES}'))
        iface = slot.get('interface')
        if iface not in SOCKET_KINDS[kind][0]:
            out.append(_P('error', 'manifest.slot_interface', s, f'{s} ({kind}) declares interface {iface!r}; a '
                                                                 f'{kind!r} socket declares {SOCKET_KINDS[kind][0]}'))
        elif B is not None and (B.get('interfaces') or {}).get(kind, iface) != iface:
            out.append(_P('error', 'manifest.slot_interface', s, f'{s} ({kind}) declares {iface!r}; the {base}\'s '
                                                                 f'{kind!r} is {B["interfaces"][kind]!r} (G8: the eye '
                                                                 'archetype is the base\'s)'))
        # the PORT (the lead's C0b call, A.6): every typed socket carries a sound frame, and its interface's dims
        extra = [k for k in slot if k not in SLOT_KEYS]
        if extra:
            out.append(_P('error', 'manifest.slot', s, f'{s}: unknown slot keys {extra} (have: {", ".join(SLOT_KEYS)}): '
                                                       'never skipped (G2)'))
        fr = slot.get('frame')
        fp = (['it carries no frame (a socket is a port: its outward normal and its tangent in its joint\'s frame, '
               'A.6)'] if fr is None else frame_problems(fr))
        if fp:
            out.append(_P('error', 'manifest.slot_frame', s, f'{s}: ' + '; '.join(fp)))
        if iface in SOCKET_KINDS[kind][0]:
            dp = dims_problems(iface, slot.get('dims'), None if fp else fr)
            if dp:
                out.append(_P('error', 'manifest.slot_dims', s, f'{s} ({kind}, {iface}): ' + '; '.join(dp)))
        if slot.get('joint') != bone:
            out.append(_P('error', 'manifest.slot_joint', s, f'{s}: slot.joint {slot.get("joint")!r} but the node '
                                                             f'hangs on {bone!r} (a slot copied onto another socket)'))
        if B is not None:
            rx = B['joints'].get(kind)
            if rx is None:
                why = (B.get('lacks') or {}).get(kind)
                out.append(_P('error', 'manifest.slot_joint', s,
                              f'{s} is typed {kind!r}, and the {base} has no {kind!r} slot' + (f': {why}' if why else
                                                                                              '')))
            elif not _match(rx, bone):
                out.append(_P('error', 'manifest.slot_joint', s,
                              f'{s} is typed {kind!r} but hangs on {bone!r}: the {base}\'s {kind!r} slot rides '
                              f'{rx} only' + (' (the old bug: a back slot on a neck bone)' if kind in ('back', 'chest')
                                              else '')))
            if kind == 'back' and _match(B['head_region'], bone):
                out.append(_P('error', 'manifest.slot_joint', s,
                              f'{s} is a back slot on {bone!r}, inside the {base}\'s head region: a mount there is '
                              'worn on the head (the sombrero)'))
        w = d.get('world')
        if w is not None and side == 'L' and w[0] < -1e-4:
            out.append(_P('error', 'manifest.slot_side', s, f'{s} is typed side L at x {w[0]:+.4f}: the creature\'s '
                                                            'LEFT is +X'))
        if w is not None and side == 'R' and w[0] > 1e-4:
            out.append(_P('error', 'manifest.slot_side', s, f'{s} is typed side R at x {w[0]:+.4f}: the RIGHT is -X'))
        for arch in sorted(d.get('seats') or {}):
            ks = SEAT_KINDS.get(arch)
            if ks is None:
                out.append(_P('warning', 'manifest.seat_unknown', f'{s}.seat_{arch}',
                              f'seat_{arch}: an archetype slots.SEAT_KINDS does not list (its kinds go unchecked)'))
            elif kind not in ks:
                out.append(_P('error', 'manifest.seat_kind', f'{s}.seat_{arch}',
                              f'seat_{arch} under {s} (kind {kind!r}): seat_{arch} hangs only under {list(ks)} '
                              'sockets'))
    for name, c in sorted(chains.items()):
        where = f'chains.{name}'
        kind = c.get('kind')
        if not isinstance(kind, str) or kind not in CHAIN_KINDS:
            out.append(_P('error', 'manifest.chain', where, f'chain {name} is typed {kind!r}: a chain record carries '
                                                            'one of slots.CHAIN_KINDS'))
            continue
        js = list(c.get('joints') or [])
        gone = [j for j in js if not isinstance(j, str) or j not in bone_set]
        if not js or gone:
            out.append(_P('error', 'manifest.chain', where, f'chain {name}: joints missing from the skin: '
                                                            f'{gone[:4] or "(none listed)"}'))
            continue
        broken = [js[i] for i in range(1, len(js)) if parent.get(js[i]) != js[i - 1]]
        if broken:
            out.append(_P('error', 'manifest.chain', where, f'chain {name} is not a parent chain at {broken[:4]}'))
        if B is not None:
            rx = B['chains'].get(kind)
            if rx is None:
                out.append(_P('error', 'manifest.chain_joint', where, f'chain {name} is typed {kind!r}, and the {base} '
                                                                      f'has no {kind!r} chain'))
            else:
                off = [j for j in js if not _match(rx, j)]
                if off:
                    out.append(_P('error', 'manifest.chain_joint', where,
                                  f'chain {name} ({kind}) holds {off[:4]}: the {base}\'s {kind!r} chain rides {rx}'))
        for key in ('s', 'radius'):
            if key in c and len(c[key]) != len(js):
                out.append(_P('error', 'manifest.chain', where, f'chain {name}: {len(c[key])} {key} for '
                                                                f'{len(js)} joints'))
        # the shares cyborg.covered judges a layer's reach against (the C0b check: a cut's share written past its
        # joints cleared a growth it covers, and a share that is no number crashed the judgement): each joint's s a
        # number 0..1 rising from the root to the tip, each listed cut's s between its two joints' shares
        ss = c.get('s')
        if ss is not None and not (isinstance(ss, (list, tuple)) and len(ss) == len(js) and
                                   all(_share_ok(x) for x in ss) and all(ss[i] <= ss[i + 1] for i in range(len(ss) - 1))):
            out.append(_P('error', 'manifest.chain', where, f'chain {name}: its shares s {str(ss)[:80]} are not numbers '
                                                            '0..1 rising from the root to the tip'))
            ss = None
        for cut in c.get('cuts') or []:
            k = cut.get('joint') if isinstance(cut, dict) else None
            if not (isinstance(k, int) and 1 <= k < len(js)):
                out.append(_P('error', 'manifest.chain', where, f'chain {name}: listed cut {cut!r} is not a joint '
                                                                f'index 1..{len(js) - 1}'))
            elif 's' in cut and not (_share_ok(cut['s']) and (ss is None or ss[k - 1] <= cut['s'] <= ss[k])):
                out.append(_P('error', 'manifest.chain', where,
                              f'chain {name}: cut {k}\'s share {cut["s"]!r} does not lie between joints {k - 1} and '
                              f'{k}' + (f' ({ss[k - 1]:.4f}-{ss[k]:.4f})' if ss is not None else '')))
        tip = c.get('tip')
        if tip is not None:
            td = socks.get(tip) if isinstance(tip, str) else None
            if td is None or td.get('bone') != js[-1]:
                out.append(_P('error', 'manifest.chain', where, f'chain {name}: tip {tip} is not a socket on its last '
                                                                f'joint {js[-1]}'))
            elif (td.get('slot') or {}).get('kind') not in (None, 'limb_tip', 'paw', 'foot', 'claw', 'tail_tip'):
                out.append(_P('error', 'manifest.chain', where, f'chain {name}: tip {tip} is typed '
                                                                f'{td["slot"]["kind"]!r}, not a distal kind'))
    # one limb, one record, one replacement (the C0 check: a second record over arm3's joints let two mech tentacles
    # replace one arm; two records sharing a label left the label naming neither)
    owners, labelled = {}, {}
    for name, c in sorted(chains.items()):
        for j in (c.get('joints') if isinstance(c.get('joints'), list) else []):
            if isinstance(j, str):
                owners.setdefault(j, []).append(name)
        if isinstance(c.get('label'), str):
            labelled.setdefault(c['label'], []).append(name)
    for names in sorted({tuple(v) for v in owners.values() if len(v) > 1}):
        js = sorted(j for j, v in owners.items() if tuple(v) == names)
        out.append(_P('error', 'manifest.chain', 'chains.' + '+'.join(names),
                      f'chain records {list(names)} share {len(js)} joints ({", ".join(js[:3])}...): a limb is ONE '
                      'chain record, replaced at most once'))
    for lab, names in sorted(labelled.items()):
        if len(names) > 1:
            out.append(_P('error', 'manifest.chain', f'chains.{lab}', f'label {lab!r} names {names}: an anatomical '
                                                                       'label names one chain'))
    for name, g in sorted(regions.items()):
        kind = g.get('kind')
        if not isinstance(kind, str) or kind not in REGION_KINDS:
            out.append(_P('error', 'manifest.region', f'regions.{name}', f'region {name} is typed {kind!r}'))
            continue
        raw = list(g.get('joints') or [])
        gone = [j for j in raw if not isinstance(j, str) or j not in bone_set]
        if not raw or gone:
            out.append(_P('error', 'manifest.region', f'regions.{name}', f'region {name}: ' + (
                f'joints missing {gone[:4]}' if gone else 'no joints (a region swap replaces joints it names)')))
        # amendment 2 for regions, as for sockets and chains (the C0 check: a head_region record over arm3_05..06
        # seated a machine head on an arm, "a robot head for a limb")
        if B is not None and kind == 'head_region':
            off = [j for j in raw if isinstance(j, str) and not _match(B['head_region'], j)]
            if off:
                out.append(_P('error', 'manifest.region_joint', f'regions.{name}',
                              f'region {name} ({kind}) holds {off[:4]}: the {base}\'s head region rides '
                              f'{B["head_region"]} only'))
    return out


# ============================================================================================ G5: the hat probe
def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _seg_dist(p, a, b):
    ab, ap = _sub(b, a), _sub(p, a)
    L2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
    t = 0.0 if L2 <= 0.0 else max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2))
    q = [a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2]]
    return math.dist(p, q)


def seat_world(sock, seat=None):
    """a seat's origin in the bind pose: the socket's world point plus its frame times the seat's local offset. None
    when it cannot be placed: no world point, or a seat offset with no frame to carry it. Never a stand-in point (the C0
    check: without its world point the socket was measured from the ORIGIN, and without its frame the seat's offset was
    dropped, so a folded arm cleared G5 that its real seat fails; the old kit fell back to the mount point alike)"""
    w = sock.get('world')
    if not w:
        return None
    w = list(w)
    loc = (seat or {}).get('local')
    F = sock.get('frame')
    if loc and any(float(x) != 0.0 for x in loc):
        if not F:
            return None
        return [w[i] + sum(F[i][k] * loc[k] for k in range(3)) for i in range(3)]
    return w


def head_clearance(man, base, site, seat=None, base_data=None):
    """the distance (m) from a seat's origin to the base's HEAD REGION: its head-region joints' bones as segments (a
    joint whose parent is also in the region joins it), and the nearest joint. (None, None, why) if it cannot be
    measured"""
    B = base_data if base_data is not None else BASES.get(base)
    if B is None:
        return None, None, f'no head region for base {base!r} (slots.BASES)'
    pos = man.get('bone_world')
    if not pos:
        return None, None, 'the manifest carries no joint positions (bone_world)'
    parent = man.get('bone_parent') or {}
    head = [b for b in (man.get('bones') or []) if _match(B['head_region'], b)]
    if not head:
        return None, None, f'no joint of the {base}\'s head region ({B["head_region"]}) in the manifest'
    unplaced = [b for b in head if b not in pos]
    if unplaced:                 # a region measured from part of its joints is not the region
        return None, None, f'the {base}\'s head-region joints {unplaced[:4]} carry no position (bone_world)'
    sock = (man.get('sockets') or {}).get(site) or {}
    p = seat_world(sock, seat)
    if p is None:
        return None, None, (f'{site} carries no world point' if not sock.get('world') else
                            f'{site} carries no frame for its seat\'s offset {list((seat or {}).get("local") or [])}')
    best, near = None, None
    for b in head:
        a = pos[parent[b]] if parent.get(b) in head else pos[b]
        dd = _seg_dist(p, a, pos[b])
        if best is None or dd < best:
            best, near = dd, b
    return best, near, ''


def head_probe(man, base, site, reach, seat=None, base_data=None):
    """G5 (the lead, 10-21): the base's HEAD REGION is its head-region joints' bones as capsules of radius
    head_margin; a back mount's site must not ride one of those joints, and its WHOLE reach envelope (a sphere of radius
    reach about its seat: every pose its joints can take, not only the rest pose) must stay outside the region.
    Returns [(message, numbers)]: empty = clear"""
    B = base_data if base_data is not None else BASES.get(base)
    sock = (man.get('sockets') or {}).get(site) or {}
    if B is None:
        return [(f'no head region for base {base!r} (slots.BASES): G5 cannot clear the mount', {})]
    rx, margin = B['head_region'], float(B['head_margin'])
    out = []
    if _match(rx, sock.get('bone')):
        out.append((f'{site} rides {sock.get("bone")}, a joint of the {base}\'s head region: a mount there stands on '
                    'the head (the sombrero)', dict(joint=sock.get('bone'))))
    best, near, why = head_clearance(man, base, site, seat=seat, base_data=B)
    if best is None:
        out.append((f'{why}: G5 cannot clear the reach envelope', {}))
        return out
    clear = best - margin - float(reach)
    if clear < 0.0:
        out.append((f'its whole reach envelope (r {float(reach):.3f} m about {site}) comes within {best:.3f} m of '
                    f'{near}, inside the head region\'s {margin:.3f} m: it can stand over the head whatever its rest '
                    'pose', dict(reach=float(reach), dist=round(best, 4), margin=margin, near=near,
                                 clear=round(clear, 4))))
    return out


# ============================================================================================ seat groups
def group_kinds(kinds, base, base_data=None):
    """the kinds and every kind that shares a SEAT GROUP with one of them on the base (the octopus: head with mantle)"""
    B = base_data if base_data is not None else BASES.get(base)
    out = set(kinds)
    for grp in (B or {}).get('seat_groups') or ():
        if out & set(grp):
            out |= set(grp)
    return out


def seat_groups(man, base, base_data=None):
    """{socket: its seat group's sockets, sorted} for every typed socket of a kind in one of the base's seat groups:
    for seat_shared the group is ONE seat (the lead's C0b call: the octopus's head top and mantle apex)"""
    B = base_data if base_data is not None else BASES.get(base)
    socks = {s: d for s, d in (man.get('sockets') or {}).items() if isinstance(d.get('slot'), dict)}
    out = {}
    for grp in (B or {}).get('seat_groups') or ():
        members = tuple(sorted(s for s, d in socks.items() if d['slot'].get('kind') in grp))
        for s in members:
            out[s] = members
    return out


# ============================================================================================ cyborg.covered
def check_covered(placements, man, base, layers, base_data=None):
    """cyborg.covered (CYBORG_PLAN A.6; the lead's A.9 decision 4, an ERROR): a covering layer the recipe stands on
    flesh a part replaces, or on a socket a mount covers. Left there it floats, and floating is impossible by
    construction (study T hides EVERY layer over a prosthesis by the same region code). placements: plan()'s. layers:
    [(where, what, reach)] from the recipe (recipe._covering_layers), reach = dict(regions: the base regions its sites
    stand on, None for everywhere; s: its (lo, hi) share along a chain, or None with growth=True for the forge's own
    growth footprint, BASES growth_s; sockets: the sockets it seats on; bones: the joints it rides; mounts: False for an
    accessory, whose clash with a mount is cyborg.seat_shared's). A chain part replaces its chain's joints from the cut
    to the tip: a layer on the chain's region whose share runs past the cut's share, or seated on one of those joints or
    their sockets, is covered. A mount covers its own socket. A ball or dome implant swaps the eye part on its joint and
    covers nothing a layer stands on (the monocle beside it is C4's fit to judge)"""
    B = base_data if base_data is not None else BASES.get(base)
    if B is None or not layers or not placements:
        return []
    chains = man.get('chains') or {}
    socks = man.get('sockets') or {}
    regions_of = B.get('chain_regions') or {}
    gone = []
    for pl in placements:
        if pl.get('interface') != 'chain':
            continue
        c = chains.get(pl.get('chain')) or {}
        js = set(pl.get('joints') or [])
        k = pl.get('cut')
        cut = next((ct for ct in c.get('cuts') or [] if isinstance(ct, dict) and ct.get('joint') == k), {})
        sh = cut.get('s')
        if not _share_ok(sh):
            ss = c.get('s') if isinstance(c.get('s'), (list, tuple)) else []   # no cut share: from joint k - 1's
            sh = ss[k - 1] if isinstance(k, int) and 0 < k <= len(ss) else 0.0
            if not _share_ok(sh):
                sh = 0.0                  # no share to judge from: the whole chain (check_manifest reports the record)
        on = {s for s, d in socks.items() if d.get('bone') in js}
        gone.append((pl, float(sh), js, on, regions_of.get(pl['kind'])))
    covers = {pl['site']: pl for pl in placements if pl.get('interface') == 'mount'}
    on_any = set().union(*(g[3] for g in gone)) if gone else set()
    out = []
    for where, what, reach in layers:
        regs = reach.get('regions')
        ss, bs = set(reach.get('sockets') or ()), set(reach.get('bones') or ())
        for pl, sh, js, on, reg in gone:
            lo, hi = reach.get('s') or ((B.get('growth_s') or {}).get(pl['kind'], (0.0, 1.0)) if reach.get('growth')
                                        else (0.0, 1.0))
            why = []
            if (regs is None or (reg is not None and reg in regs)) and hi > sh + 1e-9:
                why.append(f'its sites run along {pl["site"]} to share {hi:.3f}, past the cut at {sh:.4f}')
            if ss & on:
                why.append(f'it seats on {", ".join(sorted(ss & on))}')
            if bs & js:
                why.append(f'it rides {", ".join(sorted(bs & js))}')
            if why:
                out.append(_P('error', 'cyborg.covered', where,
                              f'{what}: {"; ".join(why)}, which {pl["part"]}.{pl["variant"]} replaces from joint '
                              f'{pl["cut"]} ({pl["joints"][0]}) to the tip. Left on a replaced limb it floats (the '
                              'lead\'s A.9 decision 4: an error): keep it to the flesh (a share below the cut), or '
                              'drop it'))
        if reach.get('mounts', True):
            for s in sorted(ss - on_any):
                pl = covers.get(s)
                if pl is not None:
                    out.append(_P('error', 'cyborg.covered', where,
                                  f'{what} seats on {s}, which {pl["part"]}.{pl["variant"]} covers: it would stand '
                                  'under the part (the lead\'s A.9 decision 4: an error)'))
    return out


# ============================================================================================ the resolver
def _chain_of(chains, name):
    if name in chains:
        return name
    hits = [n for n, c in chains.items() if c.get('label') == name]
    return hits[0] if len(hits) == 1 else None


def plan(cyb, man, base, level=0, seed=0, pick=None, accessories=(), base_data=None, check_man=True):
    """the cyborg section resolved on a BUILT creature's manifest: (placements, problems). Every kind table K places on
    the manifest's sites of kind K only (one row per site: the rows whose band holds the level, whose side matches the
    site's and whose site, if pinned, is this one; a weighted pick by pick(seed, 'cyborg.<K>.<site>', weights), the
    recipe's roll); a row whose part does not fit K is REFUSED, never placed (amendment 1); a sided row no site of K
    matches is an error (it would place nothing); every limb row replaces its chain record from a listed cut, and is
    checked at any level (its band gates only the placement). Each placement is then checked: the socket's interface
    (and the variant's), the typed seat and its validated entry, what the family requires (a gripper's replaced
    chain, a back mount's mount plate and G5's hat probe over its whole reach, a machine head's jaw), sides, Skye's
    rule, and seat_shared over every accessory seated on the socket or on its SEAT GROUP (amendment 4; the lead's C0b
    call; accessories = [(socket, item, archetype[, how])], how = why the item holds that socket: an ENCLOSING item
    claims every socket it encloses, recipe._accessory_seats). A 'none' row the pick takes places nothing: the site
    stays empty, by the seed (C0b). check_man adds check_manifest()'s problems (amendment 2). recipe.resolve_cyborg
    raises SlotError on any error"""
    if pick is None:
        raise TypeError('plan() needs pick(seed, key, weights): the recipe\'s seeded weighted pick (recipe.pick_weighted)')
    out = list(check_recipe(cyb, base=base))
    placements = []
    if not cyb or not isinstance(cyb, dict):           # a malformed section: check_recipe said so
        return placements, out
    if man is None:
        out.append(_P('error', 'cyborg.untyped', 'cyborg', 'no manifest: cyborg parts resolve only on a built '
                                                           'creature\'s typed sockets'))
        return placements, out
    B = base_data if base_data is not None else BASES.get(base)
    if check_man:
        out += check_manifest(man, base, base_data=B)
    socks = man.get('sockets') or {}
    chains = man.get('chains') or {}
    regions = man.get('regions') or {}
    typed = {s: d for s, d in socks.items() if isinstance(d.get('slot'), dict)}
    seat_users = {}

    def where_of(K, site):
        return f'cyborg.parts.{K}@{site}'

    for K, rows in (cyb.get('parts') if isinstance(cyb.get('parts'), dict) else {}).items():
        if K not in KINDS or not isinstance(rows, list) or KINDS[K]['cls'] == 'chain':
            continue                                      # check_recipe reported it
        good = [(i, r) for i, r in enumerate(rows) if isinstance(r, dict) and isinstance(r.get('part'), str)
                and (r['part'] in FAMILIES or r['part'] == NONE)]
        if KINDS[K]['cls'] == 'region':
            sites = sorted(n for n, g in regions.items() if g.get('kind') == K)
        else:
            sites = sorted(s for s, d in typed.items() if d['slot'].get('kind') == K)
        # amendment 1, the resolver's half: a row whose part does not fit K, or breaks Skye's rule on K whatever FITS
        # says, is never a candidate on K's sites (the 'none' row fits every table: it places nothing)
        fits_k = lambda F: F == NONE or (K in FAMILIES[F]['fits'] and 'chain' not in FAMILIES[F]['interfaces'] and
                                         (KINDS[K]['cls'] == 'region') == ('region' in FAMILIES[F]['interfaces']) and
                                         not never(F, K))
        for i, r in good:
            if sites and not fits_k(r['part']):
                F = r['part']
                why = never(F, K)
                out.append(_P('error', 'cyborg.never' if why else 'cyborg.kind', f'cyborg.parts.{K}[{i}]',
                              f'refused: {F} is never placed on {", ".join(sites)} (kind {K!r}): ' +
                              (f'Skye\'s rule, {why}' if why else f'it fits {list(FAMILIES[F]["fits"])} only')))
        # rows pinned to a site (a hand-edited recipe): the site must exist, be typed, and be of this table's kind
        for i, r in good:
            st = r.get('site')
            if not isinstance(st, str):                   # none, or malformed (check_recipe said so)
                continue
            w = f'cyborg.parts.{K}[{i}]'
            if KINDS[K]['cls'] == 'region':
                if st not in regions:
                    out.append(_P('error', 'cyborg.unknown', w, f'{r["part"]} names region {st!r}, which the built '
                                                                'creature lacks'))
            elif st not in socks:
                out.append(_P('error', 'cyborg.unknown', w, f'{r["part"]} names socket {st!r}, which the built creature '
                                                            f'lacks'))
            elif st not in typed:
                out.append(_P('error', 'cyborg.untyped', w, f'{r["part"]} names {st}, which carries no slot extras: '
                                                            'an untyped socket takes no cyborg part'))
            elif typed[st]['slot'].get('kind') != K:
                sk = typed[st]['slot'].get('kind')
                out.append(_P('error', 'cyborg.kind', w,
                              f'{r["part"]} is pinned to {st}, a {sk!r} slot, from the {K!r} table: a row seats only '
                              f'on its table\'s kind' + ('' if r['part'] == NONE or sk in FAMILIES[r['part']]['fits']
                                                         else f'; {r["part"]} fits '
                                                              f'{list(FAMILIES[r["part"]]["fits"])}')))
                why = never(r['part'], sk)
                if why:
                    out.append(_P('error', 'cyborg.never', w, f'{r["part"]} on {st} ({sk}): Skye\'s rule, {why}'))
        if not sites:
            asked = ", ".join(sorted({r["part"] for _, r in good if r['part'] != NONE}))
            if not asked:                                 # no rows, or 'none' rows only: nothing was asked for
                continue
            if KINDS[K]['cls'] == 'region':
                out.append(_P('error', 'cyborg.untyped' if not regions else 'cyborg.no_site', f'cyborg.parts.{K}',
                              f'no {K!r} region on this {base} for {asked} (scene extras bestiary.regions; C13)'))
            elif not typed:
                out.append(_P('error', 'cyborg.untyped', f'cyborg.parts.{K}',
                              f'the manifest\'s sockets carry no slot extras (an old glb): no cyborg part seats on it '
                              f'({asked} asked for {K!r}); t13 writes them (work/bestiary/patches/cyborg_c0_t13.md)'))
            else:
                why = ((B or {}).get('lacks') or {}).get(K)
                out.append(_P('error', 'cyborg.no_site', f'cyborg.parts.{K}',
                              f'no {K!r} slot on this {base} for {asked}' + (f': {why}' if why else
                                                                             ' (never skipped silently: G2)')))
            continue
        # a SIDED row that no site of K matches would place nothing (the C0 check: 'eye_implant side L' on unsided eyes,
        # a head row 'side L' on the unsided head seat): an error at any level, never skipped silently (G2)
        sides_k = {s: ((((typed.get(s) or {}).get('slot') or {}).get('side') or '') if KINDS[K]['cls'] == 'socket'
                       else (regions[s].get('side') or '')) for s in sites}
        for i, r in good:
            rs = r.get('side')
            if rs in ('L', 'R') and rs not in sides_k.values():
                out.append(_P('error', 'cyborg.side', f'cyborg.parts.{K}[{i}]',
                              f'{r["part"]} says side {rs}, and no {K!r} slot on this {base} is side {rs} ('
                              + ', '.join(f'{s}: {v or "no side"}' for s, v in sorted(sides_k.items()))
                              + '): the row would place nothing (never skipped silently: G2)'))
        if good and not any(_in_band(r, level) for _, r in good):
            out.append(_P('warning', 'cyborg.no_row', f'cyborg.parts.{K}',
                          f'no row covers level {level}: the {K!r} sites ({", ".join(sites)}) stay empty'))
        for site in sites:
            sd = typed.get(site) if KINDS[K]['cls'] == 'socket' else None
            sside = (sd or {}).get('slot', {}).get('side', '') if sd else (regions[site].get('side') or '')
            for _, r in good:
                if r.get('site') == site and r.get('side') and r.get('side') != sside:
                    out.append(_P('error', 'cyborg.side', where_of(K, site),
                                  f'{r["part"]} says side {r["side"]} but {site} is side {sside or "none"}'))
            cand = [r for _, r in good if fits_k(r['part']) and _in_band(r, level) and r.get('site') in (None, site)
                    and (not r.get('side') or r.get('side') == sside)]
            wts = {str(i): float(r.get('weight', 1.0)) for i, r in enumerate(cand)
                   if isinstance(r.get('weight', 1.0), (int, float)) and not isinstance(r.get('weight', 1.0), bool)
                   and r.get('weight', 1.0) > 0}
            if not wts:
                continue
            row = cand[int(pick(seed, f'cyborg.{K}.{site}', wts))]
            F = row['part']
            if F == NONE:
                continue                                  # the band picked no part: the site stays empty, by the seed
            d = FAMILIES[F]
            v = row.get('variant') or d['variants'][0]
            w = where_of(K, site)
            if v not in d['variants']:
                continue                                  # check_recipe reported the unknown variant
            pl = dict(kind=K, site=site, part=F, variant=v, interface=None, seat=None,
                      joint=(sd or {}).get('bone'), key=f'cyborg.{K}.{site}', row=dict(row))
            if KINDS[K]['cls'] == 'region':
                g = regions[site]
                pl['interface'] = 'region'
                if 'keeps_jaw' in d['requires'] and not g.get('keeps_jaw'):
                    out.append(_P('error', 'cyborg.requires', w, f'{F} on region {site}: the region record does not '
                                                                 'keep the jaw joint (G6: a machine head still talks)'))
                placements.append(pl)
                continue
            iface = sd['slot'].get('interface')
            pl['interface'] = iface
            if iface not in d['interfaces']:
                out.append(_P('error', 'cyborg.interface', w, f'{F} ({"/".join(d["interfaces"])}) on {site}, a '
                                                              f'{iface!r} socket'))
            vi = (d.get('variant_interface') or {}).get(v)
            if vi and iface in d['interfaces'] and vi != iface:
                out.append(_P('error', 'cyborg.interface', w, f'{F} variant {v!r} rides a {vi!r} eye; {site} is '
                                                              f'{iface!r} (G8: the variant follows the eye archetype)'))
            if d['seat']:
                arch = d['seat']
                pl['seat'] = f'seat_{arch}'
                seat = (sd.get('seats') or {}).get(arch)
                entry = None
                if seat is None:
                    out.append(_P('error', 'cyborg.seat', w, f'{F} on {site}: no seat_{arch} under it (a mount seats '
                                                             'only under its typed seat; no fallback mount point)'))
                else:
                    entry = ((seat.get('fit') or {}).get('validated') or {}).get(f'{F}.{v}')
                    if entry is None:
                        out.append(_P('error', 'cyborg.seat', w, f'{F}.{v} on {site}: seat_{arch} holds no validated '
                                                                 'entry for it (sizes and frames come from the seat\'s '
                                                                 'validated fit, never a box: G3)'))
                if 'mount_plate' in d['requires'] and seat is not None and not (seat.get('fit') or {}).get('mount_plate'):
                    out.append(_P('error', 'cyborg.requires', w, f'{F} on {site}: no mount plate under seat_{arch} (a '
                                                                 'back mount stands on a conforming plate, never a '
                                                                 'pedestal: N6)'))
                if 'reach' in d['requires']:
                    reach = (entry or {}).get('reach')
                    if entry is not None and not (isinstance(reach, (int, float)) and reach > 0):
                        out.append(_P('error', 'cyborg.seat', w, f'{F}.{v} on {site}: its validated entry declares no '
                                                                 'reach (G5 clears the WHOLE reach envelope)'))
                    probe = head_probe(man, base, site, reach if isinstance(reach, (int, float)) else 0.0, seat=seat,
                                       base_data=B)
                    for msg, _nums in probe:
                        out.append(_P('error', 'cyborg.head_probe', w, f'{F}.{v}: {msg}'))
                seat_users.setdefault(site, []).append(f'{F}.{v}')
            if 'chain_replaced' in d['requires']:
                owner = [n for n, c in chains.items() if c.get('tip') == site]
                pl['chain'] = owner[0] if owner else None
            why = never(F, K)
            if why:
                out.append(_P('error', 'cyborg.never', w, f'{F} on {site} ({K}): Skye\'s rule, {why}'))
            placements.append(pl)
    # the limbs: a chain record replaced from a listed cut to its tip
    replaced = {}
    for i, row in enumerate(cyb.get('limbs') if isinstance(cyb.get('limbs'), list) else []):
        if not isinstance(row, dict) or not isinstance(row.get('part'), str) or row['part'] not in FAMILIES:
            continue
        # every limb row is checked at ANY level, as a pinned parts row is; its band gates only the placement (the C0
        # check: an out-of-band row naming a beetle leg as 'tentacle', or a chain and a cut that do not exist, validated
        # clean until the level reached it)
        in_band = _in_band(row, level)
        w = f'cyborg.limbs[{i}]'
        F, K = row['part'], row.get('kind')
        d = FAMILIES[F]
        if 'chain' not in d['interfaces'] or not isinstance(K, str) or K not in CHAIN_KINDS:
            out.append(_P('error', 'cyborg.interface', w, f'refused: {F} on {row.get("chain")!r} as {K!r}: only a '
                                                          'chain part replaces a chain kind'))
            continue
        if not isinstance(row.get('chain'), str):
            continue                                      # check_recipe reported it
        if not chains:
            out.append(_P('error', 'cyborg.untyped', w, f'{F} on {row.get("chain")!r}: the manifest carries no chain '
                                                        'records (scene extras bestiary.chains; t13 writes them)'))
            continue
        cn = _chain_of(chains, row.get('chain'))
        if cn is None:
            out.append(_P('error', 'cyborg.unknown', w, f'{F}: no chain {row.get("chain")!r} (have: '
                                                        f'{", ".join(sorted(chains))})'))
            continue
        c = chains[cn]
        if c.get('kind') != K:
            out.append(_P('error', 'cyborg.kind', w, f'refused: {F} names {cn} as {K!r}, and {cn} is a '
                                                     f'{c.get("kind")!r} chain'))
            continue
        if K not in d['fits']:
            out.append(_P('error', 'cyborg.kind', w, f'refused: {F} does not fit {cn} ({K}); it fits '
                                                     f'{list(d["fits"])}'))
            continue
        if never(F, K):
            out.append(_P('error', 'cyborg.never', w, f'refused: {F} on {cn} ({K}): Skye\'s rule, {never(F, K)}'))
            continue
        # (C3) chain_role_arm: the leg_fore chain must be an ARM, its joints running to a hand (the human's clavicle ->
        # upperarm -> lowerarm -> hand; a wolf's or an axolotl's fore leg runs to a carpus and is refused)
        if 'chain_role_arm' in d['requires'] and not (
                base == 'human' or any(re.sub(r'_[LR]$', '', str(j)) == 'hand' for j in c.get('joints') or [])):
            out.append(_P('error', 'cyborg.requires', w, f'refused: {F} on {cn}: its family needs an ARM (a {K} chain '
                                                         'whose joints run to a hand), and this one runs to '
                                                         f'{(c.get("joints") or ["nothing"])[-1]!r}'))
            continue
        cuts = [ct.get('joint') for ct in c.get('cuts') or [] if isinstance(ct, dict)]
        cj = row.get('cut_joint')
        if cj not in cuts:
            out.append(_P('error', 'cyborg.cut', w, f'{F} on {cn} at joint {cj!r}: not a listed cut ({cuts}): no ring '
                                                    'to cut at, no weights to pin'))
            continue
        if not in_band:
            continue
        if cn in replaced:
            out.append(_P('error', 'cyborg.seat_shared', w, f'{F} on {cn}: the chain is already replaced by '
                                                            f'{replaced[cn]}'))
            continue
        held = [k_ for k_, v_ in replaced.items() if v_.split('.')[0] == F]
        if F == 'mech_tentacle' and held:
            out.append(_P('error', 'cyborg.limit', w, f'{F} on {cn}: v1 mounts ONE mech arm per creature (the '
                                                      'lead\'s C5c call: the runtime carries one replaced arm\'s '
                                                      f'ground line and AO floor), and {held[0]} carries one'))
            continue
        v = row.get('variant') or d['variants'][0]
        replaced[cn] = f'{F}.{v}'
        js = list(c.get('joints') or [])
        placements.append(dict(kind=K, site=cn, part=F, variant=v, interface='chain', seat=None, chain=cn, cut=cj,
                               joints=js[cj:], key=f'cyborg.limbs.{cn}', row=dict(row)))
    # what needs the limbs: a gripper on a tip whose chain is replaced
    for pl in placements:
        if 'chain_replaced' in FAMILIES[pl['part']]['requires']:
            w = where_of(pl['kind'], pl['site'])
            if pl.get('chain') is None:
                out.append(_P('error', 'cyborg.requires', w, f'{pl["part"]} on {pl["site"]}: no chain record names this '
                                                             'tip'))
            elif pl['chain'] not in replaced:
                out.append(_P('error', 'cyborg.requires', w, f'{pl["part"]} on {pl["site"]}: an ORGANIC tip ({pl["chain"]} '
                                                             'is not replaced): a gripper rides a mech chain only'))
    # seat_shared (amendment 4; the lead's C0b calls): a cyborg mount and ANY accessory holding the same socket, or a
    # socket of its SEAT GROUP (the octopus's head top and mantle apex: one head), or two mounts on one seat or group.
    # An accessory holds its seat, the sockets its bone carries (recipe._accessory_seats), and, an ENCLOSING one, every
    # socket it encloses (the space helmet: the face)
    group = seat_groups(man, base, base_data=B)
    acc_on = {}
    for a in accessories:
        sock, item, arch = a[0], a[1], a[2]
        how = a[3] if len(a) > 3 and a[3] else ''
        acc_on.setdefault(sock, []).append(f'{item} ({arch}' + (f'; {how}' if how else '') + ')')
    for site, who in sorted(seat_users.items()):
        g = group.get(site, (site,))
        same = acc_on.get(site, [])
        other = [f'{x} on {s}' for s in g if s != site for x in acc_on.get(s, [])]
        if same or other:
            out.append(_P('error', 'cyborg.seat_shared', f'cyborg@{site}',
                          f'{", ".join(who)} on {site} with ' + '; '.join(
                              ([', '.join(same)] if same else []) +
                              ([f'{", ".join(other)}, in its seat group ({", ".join(g)}: one seat)'] if other else []))
                          + ': a cyborg part and an accessory never share a seat in v1 (a head module XOR a hat; the '
                            'lead, 10-21)'))
    done = set()
    for site in sorted(seat_users):
        g = tuple(group.get(site, (site,)))
        if g in done:
            continue
        done.add(g)
        who = [x + ('' if s == site and len(g) == 1 else f' on {s}') for s in g for x in seat_users.get(s, [])]
        if len(who) > 1:
            out.append(_P('error', 'cyborg.seat_shared', 'cyborg@' + '+'.join(g), f'{len(who)} cyborg parts on '
                                                                                  f'{" / ".join(g)}: {", ".join(who)}'))
    return placements, out


def describe():
    """the closed table, Skye's rule and the per-base tables, as text"""
    pairs = allowed_pairs()
    nev = [(f, k) for f in FAMILIES for k in KINDS if never(f, k)]
    lines = [f'[slots] {len(FAMILIES)} families x {len(KINDS)} kinds ({len(SOCKET_KINDS)} socket, {len(CHAIN_KINDS)} '
             f'chain, {len(REGION_KINDS)} region) = {len(FAMILIES) * len(KINDS)} pairs: {len(pairs)} allowed, '
             f'{len(FAMILIES) * len(KINDS) - len(pairs)} refused; table checks: {check_table() or "ok"}']
    for f, d in FAMILIES.items():
        lines.append(f'  {f:16s} {"/".join(d["interfaces"]):9s} fits {", ".join(d["fits"]):30s} seat '
                     f'{d["seat"] or "-":7s} class {PART_CLASS[f]:6s} variants {", ".join(d["variants"])}')
    lines.append(f'  Skye\'s rule: {len(nev)} never pairs ({", ".join(f"{c} x {r}" for c, r in NEVER)}), apart from '
                 'the closed table')
    lines.append('  seat kinds: ' + '; '.join(f'seat_{a} under {", ".join(k)}' for a, k in SEAT_KINDS.items()))
    lines.append('  ports: extras.slot carries frame {normal, tangent} in its joint\'s frame and dims by interface ('
                 + '; '.join(f'{i}: {", ".join(k) or "none"}' for i, k in DIMS_KEYS.items()) + f'); mount dims on the '
                 f'kit\'s TC70 pattern (bolt circle {KIT_FLANGE["bolt_circle"]:.4f} r, pilot {KIT_FLANGE["pilot"]:.4f} '
                 f'r, {KIT_FLANGE["bolts"]} bolts); a kind table may hold a {NONE!r} row')
    for b, B in BASES.items():
        lines.append(f'  {b}: socket kinds {", ".join(B["joints"])}; chains {", ".join(B["chains"])}; head region '
                     f'{B["head_region"]} (+{B["head_margin"]} m)' + (f'; lacks {", ".join(B["lacks"])}'
                                                                      if B.get('lacks') else '') +
                     (f'; seat groups {B["seat_groups"]}' if B.get('seat_groups') else '') +
                     (f'; chain regions {B["chain_regions"]}' if B.get('chain_regions') else '') +
                     (f'; growths along {B["growth_s"]}' if B.get('growth_s') else ''))
    return '\n'.join(lines)


if __name__ == '__main__':
    print(describe())
