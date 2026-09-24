# Voice machines — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md) · [Credits](../../../../CREDITS.md)

## Original work

Everything that ships here was made by Claude (Opus 5.5) with Skye for the
DAISY music video (2026-09), and is released with this repository (see
[LICENSE](../../../../LICENSE) and [CREDITS](../../../../CREDITS.md)). That
covers:

- the geometry of all eight machines, modelled in Blender 5.2;
- the era-1 masks and layouts;
- the era-2 baked colour, normal and AO/roughness maps, including the
  printed labels and period marks baked into them;
- the modules in `eidoverse/props/voice_machines/`, with everything they draw
  on canvas at runtime (labels, dials, screens, the Teletype paper).

No third-party mesh data and no reference photograph is part of any file. The build
scripts are in [`../voice_machines_src/`](../voice_machines_src/README.md).

## Period marks: homages, not official artwork

The machines carry hand-drawn homages of the marks that belong to their
history. They are original artwork depicting historical products and
companies, drawn with canvas or PIL paths from scratch. No logo file is copied
or loaded. They are not the companies' official marks; the trademarks belong
to their owners, and nothing here implies an endorsement.

| Machine | Homage | Made by |
| --- | --- | --- |
| `voder` | The Bell System roundel, 1939 style: a bell in a double ring with BELL SYSTEM lettered round the top | Canvas decal in `voder.js` |
| `mainframe` | IBM's striped wordmark on the tape-drive plates and the console nameplate (the striped mark dates from 1972; a 1961 room wore the solid 1956 letters) | Canvas decals in `mainframe.js` |
| `teletype` | "T E L E T Y P E" on the band and the TT monogram on the cover (Teletype Corporation), and an M.I.T. Project MAC property tag on the pedestal | Canvas decals in `teletype.js` |
| `speakspell` | The Speak & Spell wordmark, TEXAS INSTRUMENTS in small caps and the Texas-outline "ti" mark | `era_logos.py`, baked into the card |
| `c64` | The commodore badge with the C= mark, rainbow stripes and 64, the C= key, and the monitor's commodore plate | `era_logos.py`, baked |
| `mac1984` | The six-band rainbow apple badge (baked), and a 1-bit apple in the menu bar on the screen | `era_logos.py` and `mac1984.js` |
| `dectalk` | DEC's seven-block "digital" and a red "DECtalk" on the slant | `era_logos.py`, baked |
| `desktop2001` | The four-tile flag on the Start button (screen), and the XP-style sticker on the tower and the flag keys (baked) | `desktop2001.js` and `era_logos.py` |

The desktop's screen shows a generic green hill under a blue sky drawn in
code, not the real Windows wallpaper.

## CC0 textures

