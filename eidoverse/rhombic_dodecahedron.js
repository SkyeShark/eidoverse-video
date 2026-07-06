/**
 * Rhombic Dodecahedron voxel system for three.js scenes.
 *
 * Rhombic dodecahedra are 12-faced polyhedra that tile 3D space perfectly
 * (like cubes, but with an organic crystalline look). Uses FCC lattice packing.
 *
 * Usage in render_scene.mjs scene scripts:
 *
 *   // Create geometry for a single cell
 *   const rdGeo = createRhombicDodecahedron(0.5);  // radius 0.5
 *
 *   // Fill a box volume with RD voxels (returns InstancedMesh)
 *   const crystal = fillVolumeRD({
 *       bounds: { x: [-3, 3], y: [0, 4], z: [-3, 3] },
 *       cellSize: 0.5,
 *       material: new THREE.MeshStandardMaterial({ color: 0xff2d95 }),
 *   });
 *   scene.add(crystal);
 *
 *   // Fill a sphere volume
 *   const orb = fillSphereRD({
 *       center: [0, 2, 0], radius: 3, cellSize: 0.4,
 *       material: new THREE.MeshStandardMaterial({ color: 0x00d4ff, metalness: 0.8 }),
 *   });
 *   scene.add(orb);
 *
 *   // Voxelize an existing mesh into RD cells
 *   const voxelized = voxelizeMeshRD({
 *       mesh: someLoadedModel,
 *       cellSize: 0.3,
 *       material: new THREE.MeshStandardMaterial({ color: 0xffaa00 }),
 *   });
 *   scene.add(voxelized);
 *
 *   // Animate: dissolve/materialize by toggling instance visibility
 *   // In renderFrame(t):
 *   const im = crystal;  // the InstancedMesh
 *   const dummy = new THREE.Object3D();
 *   for (let i = 0; i < im.count; i++) {
 *       im.getMatrixAt(i, dummy.matrix);
 *       dummy.matrix.decompose(dummy.position, dummy.quaternion, dummy.scale);
 *       // Show cells based on distance from center + time
 *       const dist = dummy.position.length();
 *       const show = dist < t * 3;  // expanding sphere reveal
 *       dummy.scale.setScalar(show ? 1 : 0.001);
 *       dummy.updateMatrix();
 *       im.setMatrixAt(i, dummy.matrix);
 *   }
 *   im.instanceMatrix.needsUpdate = true;
 */

