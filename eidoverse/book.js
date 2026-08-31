// book.js — the video-repo adapters over BookCore (eidoverse/book_core.js).
//
// The rig itself — geometry, skinning, posing, page turning — lives in
// BookCore, engine-agnostic and shared verbatim with eidoverse-worlds. This
// file owns what is specific to THIS repo:
//
//   globalThis.makeBook(gltfOrScene, opts)   measure a book GLB into a spec
//       (the janus asset path — used by work/book_janus). Dimensions and the
//       wrap-U landmark are READ off the asset, never assumed; the returned
//       object keeps the pre-refactor API so existing scenes run unchanged.
//
//   globalThis.makeBookFromSpec(input, opts) build a book from DATA — no GLB.
//       input = {
//         size: { width, height, thickness },    // closed book, metres
//         pages?, openAt?,                       // leaf count / open-at-front
//         cover:  texture | { wrap } | { front, back?, spine?, color? },
//         lining?: texture | color,              // endpaper (plain span!)
//         edges?:  texture | color,              // block cut edges
//         spreads?: [texture|bytes|url ...],     // two-page scans, in order
//       }
//       A full arc-length `wrap` texture is used as-is. Given separate cover
//       images instead, the wrap is COMPOSED onto a canvas at the correct
//       arc-length layout (back | spine | front), so "any front cover jpg"
//       is enough to make a readable book.
//
//   TSL page glow — paper translucency via emissiveNode (plain .emissive
//       scalars do not bind on this NodeMaterial stack), driven by each
//       page's own map so print stays print and stock glows like stock.
//
//   const book = globalThis.makeBook(await loadGLTF(ASSETS.book));
//   book.layFlat();
//   await book.loadSpreads([...bytes]);
//   book.setOpen(1);
//   book.riffle(t, { start: 12, secondsPerPage: 1.2 });
//   // or, discretely: book.setPage(3); book.poseTurn(0.5);

