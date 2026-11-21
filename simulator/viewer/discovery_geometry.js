// Original close-up field-guide subjects, in metres, with +Y pointing away from the host surface.
// Each recipe produces one indexed, vertex-coloured mesh. Relief and broken edges catch the vehicle lamps.
import * as THREE from 'three';

const TAU = Math.PI * 2;
const UP = new THREE.Vector3(0, 1, 0);
const EAST = new THREE.Vector3(1, 0, 0);

class Surface {
  positions = [];
  colours = [];
  triangles = [];
  tint = new THREE.Color();

  constructor(coarse) {
    this.coarse = coarse;
  }

  vertex(x, y, z, colour, value = 1) {
    const tint = this.tint.setHex(colour);
    this.colours.push(tint.r * value, tint.g * value, tint.b * value);
    this.positions.push(x, y, z);
  }

  // Join cross-sections winding around a shell, arm or strand. Closing rows contract to a small tip.
  rings(rows, sides, draw) {
    const start = this.positions.length / 3;
    // The far silhouette keeps both ends of every tube and at least five vertices around each section.
    const rowStep = this.coarse && rows > 3 ? 2 : 1;
    const width = this.coarse ? Math.min(6, sides) : sides;
    const height = Math.ceil((rows - 1) / rowStep) + 1;
    for (let row = 0; row < height; row++) {
      for (let col = 0; col < width; col++) {
        const k = Math.floor(col * sides / width);
        draw(Math.min(row * rowStep, rows - 1), k, TAU * k / sides);
        if (row + 1 === height) continue;
        const a = start + row * width + col;
        const b = start + row * width + (col + 1) % width;
        this.triangles.push(a, a + width, b, b, a + width, b + width);
      }
    }
  }

  finish() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(this.positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(this.colours, 3));
    // Planar grain in metres, angled slightly off the attachment plane so it continues up the edges.
    const uv = [];
    for (let i = 0; i < this.positions.length; i += 3) {
      const x = this.positions[i];
      const y = this.positions[i + 1];
      const z = this.positions[i + 2];
      uv.push((x + .38 * y) * 8, (z - .24 * y) * 8);
    }
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geometry.setIndex(this.triangles);
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    return geometry;
  }
}

// Elliptical sections. Each row can shift the centre to form a hinge or an off-centre shell apex.
function shell(surface, x, z, angle, rows, sides, rib = 0, taper = 0) {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  surface.rings(rows.length, sides, function section(i, k, a) {
    const [rx, rz, y, colour, offset = 0] = rows[i];
    const u = rx * Math.cos(a) * (1 + rib * (k % 2)) + offset;
    const v = rz * Math.sin(a) * (1 + rib * (k % 2)) * (1 - taper * Math.cos(a));
    surface.vertex(x + c * u - s * v, y, z + s * u + c * v, colour, .84 + .16 * (k % 2));
  });
}

// Open-ended tapered tubes. The frame uses the surface normal for horizontal limbs.
function strand(surface, path, radii, colours, sides = 5) {
  const points = path.map(p => new THREE.Vector3(...p));
  const tangent = new THREE.Vector3();
  const side = new THREE.Vector3();
  const across = new THREE.Vector3();
  surface.rings(path.length, sides, function segment(i, k, a) {
    if (!k) {
      tangent.subVectors(points[Math.min(points.length - 1, i + 1)], points[Math.max(0, i - 1)]).normalize();
      side.crossVectors(tangent, Math.abs(tangent.y) > .92 ? EAST : UP).normalize();
      across.crossVectors(side, tangent);
    }
    const p = points[i];
    const u = radii[i] * Math.cos(a);
    const v = radii[i] * Math.sin(a);
    surface.vertex(p.x + u * side.x + v * across.x, p.y + u * side.y + v * across.y,
      p.z + u * side.z + v * across.z, colours[i % colours.length], .88 + .12 * (k % 2));
  });
}

