// Vehicle attitude from the authoritative FRD/NED Euler angles, in degrees.
// Side view: bow points right, positive pitch raises it. Stern view: starboard
// is on the right, positive roll lowers it. The dashed reference stays level.
export function drawROVAttitude(canvas,{pitch=0,roll=0,heading=0}={}){
  const valid=[pitch,roll,heading].every(Number.isFinite),ctx=canvas.getContext('2d');
  if(!ctx)return;
  ctx.save();ctx.clearRect(0,0,canvas.width,canvas.height);ctx.scale(canvas.width/520,canvas.height/240);
  ctx.fillStyle='#0a202b';ctx.fillRect(0,0,520,240);
  const ink='#d8e9ec',muted='#91aab3',accent='#edcb64';
  ctx.font='18px system-ui';ctx.textAlign='left';ctx.fillStyle=muted;ctx.fillText('ROV 姿態',16,27);
  const hdg=((Math.round(heading)%360)+360)%360;
  ctx.textAlign='right';ctx.fillText(valid?`航向 ${String(hdg).padStart(3,'0')}°`:'等待姿態資料',504,27);
  ctx.strokeStyle='#28424d';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(12,39);ctx.lineTo(508,39);ctx.moveTo(260,52);ctx.lineTo(260,229);ctx.stroke();
  const signed=value=>(Math.abs(value)<.05?'0.0':`${value>0?'+':''}${value.toFixed(1)}`)+'°';
  function gauge(x,angle,side){
    ctx.save();ctx.translate(x,124);
    ctx.textAlign='center';ctx.fillStyle=ink;ctx.font='22px system-ui';ctx.fillText(side?'俯仰 · 側視':'橫滾 · 艉視',0,-60);
    ctx.strokeStyle='#688690';ctx.lineWidth=1;ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(-109,0);ctx.lineTo(109,0);ctx.stroke();ctx.setLineDash([]);
    ctx.font='20px system-ui';ctx.fillStyle=muted;ctx.fillText(side?'艉':'左舷',-99,20);ctx.fillText(side?'艏':'右舷',99,20);
    if(valid){
      ctx.save();ctx.rotate((side?-angle:angle)*Math.PI/180);
      ctx.fillStyle='#142d39';ctx.strokeStyle=ink;ctx.lineWidth=3;
      ctx.fillRect(-51,-14,102,37);ctx.strokeRect(-51,-14,102,37);
      ctx.fillStyle=accent;ctx.fillRect(-47,-24,94,9);
      ctx.strokeStyle=muted;ctx.beginPath();ctx.moveTo(-58,31);ctx.lineTo(58,31);ctx.moveTo(-40,23);ctx.lineTo(-40,31);ctx.moveTo(40,23);ctx.lineTo(40,31);ctx.stroke();
      const thruster=(tx,ty)=>{ctx.fillStyle='#07161c';ctx.strokeStyle='#9aaeb4';ctx.lineWidth=2;ctx.beginPath();ctx.arc(tx,ty,10,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.strokeStyle='#ce765a';ctx.beginPath();ctx.moveTo(tx-6,ty-6);ctx.lineTo(tx+6,ty+6);ctx.moveTo(tx+6,ty-6);ctx.lineTo(tx-6,ty+6);ctx.stroke();};
      if(side){thruster(-24,3);ctx.fillStyle='#82d3e4';ctx.fillRect(48,-9,11,9);ctx.beginPath();ctx.moveTo(68,-5);ctx.lineTo(58,-11);ctx.lineTo(58,1);ctx.closePath();ctx.fill();}
      else{thruster(-28,3);thruster(28,3);}
      ctx.restore();
      ctx.fillStyle=ink;ctx.beginPath();ctx.arc(0,0,2.5,0,Math.PI*2);ctx.fill();
    }
    ctx.fillStyle=accent;ctx.font='bold 28px ui-monospace,monospace';ctx.fillText(valid?signed(angle):'—',0,76);
    ctx.fillStyle=muted;ctx.font='20px system-ui';ctx.fillText(!valid?'無資料':Math.abs(angle)<.05?'水平':side?(angle>0?'抬頭':'低頭'):(angle>0?'右舷下沉':'左舷下沉'),0,100);
    ctx.restore();
  }
  gauge(130,pitch,true);gauge(390,roll,false);ctx.restore();
  canvas.dataset.pitch=valid?pitch.toFixed(1):'';canvas.dataset.roll=valid?roll.toFixed(1):'';canvas.dataset.heading=valid?String(hdg):'';
  canvas.setAttribute('role','img');canvas.setAttribute('aria-label',valid?`ROV 姿態：俯仰 ${signed(pitch)}（側視，艏朝右）；橫滾 ${signed(roll)}（艉視，右舷在右）；航向 ${hdg} 度。`:'等待 ROV 姿態資料');
}
