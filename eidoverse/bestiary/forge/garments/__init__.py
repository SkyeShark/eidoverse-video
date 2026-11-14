"""GARMENTS (B2, ROADMAP §3): clothing generated on the human body at its phenotype, draped once at the forge.

    body.py       the human glb as the garment builder reads it: skin_BODY (T rest), weights, skeleton, rings, LBS, the A-pose
    pattern.py    the garment specs (tee, shirt short / long, trousers) and their rest shapes on the body (ease envelopes)
    meshops.py    cut by a field's iso-line, subdivision, boundary loops, hems
    drape.py      the cloth solve (XPBD in Warp: stretch, bend, gravity, the body as a collider, friction)
    construct.py  the construction: hems, collar, cuffs, placket, buttons, seams and their fields
    shoes.py      the derby shoe on the foot
    necktie.py    the tie, a seated prop on socket_chest
    skin.py       weights by transfer from the body, the cloth offset, A -> T unposing
    maps.py       UVs, the bake (folds from the high drape, seams / stitches / hems as a height field), weave tiles, MASKS
    export.py     the clothed glb (the body glb plus garment meshes on its skin, the hidden-face mask)
    cache.py      the cache by (pheno hash, garment)
    gates.py      the ROM stand-off gate, texel density
Frame: metres, +Y up, +Z forward, +X the body's LEFT (DESIGN.md); the glb's rest is the VRM T-pose.
"""
