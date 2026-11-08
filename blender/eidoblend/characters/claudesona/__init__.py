"""eidoblend.characters.claudesona: the claudesona (digi's claude_suit.vrm and claude_suit_wardrobe.vrm) in Blender 5.2
EEVEE: its face, mouths and face tracks (face: claudesona_face.js), its wardrobe and the TuTa (wardrobe, tuta:
claudesona_wardrobe.js) and the MToon / PBR look (look). tools-guides/claudesona.md describes this edition.

    from eidoblend.characters import load_vrm
    from eidoblend.characters.claudesona import face, make_wardrobe, set_look
    me = load_vrm('claude_suit_wardrobe'); me.arm.scale = (0.87,) * 3      # 2.00 m rig -> a human 1.74 m
    wd = make_wardrobe(me, wear='lab_coat_1961')                          # wear(key, frame=...) keys an outfit
    f = face.install_suit_mouth(me)                                       # f.bake(fn, f0, f1) keys the face
    wd = make_wardrobe(me, wear='tuta'); wd.pin('mod_red'); wd.bake(1, 240)   # the TuTa: badges, paint, disc, neon

Every switch is keyed Blender data: outfits are keyed object visibility plus float properties on the armature
('cs_paint.*', 'cs_hide.*', 'cs_tuta.*') read by drivers (made with _paint.new_prop / _paint.drive, which keep the
evaluated armature and the drivers valid), the face is shape-key actions, badges are keyed objects.

The VRM extras that every VRM shares live beside it in eidoblend.characters: springs (spring bones baked to keys),
lookat (eyes on a target) and lipsync (visemes from audio, keyed). The turntable is blender/tools/vrm_turntable.py.
"""

from . import face  # noqa: F401
from .face import (LINE_WARP, MOUTH_OPEN, MOUTH_ROUND, PHONE_VISEME, SUIT_VISEMES, VISEME_SHAPES, VISEMES,  # noqa: F401
                   events_from_phones, install_suit_mouth, install_viseme_mouth, make_face_track, make_suit_mouth,
                   make_viseme_track, merge_max)
from .look import refresh_pbr, set_look  # noqa: F401
from .tuta import BADGES, FINAL_CHORUS, MODIFICANTI, TutaWardrobe  # noqa: F401
from .wardrobe import APPLE, C64, OPTIONAL, SUIT, WARDROBE, Wardrobe, make_wardrobe, preset  # noqa: F401
