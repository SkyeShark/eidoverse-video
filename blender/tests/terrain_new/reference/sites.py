"""The real places the references come from: where, how big, from which open dataset, and the three probe views.

Each entry:
  title, landform, note       what it is
  lat, lon                    the centre of the tile (WGS84)
  extent_m, pixel_m           the square tile's side and its pixel, metres
  source                      the dataset (fetch_references.py: gsi | usgs3dep | copernicus | swissalti3d | terrarium)
  context                     the wider, coarser surround for the eye-level view (its own extent, pixel and source)
  water                       sea (a plane at level_m) and lakes (a flood fill from a seed at the water's DEM level)
  views                       aerial: azimuth_deg = compass bearing from the tile centre to the 45-degree camera
                              eye: at = (lat, lon) the 1.7 m camera stands on, look = (lat, lon) it looks at (that
                              ground point, raised look_dz metres), lens_mm (36 mm film back)
"""

SITES = {
    'mount_fuji': dict(
        title='Mount Fuji, Japan', landform='stratovolcano',
        note='The whole cone (3776 m) with its apron, the Hoei crater on the south-east flank and the Fuji Five Lakes '
             'to the north.',
        lat=35.3606, lon=138.7274, extent_m=40000, pixel_m=40,
        source=dict(kind='gsi', zoom=13),
        context=dict(extent_m=120000, pixel_m=120, source=dict(kind='gsi', zoom=10)),
        water=[dict(kind='lake', name='Lake Kawaguchi', seed=(35.5135, 138.7600)),
               dict(kind='lake', name='Lake Yamanaka', seed=(35.4180, 138.8750)),
               dict(kind='lake', name='Lake Sai', seed=(35.4990, 138.6850)),
               dict(kind='lake', name='Lake Motosu', seed=(35.4640, 138.5800))],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(35.4050, 138.5850), look=(35.3606, 138.7274), look_dz=-1450, lens_mm=70)),
    ),
    'crater_lake': dict(
        title='Crater Lake, Oregon, USA', landform='caldera',
        note='The collapsed summit of Mount Mazama: a 8 x 10 km caldera, its walls 500-600 m above the lake, Wizard '
             'Island (a cinder cone) in the west of the lake.',
        lat=42.9420, lon=-122.1080, extent_m=14000, pixel_m=14,
        source=dict(kind='usgs3dep', sample_m=7),
        context=dict(extent_m=42000, pixel_m=42, source=dict(kind='usgs3dep', sample_m=42)),
        water=[dict(kind='lake', name='Crater Lake', seed=(42.9446, -122.1090))],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(42.91213, -122.14700), look=(42.9650, -122.1350), look_dz=0, lens_mm=28)),
    ),
    'meteor_crater': dict(
        title='Meteor Crater (Barringer Crater), Arizona, USA', landform='simple impact crater',
        note='A 1.2 km bowl, 170 m deep, its raised rim 30-60 m above the plain and the ejecta blanket around it.',
        lat=35.0274, lon=-111.0228, extent_m=3000, pixel_m=3,
        source=dict(kind='usgs3dep', sample_m=1.5),
        context=dict(extent_m=15000, pixel_m=15, source=dict(kind='usgs3dep', sample_m=15)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(35.0324, -111.0226), look=(35.0225, -111.0228), look_dz=0, lens_mm=24)),
    ),
    'grand_canyon_toroweap': dict(
        title='Grand Canyon at Toroweap, Arizona, USA', landform='canyon in layered strata',
        note='The inner gorge, 880 m sheer below the Toroweap Overlook, cut through the Esplanade bench; the outer '
             'canyon walls step back in cliffs and slopes, strata by strata.',
        lat=36.2130, lon=-113.0600, extent_m=8000, pixel_m=8,
        source=dict(kind='usgs3dep', sample_m=4),
        context=dict(extent_m=32000, pixel_m=32, source=dict(kind='usgs3dep', sample_m=32)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(36.21620, -113.05569), look=(36.2310, -113.0332), look_dz=300, lens_mm=24)),
    ),
    'monument_valley': dict(
        title='Monument Valley, Arizona / Utah, USA', landform='mesas and buttes',
        note='The Mittens and Merrick Butte: sandstone buttes 150-300 m tall with sheer walls over talus aprons, on '
             'a broad sandy floor.',
        data_note='3DEP serves 1 m lidar only north of the Utah border (the top ~quarter of the tile); the Arizona '
                  'part, with the Mittens and Merrick Butte, is 1/3 arc-second (~10 m): the butte walls are softer '
                  'and less sheer there than they are.',
        lat=36.9830, lon=-110.0990, extent_m=8000, pixel_m=8,
        source=dict(kind='usgs3dep', sample_m=4,
                    native_resolution_m='1/3 arc-second (~10 m) over the Arizona part (most of the tile); 1 m lidar '
                                        'only north of the Utah border'),
        context=dict(extent_m=32000, pixel_m=32, source=dict(kind='usgs3dep', sample_m=32)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(36.97085, -110.10256), look=(36.98873, -110.08546), look_dz=200, lens_mm=35)),
    ),
    'badlands_sd': dict(
        title='Badlands National Park, South Dakota, USA', landform='badlands',
        note='The Badlands Wall near Cedar Pass: soft sediments cut into dense gullies, knife ridges and pinnacles '
             'over a few hundred metres.',
        lat=43.7620, lon=-101.9350, extent_m=3000, pixel_m=3,
        source=dict(kind='usgs3dep', sample_m=1.5),
        context=dict(extent_m=12000, pixel_m=12, source=dict(kind='usgs3dep', sample_m=12)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(43.74925, -101.92639), look=(43.75389, -101.92378), look_dz=-20, lens_mm=35)),
    ),
    'badlands_sd_detail': dict(
        title='Badlands National Park, South Dakota, USA (detail)', landform='badlands (close range)',
        note='A 1.2 km piece of the Badlands Wall at 1.2 m: the fluted walls, knife ridges, pinnacles and gully '
             'floors at the scale a character walks past them.',
        lat=43.75389, lon=-101.92378, extent_m=1200, pixel_m=1.2,
        source=dict(kind='usgs3dep', sample_m=1.0),
        context=dict(extent_m=6000, pixel_m=6, source=dict(kind='usgs3dep', sample_m=6)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(43.74925, -101.92639), look=(43.75389, -101.92378), look_dz=-20, lens_mm=35)),
    ),
    'namib_star_dunes': dict(
        title='Namib star dunes near Sossusvlei, Namibia', landform='star dunes',
        note='Star dunes 200-350 m high with radiating arms around the Sossusvlei and Deadvlei clay pans.',
        data_note='Copernicus GLO-30 is a 30 m radar surface model: upsampled here, so slip faces and crest lines are '
                  'softer than the real knife-edge crests; flat pans keep a faint speckle.',
        lat=-24.7450, lon=15.3200, extent_m=8000, pixel_m=10,
        source=dict(kind='copernicus'),
        context=dict(extent_m=32000, pixel_m=32, source=dict(kind='copernicus')),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(-24.74576, 15.32104), look=(-24.77166, 15.32550), look_dz=-120, lens_mm=50)),
    ),
    'lauterbrunnen': dict(
        title='Lauterbrunnen Valley, Bernese Oberland, Switzerland', landform='glacial U-valley',
        note='A glacial trough: a flat floor about 800 m up between limestone walls 300-500 m sheer, the hanging '
             'terraces of Wengen and Muerren above them.',
        lat=46.5720, lon=7.9050, extent_m=8000, pixel_m=8,
        source=dict(kind='swissalti3d'),
        context=dict(extent_m=32000, pixel_m=32, source=dict(kind='terrarium', zoom=12)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(46.58674, 7.91127), look=(46.5400, 7.9000), look_dz=400, lens_mm=35)),
    ),
    'guilin_karst': dict(
        title='Guilin karst towers near Yangshuo, Guangxi, China', landform='tower karst (fenglin)',
        note='Limestone towers 100-300 m tall rising sheer from a flat alluvial plain along the Yulong and Li rivers.',
        data_note='Copernicus GLO-30 (30 m, a surface model including the forest on the towers) is the best open DEM '
                  'here: the towers, 100-300 m across, are only 3-10 source pixels wide, so their sheer walls come out '
                  'as steep rounded cones. Read the spacing, heights and the flat floor between them, not the walls.',
        lat=24.7800, lon=110.4600, extent_m=8000, pixel_m=8,
        source=dict(kind='copernicus'),
        context=dict(extent_m=32000, pixel_m=32, source=dict(kind='copernicus')),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(24.76209, 110.43799), look=(24.77565, 110.45370), look_dz=100, lens_mm=35)),
    ),
    'cliffs_of_moher': dict(
        title='Cliffs of Moher, County Clare, Ireland', landform='sea cliffs',
        note='Shale and sandstone sea cliffs rising 120-214 m straight out of the Atlantic for 8 km, from Hag\'s Head '
             'north past O\'Brien\'s Tower.',
        data_note='Copernicus GLO-30 (30 m) cannot resolve a vertical 200 m face: here the cliff is a steep ramp one or '
                  'two source pixels wide. The plan of the coast and the cliff-top plateau are right; seven_sisters is '
                  'the high-resolution (2 m lidar) reference for the vertical cliff itself.',
        lat=52.9620, lon=-9.4400, extent_m=6000, pixel_m=6,
        source=dict(kind='copernicus'),
        context=dict(extent_m=24000, pixel_m=24, source=dict(kind='copernicus')),
        water=[dict(kind='sea', name='Atlantic', level_m=0.0)],
        views=dict(aerial=dict(azimuth_deg=250),
                   eye=dict(at=(52.97364, -9.42710), look=(52.9497, -9.4717), look_dz=0, lens_mm=35)),
    ),
    'seven_sisters': dict(
        title='Seven Sisters chalk cliffs, East Sussex, England', landform='sea cliffs (chalk, with dry valleys)',
        note='Vertical white chalk cliffs 50-160 m high, cut across a row of dry valleys (the "sisters"), from '
             'Cuckmere Haven east past Birling Gap toward Beachy Head.',
        data_note='Terrain Tiles carry the Environment Agency 2 m lidar on this coast, so the vertical chalk faces are '
                  'resolved (one or two pixels wide at 6 m). A few straight survey-strip seams show as faint steps '
                  'inland in the north-east corner.',
        lat=50.7500, lon=0.1980, extent_m=6000, pixel_m=6,
        source=dict(kind='terrarium', zoom=15,
                    native_resolution_m='2 m on land (Environment Agency lidar, as Terrain Tiles carry it here)'),
        context=dict(extent_m=24000, pixel_m=24, source=dict(kind='terrarium', zoom=13)),
        water=[dict(kind='sea', name='English Channel', level_m=0.0)],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(50.74609, 0.19293), look=(50.75256, 0.16819), look_dz=25, lens_mm=35)),
    ),
    'great_sand_dunes': dict(
        title='Great Sand Dunes, Colorado, USA', landform='star dunes (lidar)',
        note='The tallest dunes in North America (Star Dune, about 230 m): star and reversing dunes piled against the '
             'Sangre de Cristo range by opposing winds, with Medano Creek along their foot. The high-resolution '
             'companion to the Namib reference.',
        lat=37.7450, lon=-105.5550, extent_m=5000, pixel_m=5,
        source=dict(kind='usgs3dep', sample_m=2.5),
        context=dict(extent_m=20000, pixel_m=20, source=dict(kind='usgs3dep', sample_m=20)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(37.73149, -105.53337), look=(37.74925, -105.53291), look_dz=-150, lens_mm=50)),
    ),
    'palouse_hills': dict(
        title='Palouse hills near Steptoe Butte, Washington, USA', landform='rolling loess hills',
        note='Wind-laid loess heaped into rolling dune-like hills 30-80 m high, steeper on their north-east faces: '
             'the generic rolling farmland of an establishing shot.',
        lat=47.0000, lon=-117.2400, extent_m=4000, pixel_m=4,
        source=dict(kind='usgs3dep', sample_m=2),
        context=dict(extent_m=16000, pixel_m=16, source=dict(kind='usgs3dep', sample_m=16)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(46.99433, -117.23212), look=(47.00718, -117.25052), look_dz=0, lens_mm=35)),
    ),
    # ---- added by the judge package (DESIGN.md section 11, package 2): the reference gaps of section 12 item 7
    'san_gabriel_mountains': dict(
        title='San Gabriel Mountains, California, USA', landform='river-carved mountain range',
        note='The steep eastern San Gabriels around the East Fork of the San Gabriel River, west of Mount San Antonio: '
             'a range carved by rivers alone (never glaciated), its hillslopes near the landslide threshold and its '
             'valleys branching down to first-order gullies; DiBiase et al. (2010) measured here how hillslope angle '
             'and relief follow erosion rate.',
        lat=34.2800, lon=-117.7600, extent_m=12000, pixel_m=12,
        source=dict(kind='usgs3dep', sample_m=6),
        context=dict(extent_m=48000, pixel_m=48, source=dict(kind='usgs3dep', sample_m=48)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(34.32495, -117.75654), look=(34.2886, -117.6467), look_dz=-400, lens_mm=35)),
    ),
    'sp_crater': dict(
        title='SP Crater, San Francisco volcanic field, Arizona, USA', landform='cinder cone field',
        note='SP Crater, a young cinder cone with its summit crater and the basalt flow that left its base for the '
             'north, among older, lower and breached cones on the lava plateau north of Flagstaff.',
        lat=35.5700, lon=-111.6300, extent_m=10000, pixel_m=10,
        source=dict(kind='usgs3dep', sample_m=5),
        context=dict(extent_m=40000, pixel_m=40, source=dict(kind='usgs3dep', sample_m=40)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(35.56000, -111.63200), look=(35.58330, -111.63170), look_dz=0, lens_mm=70)),
    ),
    'goosenecks': dict(
        title='Goosenecks of the San Juan River, Utah, USA', landform='incised (entrenched) meanders',
        note='The San Juan River entrenched about 300 m into flat-lying layered rock, looping back on itself below '
             'Goosenecks State Park: some 10 km of river for 2.4 km of westward progress, the canyon walls stepped '
             'in ledges and slopes.',
        lat=37.1720, lon=-109.9270, extent_m=6000, pixel_m=6,
        source=dict(kind='usgs3dep', sample_m=3),
        context=dict(extent_m=24000, pixel_m=24, source=dict(kind='usgs3dep', sample_m=24)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(37.17450, -109.92550), look=(37.16728, -109.93049), look_dz=0, lens_mm=24)),
    ),
    'yosemite_valley': dict(
        title='Yosemite Valley, California, USA', landform='glacial trough (U-valley)',
        note='A glacial trough in granite: a flat floor about 1200 m up between walls rising 900-1400 m (El Capitan, '
             'Cathedral Rocks, Half Dome), the hanging valleys of Yosemite and Bridalveil Creeks above it and '
             'Tenaya Canyon branching off to the north-east.',
        lat=37.7400, lon=-119.5855, extent_m=12000, pixel_m=12,
        source=dict(kind='usgs3dep', sample_m=6),
        context=dict(extent_m=48000, pixel_m=48, source=dict(kind='usgs3dep', sample_m=48)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(37.74286, -119.59485), look=(37.7459, -119.5332), look_dz=-300, lens_mm=35)),
    ),
    'white_sands': dict(
        title='White Sands, New Mexico, USA', landform='crescentic dunes (transverse and barchanoid)',
        note='Gypsum dunes a few metres to about 10 m high in the core of the field: transverse and barchanoid ridges '
             'about 100 m apart, their slip faces to the north-east under the south-westerly winds; the dome dunes '
             'and Alkali Flat are just to the west.',
        lat=32.8050, lon=-106.2880, extent_m=3000, pixel_m=3,
        source=dict(kind='usgs3dep', sample_m=1.0),
        context=dict(extent_m=12000, pixel_m=12, source=dict(kind='usgs3dep', sample_m=12)),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(32.80669, -106.29261), look=(32.80446, -106.29525), look_dz=5, lens_mm=35)),
    ),
    'namib_linear_dunes': dict(
        title='Namib linear dunes south of Gobabeb, Namibia', landform='linear (seif) dunes',
        note='Linear dunes about 2 km apart running north-south for tens of kilometres, with Y-junctions, in the '
             'northern Namib Sand Sea south of the Kuiseb River near the Gobabeb research station.',
        data_note='Copernicus GLO-30 is a 30 m radar surface model: upsampled here, so the crests are softer than the '
                  'real sharp crests and the interdune corridors keep a faint speckle.',
        lat=-23.6500, lon=14.9800, extent_m=10000, pixel_m=10,
        source=dict(kind='copernicus'),
        context=dict(extent_m=40000, pixel_m=40, source=dict(kind='copernicus')),
        water=[],
        views=dict(aerial=dict(azimuth_deg=200),
                   eye=dict(at=(-23.62594, 14.96444), look=(-23.62079, 14.96638), look_dz=-20, lens_mm=35)),
    ),
}
