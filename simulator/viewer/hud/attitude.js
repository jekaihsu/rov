// Compact roll horizon and pitch ladder for the flight overlay; engineering ADI stays intact.
export function drawFlightAttitude(canvas, euler) {
  const ctx = canvas.getContext('2d');
  const [roll, pitch] = euler || [0, 0];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.strokeStyle = '#e8f1f5';
  ctx.fillStyle = '#e8f1f5';
  ctx.font = '24px system-ui';
  ctx.textAlign = 'center';
  ctx.rotate(roll * Math.PI / 180);
  for (let degree = -30; degree <= 30; degree += 10) {
    const y = (pitch - degree) * 5;
    if (Math.abs(y) > 100) continue;
    const length = degree === 0 ? 160 : 64;
    ctx.beginPath();
    ctx.moveTo(-length, y);
    ctx.lineTo(-24, y);
    ctx.moveTo(24, y);
    ctx.lineTo(length, y);
    ctx.stroke();
    if (degree) ctx.fillText(String(degree), 0, y + 8);
  }
  ctx.restore();
  ctx.strokeStyle = '#4fd1e0';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(200, 120);
  ctx.lineTo(240, 120);
  ctx.lineTo(260, 130);
  ctx.lineTo(280, 120);
  ctx.lineTo(320, 120);
  ctx.stroke();
}