(function() {
    'use strict';

    // ========== GEOMETRY ==========

    // Rhombic dodecahedron vertices:
    // 8 "cube" vertices at (±1, ±1, ±1)
    // 6 "octahedron" vertices at (±2, 0, 0), (0, ±2, 0), (0, 0, ±2)
    const _cubeVerts = [
        [ 1,  1,  1], [ 1,  1, -1], [ 1, -1,  1], [ 1, -1, -1],
        [-1,  1,  1], [-1,  1, -1], [-1, -1,  1], [-1, -1, -1],
    ];
    const _octVerts = [
        [ 2,  0,  0], [-2,  0,  0],
        [ 0,  2,  0], [ 0, -2,  0],
        [ 0,  0,  2], [ 0,  0, -2],
    ];
    const _allVerts = [..._cubeVerts, ..._octVerts];

    // 12 rhombic faces, each defined by 4 vertex indices (ordered for correct winding)
    // Each face connects 2 cube vertices and 2 octahedron vertices
    const _faces = [
        [8, 0, 10, 1],   // +x, +y
        [8, 1, 11, 3],   // +x, -y (front-ish)
        [8, 2, 10, 0],   // +x, +y (other side)...

        // Let me use a more systematic approach
        // Face: oct_a, cube_a, oct_b, cube_b (alternating oct/cube around the rhombus)
    ];

    // Systematic face generation: each face shares an edge between
    // one octahedron vertex and two adjacent cube vertices
    // There are 12 faces. Let's enumerate them properly.
    function _buildFaces() {
        // Each face of the RD connects 2 oct verts and 2 cube verts.
        // For each pair of adjacent oct verts (sharing cube verts), we get a face.
        // Easier: enumerate all 12 faces explicitly.
        // Indices: cube verts 0-7, oct verts 8-13
        // oct 8 = (+2,0,0), 9 = (-2,0,0), 10 = (0,+2,0), 11 = (0,-2,0), 12 = (0,0,+2), 13 = (0,0,-2)
        // cube 0=(+,+,+), 1=(+,+,-), 2=(+,-,+), 3=(+,-,-), 4=(-,+,+), 5=(-,+,-), 6=(-,-,+), 7=(-,-,-)
        return [
            // +x faces (oct 8 = +2,0,0)
            [8, 0, 10, 1],  // +x +y: (2,0,0)-(1,1,1)-(0,2,0)-(1,1,-1)
            [8, 2, 12, 0],  // +x +z: (2,0,0)-(1,-1,1)-(0,0,2)-(1,1,1)
            [8, 3, 11, 2],  // +x -y: (2,0,0)-(1,-1,-1)-(0,-2,0)-(1,-1,1)
            [8, 1, 13, 3],  // +x -z: (2,0,0)-(1,1,-1)-(0,0,-2)-(1,-1,-1)
            // -x faces (oct 9 = -2,0,0)
            [9, 4, 10, 5],  // -x +y: (-2,0,0)-(-1,1,1)-(0,2,0)-(-1,1,-1)
            [9, 6, 12, 4],  // -x +z: (-2,0,0)-(-1,-1,1)-(0,0,2)-(-1,1,1)
            [9, 7, 11, 6],  // -x -y: (-2,0,0)-(-1,-1,-1)-(0,-2,0)-(-1,-1,1)
            [9, 5, 13, 7],  // -x -z: (-2,0,0)-(-1,1,-1)-(0,0,-2)-(-1,-1,-1)
            // remaining 4 faces connecting +y/-y to +z/-z
            [10, 0, 12, 4], // +y +z: (0,2,0)-(1,1,1)-(0,0,2)-(-1,1,1)
            [10, 5, 13, 1], // +y -z: (0,2,0)-(-1,1,-1)-(0,0,-2)-(1,1,-1)
            [11, 2, 12, 6], // -y +z: (0,-2,0)-(1,-1,1)-(0,0,2)-(-1,-1,1)
            [11, 7, 13, 3], // -y -z: (0,-2,0)-(-1,-1,-1)-(0,0,-2)-(1,-1,-1)
        ];
    }

    /**
     * Create a THREE.BufferGeometry for a rhombic dodecahedron.
     * @param {number} radius - Distance from center to face center (default 1)
     * @returns {THREE.BufferGeometry}
     */
    window.createRhombicDodecahedron = function(radius) {
        if (!radius) radius = 1;
        const scale = radius / 2;  // normalize so face-center distance = radius

        const faces = _buildFaces();
        const positions = [];
        const normals = [];

        for (const [a, b, c, d] of faces) {
            const va = _allVerts[a].map(v => v * scale);
            const vb = _allVerts[b].map(v => v * scale);
            const vc = _allVerts[c].map(v => v * scale);
            const vd = _allVerts[d].map(v => v * scale);

            // Compute face normal
            const e1 = [vc[0]-va[0], vc[1]-va[1], vc[2]-va[2]];
            const e2 = [vb[0]-va[0], vb[1]-va[1], vb[2]-va[2]];
            const nx = e1[1]*e2[2] - e1[2]*e2[1];
            const ny = e1[2]*e2[0] - e1[0]*e2[2];
            const nz = e1[0]*e2[1] - e1[1]*e2[0];
            const nl = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
            const n = [nx/nl, ny/nl, nz/nl];

            // Make sure normal points outward (dot with face center should be positive)
            const center = [(va[0]+vb[0]+vc[0]+vd[0])/4,
                           (va[1]+vb[1]+vc[1]+vd[1])/4,
                           (va[2]+vb[2]+vc[2]+vd[2])/4];
            if (center[0]*n[0] + center[1]*n[1] + center[2]*n[2] < 0) {
                n[0] = -n[0]; n[1] = -n[1]; n[2] = -n[2];
            }

            // Two triangles: a-b-c and a-c-d
            positions.push(...va, ...vb, ...vc);
            positions.push(...va, ...vc, ...vd);
            normals.push(...n, ...n, ...n);
            normals.push(...n, ...n, ...n);
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
        return geo;
    };

    // ========== FCC LATTICE ==========

    // Generate FCC lattice points within bounds.
    // FCC: positions where (i+j+k) is even, scaled by cellSize.
    function _fccLattice(bounds, cellSize) {
        const points = [];
        const [xMin, xMax] = bounds.x;
        const [yMin, yMax] = bounds.y;
        const [zMin, zMax] = bounds.z;
        const step = cellSize * 2;  // lattice spacing

        for (let x = xMin; x <= xMax; x += cellSize) {
            for (let y = yMin; y <= yMax; y += cellSize) {
                for (let z = zMin; z <= zMax; z += cellSize) {
                    // FCC condition: round to nearest lattice point
                    const i = Math.round(x / cellSize);
                    const j = Math.round(y / cellSize);
                    const k = Math.round(z / cellSize);
                    if ((i + j + k) % 2 === 0) {
                        points.push([i * cellSize, j * cellSize, k * cellSize]);
                    }
                }
            }
        }
        return points;
    }

    /**
     * Fill a box volume with rhombic dodecahedron voxels.
     * @param {object} opts
     * @param {object} opts.bounds - { x: [min, max], y: [min, max], z: [min, max] }
     * @param {number} opts.cellSize - Size of each cell (default 0.5)
     * @param {THREE.Material} opts.material
     * @returns {THREE.InstancedMesh}
     */
    window.fillVolumeRD = function(opts) {
        const cellSize = opts.cellSize || 0.5;
        const points = _fccLattice(opts.bounds, cellSize);
        const geo = window.createRhombicDodecahedron(cellSize * 0.5);
        const mesh = new THREE.InstancedMesh(geo, opts.material, points.length);
        const dummy = new THREE.Object3D();

        for (let i = 0; i < points.length; i++) {
            dummy.position.set(points[i][0], points[i][1], points[i][2]);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh._rdPoints = points;  // store for animation access
        mesh._rdCellSize = cellSize;
        return mesh;
    };

    /**
     * Fill a sphere volume with rhombic dodecahedron voxels.
     * @param {object} opts
     * @param {number[]} opts.center - [x, y, z] (default [0,0,0])
     * @param {number} opts.radius - Sphere radius
     * @param {number} opts.cellSize - Size of each cell (default 0.5)
     * @param {THREE.Material} opts.material
     * @returns {THREE.InstancedMesh}
     */
    window.fillSphereRD = function(opts) {
        const cellSize = opts.cellSize || 0.5;
        const cx = (opts.center && opts.center[0]) || 0;
        const cy = (opts.center && opts.center[1]) || 0;
        const cz = (opts.center && opts.center[2]) || 0;
        const r = opts.radius || 3;
        const bounds = {
            x: [cx - r, cx + r],
            y: [cy - r, cy + r],
            z: [cz - r, cz + r],
        };
        const allPoints = _fccLattice(bounds, cellSize);
        const r2 = r * r;
        const points = allPoints.filter(p => {
            const dx = p[0] - cx, dy = p[1] - cy, dz = p[2] - cz;
            return dx*dx + dy*dy + dz*dz <= r2;
        });

        const geo = window.createRhombicDodecahedron(cellSize * 0.5);
        const mesh = new THREE.InstancedMesh(geo, opts.material, points.length);
        const dummy = new THREE.Object3D();

        for (let i = 0; i < points.length; i++) {
            dummy.position.set(points[i][0], points[i][1], points[i][2]);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh._rdPoints = points;
        mesh._rdCellSize = cellSize;
        return mesh;
    };

    /**
     * Voxelize an existing 3D object into rhombic dodecahedron cells.
     * Samples the object's bounding box and keeps cells whose center is inside the mesh.
     * @param {object} opts
     * @param {THREE.Object3D} opts.mesh - The source object to voxelize
     * @param {number} opts.cellSize - Size of each cell (default 0.3)
     * @param {THREE.Material} opts.material
     * @param {number} opts.padding - Extra padding around bounding box (default 0)
     * @returns {THREE.InstancedMesh}
     */
    window.voxelizeMeshRD = function(opts) {
        const cellSize = opts.cellSize || 0.3;
        const padding = opts.padding || 0;
        const source = opts.mesh;

        source.updateMatrixWorld(true);
        const box = new THREE.Box3().setFromObject(source);
        const bounds = {
            x: [box.min.x - padding, box.max.x + padding],
            y: [box.min.y - padding, box.max.y + padding],
            z: [box.min.z - padding, box.max.z + padding],
        };

        // Collect triangles for raycasting
        const raycaster = new THREE.Raycaster();
        const allPoints = _fccLattice(bounds, cellSize);

        // Test each point: cast ray downward, count intersections (odd = inside)
        const points = [];
        for (const p of allPoints) {
            raycaster.set(
                new THREE.Vector3(p[0], p[1], p[2]),
                new THREE.Vector3(0, 1, 0)  // ray direction
            );
            const hits = raycaster.intersectObject(source, true);
            if (hits.length % 2 === 1) {
                points.push(p);  // odd number of intersections = inside
            }
        }

        // Fallback: if raycasting found nothing (non-watertight mesh), use distance to nearest surface
        if (points.length === 0) {
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            for (const p of allPoints) {
                const dx = (p[0] - center.x) / (size.x/2 || 1);
                const dy = (p[1] - center.y) / (size.y/2 || 1);
                const dz = (p[2] - center.z) / (size.z/2 || 1);
                if (dx*dx + dy*dy + dz*dz <= 1.1) {
                    points.push(p);
                }
            }
        }

        const geo = window.createRhombicDodecahedron(cellSize * 0.5);
        const mesh = new THREE.InstancedMesh(geo, opts.material, points.length);
        const dummy = new THREE.Object3D();

        for (let i = 0; i < points.length; i++) {
            dummy.position.set(points[i][0], points[i][1], points[i][2]);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh._rdPoints = points;
        mesh._rdCellSize = cellSize;
        return mesh;
    };

    console.log('[rhombic_dodecahedron] Loaded: createRhombicDodecahedron, fillVolumeRD, fillSphereRD, voxelizeMeshRD');
})();
