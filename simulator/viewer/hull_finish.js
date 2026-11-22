// Original antifouling paint wear, plate joints and the seawater intake face on a cargo hull.
// The strainer is an opaque flush insert in the collision surface. Each slot is too small for the vehicle.
export function drawHullPlating(g, size) {
  const image = g.createImageData(size, size);
  let seed = 3706;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const grain = seed / 0xffffffff;
      const u = x / size * Math.PI * 2;
      const v = y / size * Math.PI * 2;
      const mottling = .55 * Math.cos(2 * v + .8 * Math.sin(u)) + .45 * Math.sin(3 * u + v + Math.sin(5 * v));
      const scuffed = mottling * 39 + 14 * grain;
      // Alternate butt joints on adjacent strakes. A dark weld toe and a narrow raised bead catch the lamp.
      const butt = (x + (y < size / 2 ? 0 : size / 2)) % size;
      const seam = Math.min(butt, y % (size / 2));
      let value = 191 + scuffed + (y < size / 2 ? 9 : 0);
      if (seam < 2 || butt >= size - 1) value = 88 + 28 * grain;
      else if (seam < 3) value = 220 + 25 * grain;
      const offset = 4 * (y * size + x);
      image.data[offset] = value;
      image.data[offset + 1] = value - 3;
      image.data[offset + 2] = value - 9;
      image.data[offset + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
}

// Underwater survey frame numbers run from the after perpendicular along the two sides of the docking strip.
// One 4 × 4 transparent paint atlas lets both runs share a single mesh and material.
export function drawKeelFrames(g, size) {
  const cell = size / 4;
  g.fillStyle = '#e6e2c4';
  g.font = 'bold 32px sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  for (let i = 0; i < 16; i++) {
    const x = (i % 4) * cell;
    const y = Math.floor(i / 4) * cell;
    // Transverse ticks mark the frame and the rectangle below gives the pilot its frame number.
    g.fillRect(x + 4, y + 6, cell - 8, 4);
    g.fillRect(x + cell / 2 - 2, y + 5, 4, 11);
    g.fillText(String((i + 1) * 10), x + cell / 2, y + .57 * cell, cell - 7);
    g.fillRect(x + 4, y + cell - 13, 3, 7);
    g.fillRect(x + 4, y + cell - 9, 13, 3);
  }
  // Missing flakes expose the hull through the stencilled paint.
  for (let i = 0; i < 420; i++) g.clearRect(i * 131 % size, (i * 47 + Math.floor(i / 5) * 109) % size, 1, 2);
}

// Timber keel blocks mask the old antifouling coat wherever the hull sat during its last dry-docking.
export function drawBlockPrint(g, size) {
  const image = g.createImageData(size, size);
  let seed = 91335;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const grain = seed / 0xffffffff;
      const edge = Math.min(x, size - x - 1, y, size - y - 1);
      const scuff = Math.sin(.039 * x + .014 * y) + .5 * Math.cos(.14 * x - .026 * y);
      const bare = edge < 6 + 3.4 * scuff || scuff > .96;
      const value = (bare ? 193 : 128) + 21 * grain + 7 * scuff;
      const i = 4 * (size * y + x);
      image.data[i] = value;
      image.data[i + 1] = bare ? .88 * value : .66 * value;
      image.data[i + 2] = bare ? .74 * value : .49 * value;
      image.data[i + 3] = edge < 2 + 2 * scuff + 2 * grain ? 0 : 255;
    }
  }
  g.putImageData(image, 0, 0);
}

export function drawSeaChest(g, size) {
  g.fillStyle = '#635d50';
  g.fillRect(0, 0, size, size);
  g.fillStyle = '#303330';
  g.fillRect(6, 7, size - 12, size - 14);
  for (let i = 0; i < 15; i++) {
    const y = 10 + i * 16;
    const strip = g.createLinearGradient(0, y, 0, y + 7);
    strip.addColorStop(0, '#898a78');
    strip.addColorStop(.28, '#756e5d');
    strip.addColorStop(1, '#494a42');
    g.fillStyle = strip;
    g.fillRect(9, y, size - 18, 7);
  }
  g.fillStyle = '#6b6251';
  g.fillRect(size * .48, 5, 7, size - 10);
  for (const x of [4, size - 5]) {
    for (const y of [4, size / 2, size - 5]) {
      g.fillStyle = '#bbb19c';
      g.beginPath();
      g.arc(x, y, 2.5, 0, Math.PI * 2);
      g.fill();
    }
  }
}

// A coat of oxide paint with an access cover at the rudder stock and worn alignment bars at the trailing edge.
export function drawRudderPlate(g, size) {
  drawHullPlating(g, size);
  g.globalCompositeOperation = 'multiply';
  g.fillStyle = '#9c5541';
  g.fillRect(0, 0, size, size);
  g.globalCompositeOperation = 'source-over';
  const x = .73 * size;
  const y = .37 * size;
  const radius = size * .105;
  g.fillStyle = '#453e37';
  g.beginPath();
  g.arc(x, y, radius, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#746353';
  g.beginPath();
  g.arc(x, y, radius - 2, 0, Math.PI * 2);
  g.fill();
  for (let i = 0; i < 8; i++) {
    const angle = i * Math.PI / 4;
    g.fillStyle = '#b4a58b';
    g.beginPath();
    g.arc(x + .78 * radius * Math.cos(angle), y + .78 * radius * Math.sin(angle), 2, 0, 2 * Math.PI);
    g.fill();
  }
  g.fillStyle = '#463e37';
  g.fillRect(x - 6, y - 2, 12, 4);
  g.fillStyle = '#b6ab86';
  g.fillRect(0, size * .63, size * .10, 3);
  g.fillRect(0, size * .66, size * .065, 2);
  g.fillRect(0, size * .69, size * .065, 2);
}