function shellBed(surface, kind) {
  const count = {mussels: 15, limpet: 5, barnacles: 14, shell_hash: 12}[kind];
  const step = surface.coarse && count > 6 ? 3 : 1;
  for (let i = 0; i < count; i += step) {
    const a = i * 2.4;
    const radius = Math.sqrt(i) * .036;
    const x = radius * Math.cos(a);
    const z = radius * Math.sin(a) * .79;
    const size = .035 + .013 * Math.sin(a + 1);
    if (kind === 'barnacles') {
      const r = size * .49;
      shell(surface, x, z, a, [
        [r, r, .001, 0x827965], [r * .65, r * .62, r, 0xd2c6a1],
        [r * .28, r * .36, r * .95, 0xb8b095], [r * .24, r * .29, r * .56, 0x514d43],
        [0, 0, r * .55, 0x514d43],
      ], 12, .16);
    } else if (kind === 'mussels') {
      // Overlapping valves favour a common axis. Their narrow byssal ends wedge under neighbouring shells.
      const yaw = .48 * Math.sin(3.1 * i) + .88 * Math.sin(.52 * i + .6);
      shell(surface, x * .85 + .012 * Math.sin(i * 1.9), z * 1.22, yaw, [
        [size, size * .44, .002, 0x363942], [size * .98, size * .42, .006, 0x878676],
        [size * .94, size * .37, .013, 0x5b5e6b], [size * .76, size * .32, .018, 0x505b66, size * .11],
        [size * .5, size * .22, .026, 0x3d4a53, size * .26], [0, 0, .03, 0xa89571, size * .56],
      ], 12, 0, .35);
    } else if (kind === 'shell_hash') {
      // Empty, ribbed valves opened flat at different angles. The narrow hinge is at local -X.
      surface.rings(5, 24, function valve(row, k, t) {
        const u = [1, 1, .76, .42, .003][row];
        const flute = .5 + .5 * Math.cos(8 * t);
        const dx = size * u * Math.cos(t) * (1 + .04 * flute) + size * .48 * (u - 1);
        const dz = size * u * Math.sin(t) * (.64 + .27 * Math.cos(t));
        const height = row ? .002 + .012 * u * u + .003 * u * flute : .002;
        surface.vertex(x + dx * Math.cos(a) - dz * Math.sin(a), height, z + dx * Math.sin(a) + dz * Math.cos(a),
          row ? 0xd7c6a9 : 0xa18d78, .7 + .27 * flute);
      });
    } else {
      const r = size;
      shell(surface, x, z, a, [
        [r, r * .75, .003, 0x948671], [r * .97, r * .73, .006, 0x8d8b76],
        [r * .52, r * .45, .021, 0xbeb097, r * .16],
        [0, 0, .031, 0xccc4aa, r * .32],
      ], 18, .13);
    }
  }
}

function anemones(surface) {
  for (const [x, z, r] of [[-.076, -.012, .044], [.019, .046, .034], [.093, -.042, .041]]) {
    shell(surface, x, z, 0, [[r, r, .001, 0x884540], [r * .66, r * .66, .033, 0xb26052],
      [r * .9, r * .9, .04, 0xc78c60], [0, 0, .039, 0x703e35]], 12);
    for (let i = 0; i < 14; i += surface.coarse ? 2 : 1) {
      const a = i * TAU / 14;
      const c = Math.cos(a);
      const s = Math.sin(a);
      const h = .057 + .01 * Math.sin(i * 4);
      strand(surface, [[x + r * .62 * c, .034, z + r * .62 * s], [x + r * c, .054, z + r * s],
        [x + r * 1.21 * c, h, z + r * 1.21 * s]], [.0058, .0039, .001], [0xba775b, 0xd79d76, 0xd6b598]);
    }
  }
}

function brittleStar(surface) {
  shell(surface, 0, 0, 0, [[.029, .028, .003, 0x8b5340], [.028, .027, .013, 0xcb9472],
    [0, 0, .017, 0xa4694e]], 10, .1);
  for (let arm = 0; arm < 5; arm++) {
    const path = [];
    const radii = [];
    for (let i = 0; i <= 10; i++) {
      const u = i / 10;
      const a = arm * TAU / 5 + .5 * Math.sin(3.8 * u + arm) * u;
      const r = .022 + .142 * u;
      path.push([Math.cos(a) * r, .008 + .005 * Math.sin(u * Math.PI), Math.sin(a) * r]);
      radii.push(.0084 - .0076 * u);
    }
    strand(surface, path, radii, [0xb47156, 0xd9a57f, 0x8e5542]);
  }
}

function crabMolt(surface) {
  shell(surface, 0, 0, 0, [[.065, .046, .006, 0xa59876], [.063, .042, .02, 0xd4b693],
    [0, 0, .031, 0xab9675]], 16, .07);
  for (const s of [-1, 1]) {
    for (let i = 0; i < 4; i++) {
      const z = -.036 + i * .022;
      const r = .11 + .028 * Math.sin((i + .2) / 4 * Math.PI);
      strand(surface, [[.041 * s, .013, z], [r * .75 * s, .028, z * 1.7], [r * s, .005, z * 2 - .012]],
        [.008, .005, .001], [0xaa9675, 0xcab593, 0xdacfad]);
    }
    strand(surface, [[.039 * s, .013, .033], [.066 * s, .019, .064], [.048 * s, .021, .085],
      [.03 * s, .013, .101]], [.009, .009, .015, .001], [0xb5a083, 0xd2ba95]);
    strand(surface, [[.048 * s, .021, .085], [.025 * s, .012, .086]], [.007, .001], [0xd4bea1]);
  }
}