(function () {

    const PAGE_STOCK = [0.88, 0.87, 0.84];

    // Paper-translucency hook: the underside of a lifting page faces away
    // from every light and reads as a hole without it. Emissive from the
    // page's OWN map is the honest proxy; must be emissiveNode on this stack.
    function pageGlowHook(glow) {
        return (mat, tex) => {
            const stock = THREE.vec3(...PAGE_STOCK).mul(glow);
            mat.emissiveNode = tex ? THREE.texture(tex).mul(glow) : stock;
        };
    }

    async function decodeSpreads(list) {
        const out = [];
        for (const b of list) {
            out.push(b?.isTexture ? b
                : await globalThis.loadImageTexture(b, { srgb: true }));
        }
        return out;
    }

    // Shared façade: the pre-refactor surface expected by scenes and probes.
    function facade(rig, { root, part, layFlat, gated }) {
        return {
            root, part,
            setOpen: rig.setOpen,
            setPage: rig.setPage,
            poseTurn: rig.poseTurn,
            riffle: rig.riffle,
            setSpread() { /* stack carries every spread; kept for compat */ },
            async loadSpreads(list) {
                return rig.setSpreadTextures(await decodeSpreads(list));
            },
            update() { /* posed directly from the timeline */ },
            layFlat,
            seatBox: rig.seatBox,
            pageMaterials: rig.pageMaterials,
            edgeMaterial: rig.edgeMaterial,
            codeSurfaces: gated ? (() => (gated() ? rig.codeSurfaces() : false))
                                : rig.codeSurfaces,
            caseMesh: rig.caseMesh, caseBones: rig.caseBones,
            leafField: rig.leafField,   // leaves are GPU-posed now — no per-leaf meshes

            frames: rig.frames, metrics: rig.metrics,
            get spreadCount() { return rig.spreadCount; },
            get openAmount() { return rig.openAmount; },
            get page() { return rig.page; },
            get maxPage() { return rig.maxPage; },
        };
    }

    // ------------------------------------------------------------ GLB path

    globalThis.makeBook = function makeBook(gltfOrScene, opts = {}) {
        const root = gltfOrScene.scene ? gltfOrScene.scene : gltfOrScene;
        root.updateMatrixWorld(true);

        const part = {}, matByName = {};
        root.traverse((o) => {
            if (o.isMesh) {
                const mn = o.material && o.material.name;
                if (mn && !matByName[mn]) matByName[mn] = o.material;
                if (o.name && !part[o.name]) part[o.name] = o;
            }
        });
        root.traverse((o) => {              // named nodes wrapping primitives
            if (o.isMesh || !o.name || part[o.name]) return;
            let f = null; o.traverse((c) => { if (!f && c.isMesh) f = c; });
            if (f) part[o.name] = f;
        });
        for (const n of ['board_front', 'board_back']) {
            if (!part[n]) throw new Error('[makeBook] missing ' + n);
        }

        // ---- measure, never assume ----------------------------------------
        const bbAll = new THREE.Box3().setFromObject(root);
        const bbBack = new THREE.Box3().setFromObject(part.board_back);
        const halfT = Math.max(Math.abs(bbAll.min.z), Math.abs(bbAll.max.z));
        const halfH = Math.max(Math.abs(bbAll.min.y), Math.abs(bbAll.max.y));
        const jointX = -bbBack.min.x;
        const foreX = bbBack.max.x;

        // The spine piece answers two different questions — how far the cloth
        // runs flat past the board (the French groove lip) and how far it then
        // bulges (the round) — and they must not be conflated.
        let lip = 0.005, round = 0.003;
        if (part.spine) {
            const g = part.spine.geometry.attributes.position;
            let maxAll = 0, maxAtEdge = 0;
            for (let i = 0; i < g.count; i++) {
                const cx = -g.getX(i), cz = Math.abs(g.getZ(i));
                if (cx > maxAll) maxAll = cx;
                if (cz > halfT * 0.95 && cx > maxAtEdge) maxAtEdge = cx;
            }
            lip = Math.max(0.0005, maxAtEdge - jointX);
            round = Math.max(0.001, maxAll - maxAtEdge);
        }

        // Wrap-U at the joint: read off the asset's own UVs (recomputing it
        // from lengths is how the spine artwork once came out stretched).
        let uJoint = 0.4573;
        {
            const uv = part.board_back.geometry.attributes.uv;
            if (uv) {
                let m = 0;
                for (let i = 0; i < uv.count; i++) m = Math.max(m, uv.getX(i));
                if (m > 0.2 && m < 0.5) uJoint = m;
            }
        }

        console.log(`[makeBook] case halfT=${halfT.toFixed(4)} halfH=${halfH.toFixed(4)} `
            + `board=${(jointX + foreX).toFixed(4)} joint=${jointX.toFixed(4)} `
            + `lip=${lip.toFixed(4)} round=${round.toFixed(4)} uJoint=${uJoint.toFixed(4)}`);

        const rig = globalThis.BookCore.makeBookRig(THREE, {
            boardLen: jointX + foreX, jointX, foreX,
            halfH, halfT, lip, round, uJoint,
            pages: opts.pages ?? 26,
            openAt: opts.openAt ?? 1,
            angle: opts.angle ?? 180,
            pageAngle: opts.pageAngle ?? 179,
        }, {
            cloth: matByName['case_cloth'] || part.board_front.material,
            lining: matByName['case_inner'],
            edge: matByName['page_edges'],
            spread: matByName['page_spread'],
        }, {
            onPageFace: pageGlowHook(opts.pageGlow ?? 0.55),
            log: (m) => console.log(m),
        });

        // The rig rides inside the GLB root; source pieces stay (scene code
        // measures them to seat the book) but never draw.
        root.add(rig.root);
        const HIDE = ['board_front', 'board_back', 'spine',
                      'block_left', 'block_right', 'page_left', 'page_right'];
        root.traverse((o) => {
            const n = o.name || '';
            if (HIDE.some((h) => n === h || n.startsWith(h + '_'))) {
                o.visible = false;
                o.traverse((c) => { c.visible = false; });
            }
        });

        return facade(rig, {
            root, part,
            layFlat() {
                root.rotation.set(-Math.PI / 2, 0, 0);   // model thickness is +z
                root.updateMatrixWorld(true);
                return root;
            },
            gated: () => (opts.code || globalThis.__CODE_SURFACES),
        });
    };

    // ----------------------------------------------------------- spec path

    function asTexture(v, srgb) {
        if (v?.isTexture) return Promise.resolve(v);
        return globalThis.loadImageTexture(v, { srgb });
    }

    function flatCanvasTexture(color, w = 8, h = 8) {
        const { c, ctx } = globalThis.BookCore.canvas2d(w, h);
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, w, h);
        const t = new THREE.CanvasTexture(c);
        t.colorSpace = THREE.SRGBColorSpace;
        return t;
    }

    // ---- PDF -> lazy spread source (video harness path) --------------------
    // Rasterizes every page ONCE to small PNGs on disk (pymupdf — the same
    // python toolchain the rest of the video pipeline shells to; pdf.js can't
    // paint standard fonts on this deno stack), then composes two pages into
    // a spread canvas ON DEMAND: the rig's virtual window decodes only the
    // spreads around the current opening, whatever the page count.
    const PY_RASTER = `
import sys, pymupdf
doc = pymupdf.open(sys.argv[1])
h = float(sys.argv[3])
for i, page in enumerate(doc):
    z = h / max(1.0, page.rect.height)
    page.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(f"{sys.argv[2]}/p_{i:04d}.png")
print(len(doc))
`;
    async function pdfSpreadSource(pdf, pageH = 1200) {
        const dir = await Deno.makeTempDir({ prefix: 'book_pdf_' });
        // The harness hands scene assets over as raw BYTES (Uint8Array), and
        // a data blob stringified into spawn args is megabytes long — the
        // "filename too long" spawn failure. Land bytes in a file first;
        // multi-line -c scripts also break windows spawn, hence the file.
        let pdfPath = pdf;
        if (pdf instanceof Uint8Array || pdf instanceof ArrayBuffer) {
            pdfPath = `${dir}/src.pdf`;
            await Deno.writeFile(pdfPath,
                pdf instanceof Uint8Array ? pdf : new Uint8Array(pdf));
        }
        const pyFile = `${dir}/raster.py`;
        await Deno.writeTextFile(pyFile, PY_RASTER);
        let py = Deno.env.get('BOOK_PYTHON') ?? null;
        if (!py) {
            for (const cand of ['C:\\Python314\\python.exe', 'C:\\Python313\\python.exe',
                                'C:\\Python312\\python.exe', 'python']) {
                if (cand === 'python') { py = cand; break; }
                try { Deno.statSync(cand); py = cand; break; } catch { /* next */ }
            }
        }
        const out = await new Deno.Command(py, {
            args: [pyFile, pdfPath, dir, String(pageH)],
        }).output();
        if (!out.success)
            throw new Error('[book] pdf rasterize failed: '
                + new TextDecoder().decode(out.stderr).slice(0, 400));
        const nPages = parseInt(new TextDecoder().decode(out.stdout).trim(), 10);
        const count = Math.floor(nPages / 2) + 1;    // spread 0 = blank | page 0
        const pageImg = async (j) => {
            if (j < 0 || j >= nPages) return null;
            const bytes = await Deno.readFile(`${dir}/p_${String(j).padStart(4, '0')}.png`);
            return globalThis.loadCanvasImage(bytes);
        };
        const get = async (i) => {
            const [li, ri] = await Promise.all([pageImg(2 * i - 1), pageImg(2 * i)]);
            const ref = li || ri;
            if (!ref) return null;
            const pw = ref.width, ph = ref.height;
            const { c, ctx } = globalThis.BookCore.canvas2d(pw * 2, ph);
            ctx.fillStyle = '#f4f1e8';
            ctx.fillRect(0, 0, pw * 2, ph);
            if (li) ctx.drawImage(li, 0, 0, pw, ph);
            if (ri) ctx.drawImage(ri, pw, 0, pw, ph);
            const t = new THREE.CanvasTexture(c);
            t.colorSpace = THREE.SRGBColorSpace;
            t.anisotropy = 8;
            return t;
        };
        return { count, get, pages: nPages };
    }

        globalThis.makeBookFromSpec = async function makeBookFromSpec(input, opts = {}) {
        const { openAt = 1 } = input;
        // a PDF loads FIRST so the body can be honest about it: thickness
        // defaults to what that many pages of real paper measures (~0.10mm
        // a LEAF = 0.05mm a page, plus boards) — a 350-pager is a normal
        // ~26mm novel; fat tomes take 1000+ pages. Thickness counts only
        // pages the binding holds (BIND_PAGES) so an over-cap document
        // cannot wear a body its binding doesn't have.
        const BIND_LEAVES = 502;               // binds a full 1000-page doc
        const BIND_PAGES = (BIND_LEAVES - 2) * 2;
        let pdfSource = null;
        if (input.pdf) pdfSource = await pdfSpreadSource(input.pdf, input.pdfPageHeight ?? 1200);
        const size = {
            width: input.size?.width ?? 0.14,
            height: input.size?.height ?? 0.2,
            thickness: input.size?.thickness
                ?? (pdfSource ? Math.min(0.08, Math.max(0.012, 0.008 + Math.min(pdfSource.pages, BIND_PAGES) * 0.00005))
                : input.spreads?.length
                    ? Math.min(0.08, Math.max(0.01, 0.008 + input.spreads.length * 2 * 0.00005))
                    : null),
        };
        if (!size.width || !size.height || !size.thickness)
            throw new Error('[makeBookFromSpec] size {width, height, thickness} required');
const pages = input.pages
            ?? (pdfSource ? Math.max(12, Math.min(BIND_LEAVES, Math.ceil(pdfSource.pages / 2) + 2))
            : input.spreads?.length ? input.spreads.length + 1 : 26);

        const boardTh = input.boardTh ?? 0.0025;
        const lip = input.lip ?? Math.max(0.003, size.thickness * 0.21);
        const round = input.round ?? Math.max(0.0015, size.thickness * 0.09);
        const halfT = size.thickness / 2;
        const halfH = size.height / 2;
        const boardLen = size.width;

        const uJoint = input.uJoint
            ?? globalThis.BookCore.solveWrapLayout({ boardLen, lip, round, halfT });

        // ---- materials ------------------------------------------------------
        const Mat = THREE.MeshStandardNodeMaterial || THREE.MeshStandardMaterial;
        const mat = (o) => Object.assign(new Mat(), o);

        let clothTex;
        const cover = input.cover || {};
        if (cover.isTexture) clothTex = cover;
        else if (cover.wrap) clothTex = await asTexture(cover.wrap, true);
        else if (cover.front || cover.back || cover.color)
            clothTex = await globalThis.BookCore.composeWrapTexture(THREE, cover, uJoint);
        else clothTex = flatCanvasTexture('#8a1420');

        const liningTex = input.lining?.isTexture ? input.lining
            : input.lining && typeof input.lining !== 'string' ? await asTexture(input.lining, true)
            : flatCanvasTexture(typeof input.lining === 'string' ? input.lining : '#efe9dc');
        const edgeTex = input.edges?.isTexture ? input.edges
            : input.edges && typeof input.edges !== 'string' ? await asTexture(input.edges, true)
            : flatCanvasTexture(typeof input.edges === 'string' ? input.edges : '#ddd8ca');

        // Trim: the plain bookcloth on rims and turn-ins. A composed wrap has
        // no plain region to sample (back-cover art sits there), so trim is
        // its own texture — the user's, or flat cloth from cover.color.
        const trimTex = cover.trim ? await asTexture(cover.trim, true)
            : flatCanvasTexture(cover.color || '#8a1420');
        const materials = {
            cloth: mat({ map: clothTex, roughness: 0.88, name: 'case_cloth' }),
            lining: mat({ map: liningTex, roughness: 0.94, name: 'case_inner' }),
            edge: mat({ map: edgeTex, roughness: 0.92, name: 'page_edges' }),
            spread: mat({ roughness: 0.9, name: 'page_spread' }),
            trim: mat({ map: trimTex, roughness: 0.9, name: 'case_trim' }),
        };

        const rig = globalThis.BookCore.makeBookRig(THREE, {
            boardLen, halfH, halfT, boardTh, lip, round, uJoint,
            liningFit: true,
            pages, openAt,
            angle: opts.angle ?? 180, pageAngle: opts.pageAngle ?? 179,
        }, materials, {
            onPageFace: pageGlowHook(opts.pageGlow ?? 0.55),
            log: (m) => console.log(m),
        });

        const book = facade(rig, {
            root: rig.root, part: {},
            layFlat: rig.layFlat,
            gated: () => (opts.code || globalThis.__CODE_SURFACES),
        });
        if (pdfSource) rig.setSpreadSource(pdfSource);
        else if (input.spreads?.length) await book.loadSpreads(input.spreads);
        return book;
    };
})();