**Shipped in `tex/` and read at runtime by the era-1 modules.** These are
[AmbientCG](https://ambientcg.com) sets at 1K JPG, under
[CC0 1.0](https://docs.ambientcg.com/license/). Only the `_Color`, `_NormalGL`
and `_Roughness` maps are included. A `_1k` suffix in a folder name marks the
builder's 1K download of the same set.

| Set | Used for |
| --- | --- |
| [Fabric030](https://ambientcg.com/a/Fabric030) | The Voder's loudspeaker grille cloth |
| [Fingerprints002](https://ambientcg.com/a/Fingerprints002) | Roughness breakup: fingerprints |
| [Metal041A](https://ambientcg.com/a/Metal041A) | Aluminium and plain metal |
| [Metal046A](https://ambientcg.com/a/Metal046A) | Crinkle and wrinkle finishes |
| [Metal049A](https://ambientcg.com/a/Metal049A) | Chrome and bright metal |
| [PaintedMetal002](https://ambientcg.com/a/PaintedMetal002) | Enamel panels and cabinets |
| [Paper004](https://ambientcg.com/a/Paper004) | The Teletype's paper |
| [Plastic003](https://ambientcg.com/a/Plastic003) | Gloss plastic |
| [Plastic004](https://ambientcg.com/a/Plastic004) | The Teletype's moulded housing |
| [Plastic006](https://ambientcg.com/a/Plastic006) | Satin plastic |
| [Plastic013B](https://ambientcg.com/a/Plastic013B) | Moulded plastic |
| [Plastic018B](https://ambientcg.com/a/Plastic018B) | Grey plastic panels |
| [Rubber004](https://ambientcg.com/a/Rubber004) | Rubber feet, cables and keys |
| [Smear004](https://ambientcg.com/a/Smear004) | Roughness breakup: smears |

**Baked into the era-2 GLBs.** These were box-projected at real scale (2K
sources) and baked. The source sets are not shipped.
[Plastic012B](https://ambientcg.com/a/Plastic012B),
[Plastic013B](https://ambientcg.com/a/Plastic013B),
[Plastic018B](https://ambientcg.com/a/Plastic018B),
[Rubber004](https://ambientcg.com/a/Rubber004) and
[Fabric082A](https://ambientcg.com/a/Fabric082A) (the desktop speakers'
cloth). All are AmbientCG, CC0 1.0.

## Fonts

No font file is bundled with this pack.

- **Baked labels.** The labels in the era-2 bakes were rasterized in PIL from
  the Windows fonts installed on the authoring machine (Arial, Arial Black,
  Segoe UI, Franklin Gothic, Georgia, Times New Roman, Tahoma, Consolas).
  They are pixels in the textures; no font file is distributed.
- **Runtime labels and screens.** The canvas labels and screens request
  Windows faces through Skia's system font lookup:
  - Bahnschrift and Segoe UI on the era-1 plates;
  - Lucida Console and Consolas on the Teletype paper;
  - Tahoma and Verdana on the Mac and 2001 screens.

  Each request carries a generic fallback. The C64 and the Speak & Spell VFD
  draw their own 8×8 and 14-segment glyphs and need no font.

## Reference photos (provenance only)

The builders compared their renders with these photos while modelling. They
are listed here as provenance. They are **not** in the repository, and
several are copyrighted or under share-alike licences, so do not add them.
Licences are as recorded on each source page when it was consulted.

<!-- REFS:machines -->
| Machine | Reference | Source | Author | Licence |
| --- | --- | --- | --- | --- |
| voder | Voder room at 1939 New York World's Fair | [Commons](https://commons.wikimedia.org/wiki/File:Voder_room_at_1939_New_York_World%27s_Fair.jpg) | Unknown author | Public domain |
| voder | VODER demonstrated on 1939 New York World Fair - The VODER fascinates the crowds - Bell Telephone Quarterly (January 1940) | [Commons](https://commons.wikimedia.org/wiki/File:VODER_demonstrated_on_1939_New_York_World_Fair_-_The_VODER_fascinates_the_crowds_-_Bell_Telephone_Quarterly_(January_1940).jpg) | Internet Archive Book Images | No restrictions |
| voder | Homer Dudley (October 1940). "The Carrier Nature of Speech". Bell System Technical Journal, XIX(4);495-515. -- Fig.5 The voder being demonstrated at the New York World's Fair | [Commons](https://commons.wikimedia.org/wiki/File:Homer_Dudley_(October_1940)._%22The_Carrier_Nature_of_Speech%22._Bell_System_Technical_Journal,_XIX(4);495-515._--_Fig.5_The_voder_being_demonstrated_at_the_New_York_World%27s_Fair.jpg) | Internet Archive Book Images | No restrictions |
| voder | Homer Dudley (October 1940). "The Carrier Nature of Speech". Bell System Technical Journal, XIX(4);495-515. -- Fig.8 Schematic circuit of the voder | [Commons](https://commons.wikimedia.org/wiki/File:Homer_Dudley_(October_1940)._%22The_Carrier_Nature_of_Speech%22._Bell_System_Technical_Journal,_XIX(4);495-515._--_Fig.8_Schematic_circuit_of_the_voder.jpg) | Internet Archive Book Images | No restrictions |
| voder | Bell telephone magazine (1940) (14756325402) | [Commons](https://commons.wikimedia.org/wiki/File:Bell_telephone_magazine_(1940)_(14756325402).jpg) | Internet Archive Book Images | No restrictions |
| voder | Bell telephone magazine (1940) (14733635746) | [Commons](https://commons.wikimedia.org/wiki/File:Bell_telephone_magazine_(1940)_(14733635746).jpg) | Internet Archive Book Images | No restrictions |
| voder | The Voder as demonstrated by Mrs. Harper at The Franklin Institute (J. Franklin Inst. 227(6), 1939), reproduced in Specialty Answering Service white paper The-Voder.pdf | [specialtyansweringservice.net](https://www.specialtyansweringservice.net/wp-content/uploads/resources_papers/what-is-the-voder/The-Voder.pdf) | — | reference only (not distributed) |
| voder | Voder keyboard block diagram (keys 1-10, quiet key, t-d/p-b/k-g stops, wrist bar, foot pedal), same white paper | [specialtyansweringservice.net](https://www.specialtyansweringservice.net/wp-content/uploads/resources_papers/what-is-the-voder/The-Voder.pdf) | — | reference only (not distributed) |
| mainframe | IBM 7090 computer | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7090_computer.jpg) | NASA Ames Research Center / Emerson Shaw | Public domain |
| mainframe | NASAComputerRoom7090.NARA | [Commons](https://commons.wikimedia.org/wiki/File:NASAComputerRoom7090.NARA.jpg) | NASA | Public domain |
| mainframe | IBM 7090 console | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7090_console.jpg) | Bubba73 | CC BY-SA 4.0 |
| mainframe | IBM 7090 console.nasa | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7090_console.nasa.jpg) | NASA | Public domain |
| mainframe | IBM 729 Tape Drives.nasa | [Commons](https://commons.wikimedia.org/wiki/File:IBM_729_Tape_Drives.nasa.jpg) | NASA | Public domain |
| mainframe | IBM 729 tape drives.agr | [Commons](https://commons.wikimedia.org/wiki/File:IBM_729_tape_drives.agr.jpg) | ArnoldReinhold | CC BY-SA 3.0 |
| mainframe | IBM 729 restored | [Commons](https://commons.wikimedia.org/wiki/File:IBM_729_restored.jpg) | Marcin Wichary | CC BY 2.0 |
| mainframe | Ibm-729v | [Commons](https://commons.wikimedia.org/wiki/File:Ibm-729v.jpg) | No machine-readable author provided. T | CC BY-SA 2.5 |
| mainframe | IBM 7090 Computer Data Processing System being Used (23 0003702) | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7090_Computer_Data_Processing_System_being_Used_(23_0003702).jpg) | SDASM Archives | No restrictions |
| mainframe | IBM 7094 console.agr | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7094_console.agr.JPG) | ArnoldReinhold | CC BY-SA 3.0 |
| mainframe | IBM 7070 | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7070.jpg) | — | Public domain |
| mainframe | IBM 7070 at Tokai Bank | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7070_at_Tokai_Bank.jpg) | — | Public domain |
| mainframe | IBM 7044 at NTT Central Statics Institute | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7044_at_NTT_Central_Statics_Institute.jpg) | — | Public domain |
| mainframe | IBM 7080 | [Commons](https://commons.wikimedia.org/wiki/File:IBM_7080.jpg) | — | CC BY-SA 4.0 |
| mainframe | 1960- David Stevens avid Stevens (at the typewriter) and Carol Bruno at an IBM 7040 | [Commons](https://commons.wikimedia.org/wiki/File:1960-_David_Stevens_avid_Stevens_(at_the_typewriter)_and_Carol_Bruno_at_an_IBM_7040.jpg) | — | CC BY 2.0 |
| teletype | ASR-33 at CHM.agr | [Commons](https://commons.wikimedia.org/wiki/File:ASR-33_at_CHM.agr.jpg) | ArnoldReinhold | CC BY-SA 3.0 |
| teletype | Teletype-IMG 7287 | [Commons](https://commons.wikimedia.org/wiki/File:Teletype-IMG_7287.jpg) | Rama & Musée Bolo | CC BY-SA 2.0 fr |
| teletype | ASR-33 1 | [Commons](https://commons.wikimedia.org/wiki/File:ASR-33_1.jpg) | Dominic Alves from Brighton, England | CC BY 2.0 |
| teletype | ASR-33 2 | [Commons](https://commons.wikimedia.org/wiki/File:ASR-33_2.jpg) | Marcin Wichary from San Francisco, U.S.A. | CC BY 2.0 |
| teletype | Teletype Model 33 ASR (1968) (14689737122) | [Commons](https://commons.wikimedia.org/wiki/File:Teletype_Model_33_ASR_(1968)_(14689737122).png) | Dennis van Zuijlekom from Ermelo, The Netherlands | CC BY-SA 2.0 |
| teletype | Teletype asr-33 | [Commons](https://commons.wikimedia.org/wiki/File:Teletype_asr-33.jpg) | Zdekos | CC BY-SA 4.0 |
| teletype | ASR 33 | [Commons](https://commons.wikimedia.org/wiki/File:ASR_33.jpg) | Bubba73 (Jud McCranie) | CC BY-SA 3.0 |
| teletype | Teletype Model 33 (15427779806) | [Commons](https://commons.wikimedia.org/wiki/File:Teletype_Model_33_(15427779806).jpg) | Kai Wegner from Berlin, Deutschland | CC BY 2.0 |
| teletype | ASR-33 Teletype terminal IMG 1658 | [Commons](https://commons.wikimedia.org/wiki/File:ASR-33_Teletype_terminal_IMG_1658.jpg) | Rama & Musée Bolo | CC BY-SA 2.0 fr |
| speakspell | TI SpeakSpell no shadow | [Commons](https://commons.wikimedia.org/wiki/File:TI_SpeakSpell_no_shadow.jpg) | Bill Bertram (edit by Tomhannen) | CC BY-SA 2.5 |
| speakspell | TI SpeakSpell | [Commons](https://commons.wikimedia.org/wiki/File:TI_SpeakSpell.jpg) | Bill Bertram | CC BY-SA 2.5 |
| speakspell | Speak & Spell (original style) | [Commons](https://commons.wikimedia.org/wiki/File:Speak_%26_Spell_(original_style).jpg) | FozzTexx | CC BY-SA 4.0 |
| c64 | Commodore-64-Computer-FL | [Commons](https://commons.wikimedia.org/wiki/File:Commodore-64-Computer-FL.jpg) | Evan-Amos | Public domain |
| c64 | Commodore 1702 (made by JVC) front | [Commons](https://commons.wikimedia.org/wiki/File:Commodore_1702_(made_by_JVC)_front.jpg) | Gona.eu | CC BY-SA 3.0 |
| c64 | Commodore 1702 Video Monitor | [Commons](https://commons.wikimedia.org/wiki/File:Commodore_1702_Video_Monitor.jpg) | shane doucette | CC BY-SA 2.0 |
| c64 | Commodore 64 Pisa computers museum | [Commons](https://commons.wikimedia.org/wiki/File:Commodore_64_Pisa_computers_museum.jpg) | Federigo Federighi | CC BY-SA 4.0 |
| mac1984 | Macintosh 128k transparency | [Commons](https://commons.wikimedia.org/wiki/File:Macintosh_128k_transparency.png) | Grm wnr | CC BY-SA 3.0 |
| mac1984 | Macintosh 128K fronte | [Commons](https://commons.wikimedia.org/wiki/File:Macintosh_128K_fronte.jpg) | Marco Mioli | CC BY-SA 2.5 it |
| mac1984 | Macintosh 128k | [Commons](https://commons.wikimedia.org/wiki/File:Macintosh_128k.jpg) | — | CC BY-SA 3.0 |
| dectalk | DECtalk DCT01 and Tink | [Commons](https://commons.wikimedia.org/wiki/File:DECtalk_DCT01_and_Tink.jpg) | Emgaol | CC BY 3.0 |
| dectalk | DECtalk speech synthesizer, catalogue 102757099 (front) | [computerhistory.org](https://www.computerhistory.org/collections/catalog/102757099) | Computer History Museum | Computer History Museum catalogue image (reference only) |
| dectalk | DECtalk speech synthesizer, catalogue 102757099 (back) | [computerhistory.org](https://www.computerhistory.org/collections/catalog/102757099) | Computer History Museum | Computer History Museum catalogue image (reference only) |
| dectalk | DECtalk speech synthesizer, catalogue 102757099 (bottom) | [computerhistory.org](https://www.computerhistory.org/collections/catalog/102757099) | Computer History Museum | Computer History Museum catalogue image (reference only) |
| desktop2001 | Viglen PC (51332336626) | [Commons](https://commons.wikimedia.org/wiki/File:Viglen_PC_(51332336626).jpg) | Steve Elliott | CC BY-SA 2.0 |
| desktop2001 | Mypc11999 | [Commons](https://commons.wikimedia.org/wiki/File:Mypc11999.jpg) | Oompje | CC BY-SA 4.0 |
| desktop2001 | HP Pavilion v72 17 inch CRT Monitor front view IMG 9419 | [Commons](https://commons.wikimedia.org/wiki/File:HP_Pavilion_v72_17_inch_CRT_Monitor_front_view_IMG_9419.JPG) | Smiller933 | CC BY 3.0 |
| desktop2001 | HP Pavilion v72 17 inch CRT Monitor IMG 9378 | [Commons](https://commons.wikimedia.org/wiki/File:HP_Pavilion_v72_17_inch_CRT_Monitor_IMG_9378.JPG) | Smiller933 | CC BY 3.0 |
| desktop2001 | Trinitron computer-monitor | [Commons](https://commons.wikimedia.org/wiki/File:Trinitron_computer-monitor.jpg) | Daniel Christensen | CC BY 3.0 |
| desktop2001 | Gateway 2000 P5-75 close-up | [Commons](https://commons.wikimedia.org/wiki/File:Gateway_2000_P5-75_close-up.jpg) | phreakindee | CC0 |
| desktop2001 | Dell Dimension 2100 (D2100 3) | [Commons](https://commons.wikimedia.org/wiki/File:Dell_Dimension_2100_(D2100_3).jpg) | The Serial Port | CC BY-SA 4.0 |
| desktop2001 | Compaq Presario 5000 | [Commons](https://commons.wikimedia.org/wiki/File:Compaq_Presario_5000.jpg) | Erickarroqui | CC BY 3.0 |
| desktop2001 | Dell Dimension (243437310) | [Commons](https://commons.wikimedia.org/wiki/File:Dell_Dimension_(243437310).jpg) | Diehl | CC BY 2.0 |
| desktop2001 | Personalcomputer | [Commons](https://commons.wikimedia.org/wiki/File:Personalcomputer.jpg) | Adrian Pingstone / Marcusvox | Public domain |
<!-- /REFS -->