function ropeOffcut(surface) {
  for (let ply = 0; ply < 3; ply++) {
    const path = [];
    for (let i = 0; i <= 32; i++) {
      const u = i / 32;
      const a = u * 24 + TAU * ply / 3;
      const fringe = u > .85 ? 1 + (u - .85) * 18 : 1;
      path.push([.4 * (u - .5), .012 + .004 * Math.cos(a),
        .048 * Math.sin(u * 5.5) + fringe * .005 * Math.sin(a)]);
    }
    strand(surface, path, path.map(() => .0055), [0x978967, 0x8c8064, 0xae9b72]);
  }
}

function shackle(surface) {
  const path = [[-.035, .01, -.065], [-.035, .012, -.037]];
  for (let i = 0; i <= 12; i++) {
    const a = i * Math.PI / 12;
    path.push([-.06 * Math.cos(a), .013, .012 + .062 * Math.sin(a)]);
  }
  path.push([.035, .012, -.037], [.035, .01, -.065]);
  strand(surface, path, path.map(() => .0095), [0x665851, 0x8c7867, 0x685d4e], 8);
  strand(surface, [[-.054, .014, -.056], [-.044, .014, -.056], [.047, .014, -.056], [.052, .014, -.056]],
    [.015, .008, .008, .009], [0xa18367, 0x716c64, 0x827c72], 8);
}

function netPatch(surface) {
  // A folded corner of seine mesh, the knot crossings follow the same sagged surface.
  function knot(u, v) {
    const twist = .035 * Math.sin(4.2 * u + 1.5 * v);
    return [(u + v - 1) * .235 + twist, .004 + .045 * u * v * v,
      (u - v) * .162 + .04 * Math.sin(4 * u + 1.3 * v)];
  }
  for (let j = 0; j <= 6; j++) {
    const u = j / 6;
    for (const warp of [true, false]) {
      const path = [];
      const end = j > 3 && warp ? 4 + j % 3 : 6;
      for (let i = 0; i <= end; i++) path.push(warp ? knot(u, i / 6) : knot(i / 6, u));
      const hem = j === 0 && warp;
      strand(surface, path, path.map(() => hem ? .006 : .0027), [hem ? 0x927f5d : 0x5e6960]);
    }
  }
}

function bottleGlass(surface) {
  // Horizontal chipped lip and tapered shoulder. A dull green inner wall makes the open neck readable.
  const rings = [[-.11, .039], [-.038, .038], [.003, .023], [.025, .015],
    [.073, .015], [.075, .02], [.089, .019], [.089, .012], [.045, .011]];
  surface.rings(rings.length, 16, function neck(i, k, a) {
    const [axial, r] = rings[i];
    const chip = i === 0 ? .021 * Math.sin(k * 3.8) : 0;
    surface.vertex(axial + chip, .036 + r * Math.sin(a), r * Math.cos(a),
      i > 6 ? 0x355d53 : i > 4 || i === 0 ? 0x789c82 : 0x536f5d, .84 + .16 * Math.cos(a));
  });
}

function shards(surface, ceramic) {
  const outline = ceramic ? [[-.12,-.056],[-.089,-.084],[.047,-.073],[.105,.009],[.069,.066],[-.044,.083]]
    : [[-.137,-.024],[-.127,-.067],[-.086,-.053],[-.054,-.078],[.064,-.046],[.151,.018],
      [.089,.039],[.056,.075],[.017,.054],[-.092,.065]];
  surface.rings(6, outline.length, function shard(i, k) {
    const [x, z] = outline[k];
    const f = [1, 1, .985, .78, .74, .001][i];
    const height = ceramic ? .009 * (1 + Math.sin(k)) : .004 + .015 * (k === 0);
    const clay = [0x94765d, 0xbda987, 0xd6c9ae, 0xcabea7, 0x929e99, 0xe2d2b4];
    const iron = [0x564432, 0xb06c42, 0x905737, 0x965b37, 0x8c6548, 0x70513a];
    surface.vertex(x * f, i === 0 ? .001 : .007 + f * height, z * f, (ceramic ? clay : iron)[i],
      .82 + .18 * Math.sin(k * 1.8) ** 2);
  });
}

const recipes = {
  mussels: s => shellBed(s, 'mussels'),
  barnacles: s => shellBed(s, 'barnacles'),
  limpet: s => shellBed(s, 'limpet'),
  shell_hash: s => shellBed(s, 'shell_hash'),
  anemones,
  brittle_star: brittleStar,
  crab_molt: crabMolt,
  rope_offcut: ropeOffcut,
  shackle,
  bottle_glass: bottleGlass,
  net_patch: netPatch,
  ceramic_shard: s => shards(s, true),
  rust_flake: s => shards(s, false),
};

export function discoveryGeometry(kind, coarse = false) {
  const recipe = recipes[kind];
  if (!recipe) return null;
  const surface = new Surface(coarse);
  recipe(surface);
  return surface.finish();
}
