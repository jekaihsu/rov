// Continuous heading tape interpolation with wrap-safe heading differences.
let displayed;
export function drawFlightCompass(canvas, heading, dt) {
  displayed ??= heading;
  const delta = ((heading - displayed + 540) % 360) - 180;
  displayed = (displayed + delta * (1 - Math.exp(-dt * 12)) + 360) % 360;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'rgba(8,18,26,.62)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#8fa6b2';
  ctx.fillStyle = '#e8f1f5';
  ctx.font = '24px monospace';
  ctx.textAlign = 'center';
  for (let angle = Math.floor((displayed - 50) / 5) * 5; angle <= displayed + 50; angle += 5) {
    const x = canvas.width / 2 + (angle - displayed) * 5;
    const normalized = (angle + 360) % 360;
    ctx.beginPath();
    ctx.moveTo(x, 60);
    ctx.lineTo(x, normalized % 30 ? 50 : 40);
    ctx.stroke();
    if (normalized % 30 === 0) ctx.fillText(String(normalized).padStart(3, '0'), x, 27);
  }
  ctx.fillStyle = '#4fd1e0';
  ctx.fillRect(canvas.width / 2 - 35, 0, 70, 32);
  ctx.fillStyle = '#04090d';
  ctx.fillText(String(Math.round(displayed) % 360).padStart(3, '0'), canvas.width / 2, 25);
}
