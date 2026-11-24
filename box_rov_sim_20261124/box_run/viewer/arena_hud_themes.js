// /arena 3-Candidate HUD & Underwater Scene Bakeoff + Grafted Synthesis Engine for ROV-01
// Candidates:
//   1. TACTICAL_SONAR         (Candidate A: Cyan #22D3EE + Phosphor Green #10B981, 6-Thruster Hex-Radar, low-vis scatter)
//   2. INDUSTRIAL_P260        (Candidate B: Safety Amber #F59E0B + Slate #0F172A, Live UT A-Scan Waveform, Tether Catenary Meter)
//   3. STEAM_DIEGETIC         (Candidate C: Diegetic Pilot Visor Vignette, Thruster RPM Acoustic Spectrum, M4 Gate Split-Timer)
// Grafted Default: Combines Candidate A's 6-thruster hex-vector radar, Candidate B's UT A-scan & tether catenary meter,
//                  and Candidate C's mission split-timer & RPM spectrum, while allowing live F2 / pill preset switching.

export const ARENA_PRESET_ORDER = [
  'TACTICAL_SONAR',
  'INDUSTRIAL_P260',
  'STEAM_DIEGETIC',
];

export const ARENA_HUD_PRESETS = {
  TACTICAL_SONAR: {
    id: 'TACTICAL_SONAR',
    code: 'CANDIDATE_A',
    label: 'TACTICAL SONAR',
    titleZh: '深海戰術聲納 HUD',
    primary: '#22D3EE',
    secondary: '#10B981',
    accent: '#38BDF8',
    bgPanel: 'rgba(4, 17, 29, 0.92)',
    borderPanel: 'rgba(34, 211, 238, 0.48)',
    vignette: 'radial-gradient(circle at 50% 50%, rgba(4,17,29,0) 62%, rgba(2,12,22,0.52) 100%)',
    scanlinesOpacity: 0.18,
    underwater: {
      waterSurfHex: '#125369',
      waterDeepHex: '#020b14',
      fogDensityScale: 0.90,
      hemiIntensity: 1.35,
      sunIntensity: 1.45,
      particleOpacity: 0.68,
    },
  },
  INDUSTRIAL_P260: {
    id: 'INDUSTRIAL_P260',
    code: 'CANDIDATE_B',
    label: 'INDUSTRIAL P260',
    titleZh: 'P260 海事工程巡檢 HUD',
    primary: '#F59E0B',
    secondary: '#22D3EE',
    accent: '#FDE047',
    bgPanel: 'rgba(15, 23, 42, 0.94)',
    borderPanel: 'rgba(245, 158, 11, 0.50)',
    vignette: 'radial-gradient(circle at 50% 50%, rgba(15,23,42,0) 72%, rgba(9,13,22,0.34) 100%)',
    scanlinesOpacity: 0.06,
    underwater: {
      waterSurfHex: '#1b6075',
      waterDeepHex: '#05131f',
      fogDensityScale: 1.12,
      hemiIntensity: 1.60,
      sunIntensity: 1.75,
      particleOpacity: 0.42,
    },
  },
  STEAM_DIEGETIC: {
    id: 'STEAM_DIEGETIC',
    alias: 'STEAM_DIEGETIC_COCKPIT',
    code: 'CANDIDATE_C',
    label: 'STEAM DIEGETIC',
    titleZh: 'Steam 沉浸式頭盔座艙 HUD',
    primary: '#06B6D4',
    secondary: '#FACC15',
    accent: '#10B981',
    bgPanel: 'rgba(9, 13, 22, 0.90)',
    borderPanel: 'rgba(6, 182, 212, 0.45)',
    vignette: 'radial-gradient(circle at 50% 50%, rgba(9,13,22,0) 56%, rgba(2,6,23,0.64) 100%)',
    scanlinesOpacity: 0.12,
    underwater: {
      waterSurfHex: '#1d6378',
      waterDeepHex: '#030914',
      fogDensityScale: 1.05,
      hemiIntensity: 1.50,
      sunIntensity: 1.65,
      particleOpacity: 0.54,
    },
  },
};

// Alias STEAM_DIEGETIC_COCKPIT -> STEAM_DIEGETIC for callers using full candidate name
ARENA_HUD_PRESETS.STEAM_DIEGETIC_COCKPIT = ARENA_HUD_PRESETS.STEAM_DIEGETIC;

export function normalizePresetId(id) {
  if (!id) return 'TACTICAL_SONAR';
  const up = String(id).trim().toUpperCase();
  if (up === 'STEAM_DIEGETIC_COCKPIT' || up === 'CANDIDATE_C') return 'STEAM_DIEGETIC';
  if (up === 'CANDIDATE_A') return 'TACTICAL_SONAR';
  if (up === 'CANDIDATE_B') return 'INDUSTRIAL_P260';
  return ARENA_HUD_PRESETS[up] ? ARENA_HUD_PRESETS[up].id : 'TACTICAL_SONAR';
}

export function installArenaHudThemes({ getState, getWorld } = {}) {
  let activePresetId = 'TACTICAL_SONAR';
  let phaseClock = 0;

  // Inject CSS for the 3 Arena presets + Grafted HUD widgets
  const style = document.createElement('style');
  style.id = 'arenaHudThemeStyles';
  style.textContent = `
    :root {
      --arena-primary: #22D3EE;
      --arena-secondary: #10B981;
      --arena-accent: #38BDF8;
      --arena-bg: rgba(4, 17, 29, 0.92);
      --arena-border: rgba(34, 211, 238, 0.48);
      --arena-vignette: radial-gradient(circle at 50% 50%, rgba(4,17,29,0) 62%, rgba(2,12,22,0.52) 100%);
      --arena-scanlines: 0.18;
    }
    .w1-sec {
      background: var(--arena-bg) !important;
      border-color: var(--arena-border) !important;
      transition: background 0.2s ease, border-color 0.2s ease;
    }
    .w1-sec h2 {
      color: var(--arena-primary) !important;
    }
    .w1-hud-banner {
      pointer-events: auto !important;
      border-color: var(--arena-border) !important;
      background: var(--arena-bg) !important;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.55);
    }
    .arena-preset-pill {
      cursor: pointer;
      user-select: none;
      padding: 2px 9px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.04em;
      background: rgba(34, 211, 238, 0.18);
      color: var(--arena-primary);
      border: 1px solid var(--arena-primary);
      transition: all 0.15s ease;
    }
    .arena-preset-pill:hover {
      filter: brightness(1.2);
      transform: translateY(-1px);
    }
    .arena-diegetic-overlay {
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 18;
      background: var(--arena-vignette);
      overflow: hidden;
    }
    .arena-diegetic-scanlines {
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0) 0px,
        rgba(255, 255, 255, 0) 2px,
        rgba(34, 211, 238, 0.07) 3px
      );
      opacity: var(--arena-scanlines);
    }
    .arena-visor-corner {
      position: absolute;
      width: 28px;
      height: 28px;
      border-color: var(--arena-primary);
      opacity: 0.65;
    }
    .arena-visor-corner.tl { top: 12px; left: 12px; border-top: 2px solid var(--arena-primary); border-left: 2px solid var(--arena-primary); }
    .arena-visor-corner.tr { top: 12px; right: 12px; border-top: 2px solid var(--arena-primary); border-right: 2px solid var(--arena-primary); }
    .arena-visor-corner.bl { bottom: 12px; left: 12px; border-bottom: 2px solid var(--arena-primary); border-left: 2px solid var(--arena-primary); }
    .arena-visor-corner.br { bottom: 12px; right: 12px; border-bottom: 2px solid var(--arena-primary); border-right: 2px solid var(--arena-primary); }
    .arena-graft-box {
      margin-top: 6px;
      padding: 6px 8px;
      border-radius: 6px;
      background: rgba(2, 8, 18, 0.78);
      border: 1px solid rgba(148, 163, 184, 0.22);
    }
    .arena-graft-title {
      font-size: 10.5px;
      font-weight: 700;
      color: var(--arena-primary);
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
      letter-spacing: 0.03em;
    }
    .arena-theme-tabs {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      margin-bottom: 6px;
    }
    .arena-theme-tab {
      padding: 4px 4px;
      font-size: 10px;
      font-weight: 700;
      border-radius: 4px;
      border: 1px solid rgba(148, 163, 184, 0.28);
      background: rgba(15, 23, 42, 0.85);
      color: #cbd5e1;
      cursor: pointer;
      text-align: center;
      transition: all 0.12s ease;
    }
    .arena-theme-tab.active {
      border-color: var(--arena-primary);
      color: #020617;
      background: var(--arena-primary);
    }
    .arena-split-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 3px;
      font-size: 10px;
      margin-top: 4px;
    }
    .arena-split-cell {
      background: rgba(15, 23, 42, 0.88);
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: 3px;
      padding: 2px 4px;
      text-align: center;
    }
    .arena-split-cell.done {
      border-color: #10B981;
      color: #6ee7b7;
    }
    .arena-split-cell.active {
      border-color: #FACC15;
      color: #fde047;
    }
    .arena-rpm-bars {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 4px;
      height: 22px;
      align-items: end;
      margin-top: 4px;
      padding: 2px 4px;
      background: rgba(2, 6, 23, 0.75);
      border-radius: 4px;
    }
    .arena-rpm-col {
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
    }
    .arena-rpm-fill {
      width: 100%;
      background: linear-gradient(to top, var(--arena-primary), var(--arena-secondary));
      border-radius: 2px 2px 0 0;
      transition: height 0.08s ease;
    }
  `;
  document.head.appendChild(style);

  // 1. Add Diegetic Viewport Overlay inside #vp (Candidate C graft: subtle visor vignette + corners)
  const vp = document.getElementById('vp');
  const diegeticOverlay = document.createElement('div');
  diegeticOverlay.className = 'arena-diegetic-overlay';
  diegeticOverlay.id = 'arenaDiegeticFrame';
  diegeticOverlay.innerHTML = `
    <div class="arena-diegetic-scanlines"></div>
    <div class="arena-visor-corner tl"></div>
    <div class="arena-visor-corner tr"></div>
    <div class="arena-visor-corner bl"></div>
    <div class="arena-visor-corner br"></div>
  `;
  if (vp) vp.appendChild(diegeticOverlay);

  // 2. Add clickable Preset Pill into #w1HudBanner
  const banner = document.getElementById('w1HudBanner');
  const presetPill = document.createElement('span');
  presetPill.className = 'arena-preset-pill';
  presetPill.id = 'w1ArenaPresetPill';
  presetPill.title = '點擊或按 F2 切換 /arena HUD 視覺方案 (TACTICAL_SONAR / INDUSTRIAL_P260 / STEAM_DIEGETIC)';
  presetPill.textContent = 'HUD: TACTICAL SONAR [F2]';
  if (banner) banner.appendChild(presetPill);

  // 3. Inject Candidate A + Candidate C Grafted Widgets into Left Rack (#wave1MissionPanel)
  const leftMissionPanel = document.getElementById('wave1MissionPanel');
  const leftGraft = document.createElement('div');
  leftGraft.className = 'arena-graft-box';
  leftGraft.id = 'arenaLeftGraft';
  leftGraft.innerHTML = `
    <div class="arena-graft-title">
      <span>/ARENA HUD 視覺主題 (F2 切換)</span>
      <span id="arenaActiveCode" style="color:#10B981;">GRAFTED v3</span>
    </div>
    <div class="arena-theme-tabs" id="arenaThemeTabs">
      <button type="button" class="arena-theme-tab active" data-arena-preset="TACTICAL_SONAR">A 戰術聲納</button>
      <button type="button" class="arena-theme-tab" data-arena-preset="INDUSTRIAL_P260">B 工業巡檢</button>
      <button type="button" class="arena-theme-tab" data-arena-preset="STEAM_DIEGETIC">C 頭盔座艙</button>
    </div>
    <div style="display:grid;grid-template-columns:132px 1fr;gap:6px;align-items:center;">
      <canvas id="arenaHexRadar" width="132" height="96" style="background:rgba(2,10,20,0.9);border:1px solid rgba(34,211,238,0.28);border-radius:4px;"></canvas>
      <div>
        <div style="font-size:10px;color:#94a3b8;display:flex;justify-content:space-between;">
          <span>6-THRUSTER HEX VECTOR</span>
          <b id="arenaHexMag" style="color:#22D3EE;">0.00 N·m</b>
        </div>
        <div class="arena-rpm-bars" id="arenaRpmSpectrum">
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_0" style="height:15%"></div></div>
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_1" style="height:15%"></div></div>
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_2" style="height:15%"></div></div>
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_3" style="height:15%"></div></div>
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_4" style="height:15%"></div></div>
          <div class="arena-rpm-col"><div class="arena-rpm-fill" id="arenaRpm_5" style="height:15%"></div></div>
        </div>
        <div style="font-size:10px;color:#94a3b8;margin-top:4px;display:flex;justify-content:space-between;">
          <span>M4 管線穿越分段計時</span>
          <b id="arenaSplitDelta" style="color:#10B981;">-0.62s GOLD</b>
        </div>
        <div class="arena-split-grid" id="arenaSplitTimer">
          <div class="arena-split-cell done" id="arenaGate_1">G1<br>18.4s</div>
          <div class="arena-split-cell done" id="arenaGate_2">G2<br>37.1s</div>
          <div class="arena-split-cell active" id="arenaGate_3">G3<br>56.8s</div>
          <div class="arena-split-cell" id="arenaGate_4">G4<br>84.0s</div>
        </div>
      </div>
    </div>
  `;
  if (leftMissionPanel) leftMissionPanel.appendChild(leftGraft);

  // 4. Inject Candidate B Grafted Widgets into Right Rack (#wave1B2BPanel): Live UT A-Scan + Tether Catenary Meter
  const rightB2BPanel = document.getElementById('wave1B2BPanel');
  const rightGraft = document.createElement('div');
  rightGraft.className = 'arena-graft-box';
  rightGraft.id = 'arenaRightGraft';
  rightGraft.innerHTML = `
    <div class="arena-graft-title">
      <span>UT A-SCAN 超音波波形 & 懸鏈張力</span>
      <span id="arenaUtGateStatus" style="color:#22D3EE;">GATE: 13.8mm</span>
    </div>
    <canvas id="arenaUtAScan" width="260" height="58" style="width:100%;height:58px;background:rgba(2,10,20,0.92);border:1px solid rgba(245,158,11,0.32);border-radius:4px;display:block;"></canvas>
    <div style="display:flex;justify-content:space-between;align-items:center;font-size:10px;color:#cbd5e1;margin-top:4px;">
      <span>臍帶纜懸鏈張力 (Catenary)</span>
      <b id="arenaTetherTensionText" style="color:#10B981;">42.0 N / 250 N WARN</b>
    </div>
    <div style="height:5px;background:rgba(30,41,59,0.9);border-radius:3px;overflow:hidden;margin-top:2px;">
      <div id="arenaTetherBarFill" style="height:100%;width:18%;background:linear-gradient(90deg,#10B981,#F59E0B);transition:width 0.1s;"></div>
    </div>
  `;
  if (rightB2BPanel) rightB2BPanel.appendChild(rightGraft);

  function applyUnderwaterThemeToScene(preset) {
    const v = typeof window !== 'undefined' ? window.__viewer : null;
    if (!v || !v.THREE || !v.scene) return;
    const uw = preset.underwater;
    try {
      v.scene.userData.arenaPreset = preset.id;
      const bg = new v.THREE.Color(uw.waterSurfHex);
      if (v.scene.background && v.scene.background.set) {
        v.scene.background.lerp(bg, 0.35);
      }
      if (v.scene.fog && v.scene.fog.color) {
        v.scene.fog.color.lerp(bg, 0.35);
      }
    } catch (_) {
      // Ignore scene tint errors during early boot
    }
  }

  function setPreset(presetId) {
    const normId = normalizePresetId(presetId);
    const preset = ARENA_HUD_PRESETS[normId];
    activePresetId = preset.id;

    document.documentElement.dataset.arenaTheme = preset.id;
    const rootStyle = document.documentElement.style;
    rootStyle.setProperty('--arena-primary', preset.primary);
    rootStyle.setProperty('--arena-secondary', preset.secondary);
    rootStyle.setProperty('--arena-accent', preset.accent);
    rootStyle.setProperty('--arena-bg', preset.bgPanel);
    rootStyle.setProperty('--arena-border', preset.borderPanel);
    rootStyle.setProperty('--arena-vignette', preset.vignette);
    rootStyle.setProperty('--arena-scanlines', String(preset.scanlinesOpacity));

    if (presetPill) {
      presetPill.textContent = `HUD: ${preset.label} [F2]`;
    }
    const codeEl = document.getElementById('arenaActiveCode');
    if (codeEl) {
      codeEl.textContent = `${preset.id}`;
      codeEl.style.color = preset.primary;
    }
    document.querySelectorAll('#arenaThemeTabs .arena-theme-tab').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.arenaPreset === preset.id);
    });

    applyUnderwaterThemeToScene(preset);
    return preset;
  }

  function cyclePreset() {
    const idx = ARENA_PRESET_ORDER.indexOf(activePresetId);
    const nextId = ARENA_PRESET_ORDER[(idx + 1) % ARENA_PRESET_ORDER.length];
    return setPreset(nextId);
  }

  // Wire click events & F2 shortcut
  presetPill.addEventListener('click', () => cyclePreset());
  document.querySelectorAll('#arenaThemeTabs .arena-theme-tab').forEach((btn) => {
    btn.addEventListener('click', () => setPreset(btn.dataset.arenaPreset));
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'F2') {
      e.preventDefault();
      cyclePreset();
    }
  });

  // Draw Candidate A's 6-Thruster Hex-Vector Radar
  function drawHexRadar(thrust = [0, 0, 0, 0, 0, 0], health = [1, 1, 1, 1, 1, 1], preset = ARENA_HUD_PRESETS[activePresetId]) {
    const canvas = document.getElementById('arenaHexRadar');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const cx = w * 0.5;
    const cy = h * 0.5;
    const R = Math.min(w, h) * 0.39;

    ctx.clearRect(0, 0, w, h);

    // Hexagonal sonar grid rings
    const labels = ['T1', 'T2', 'T6', 'T4', 'T3', 'T5'];
    const orderIdx = [0, 1, 5, 3, 2, 4];
    for (const frac of [0.5, 1.0]) {
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const ang = -Math.PI / 2 + (i * Math.PI) / 3;
        const x = cx + Math.cos(ang) * R * frac;
        const y = cy + Math.sin(ang) * R * frac;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = frac === 1.0 ? 'rgba(34, 211, 238, 0.38)' : 'rgba(148, 163, 184, 0.18)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Thrust polygon & spokes
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const tIdx = orderIdx[i];
      const ang = -Math.PI / 2 + (i * Math.PI) / 3;
      const isFault = (health[tIdx] ?? 1) <= 0.15;
      const mag = isFault ? 0.08 : Math.min(1, Math.max(0.12, Math.abs(Number(thrust[tIdx] || 0))));
      const px = cx + Math.cos(ang) * R * mag;
      const py = cy + Math.sin(ang) * R * mag;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(34, 211, 238, 0.22)';
    ctx.fill();
    ctx.strokeStyle = preset.primary;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // Vertex dots + fault highlights + labels
    for (let i = 0; i < 6; i++) {
      const tIdx = orderIdx[i];
      const ang = -Math.PI / 2 + (i * Math.PI) / 3;
      const isFault = (health[tIdx] ?? 1) <= 0.15;
      const lx = cx + Math.cos(ang) * (R + 9);
      const ly = cy + Math.sin(ang) * (R + 8);
      ctx.fillStyle = isFault ? '#EF4444' : '#94A3B8';
      ctx.font = 'bold 8.5px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(labels[i], lx, ly);

      if (isFault) {
        ctx.beginPath();
        ctx.arc(cx + Math.cos(ang) * R * 0.65, cy + Math.sin(ang) * R * 0.65, 4.2, 0, Math.PI * 2);
        ctx.fillStyle = '#EF4444';
        ctx.fill();
      }
    }

    // Resultant vector arrow in center
    const surge = ((thrust[0] || 0) + (thrust[1] || 0) + (thrust[2] || 0) + (thrust[3] || 0)) * 0.35;
    const sway = ((thrust[0] || 0) - (thrust[1] || 0) - (thrust[2] || 0) + (thrust[3] || 0)) * 0.35;
    const vx = Math.max(-1, Math.min(1, sway)) * R * 0.75;
    const vy = -Math.max(-1, Math.min(1, surge)) * R * 0.75;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + vx, cy + vy);
    ctx.strokeStyle = preset.secondary;
    ctx.lineWidth = 2.2;
    ctx.stroke();

    const magEl = document.getElementById('arenaHexMag');
    if (magEl) {
      const totalMag = thrust.reduce((acc, v, i) => acc + ((health[i] ?? 1) > 0.15 ? Math.abs(Number(v) || 0) : 0), 0);
      magEl.textContent = `${(totalMag * 14.5).toFixed(1)} N`;
    }
  }

  // Draw Candidate B's Live UT A-Scan Waveform
  function drawUtAScan(w1 = {}, preset = ARENA_HUD_PRESETS[activePresetId]) {
    const canvas = document.getElementById('arenaUtAScan');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Oscilloscope graticule
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
    ctx.lineWidth = 1;
    for (let x = 26; x < w; x += 26) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 14; y < h; y += 14) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    const utRingState = w1.wave3?.ut_ring_state || 'searching';
    const sop = w1.sop_evaluation || {};
    const doneCps = (sop.ut_checkpoints || []).filter((c) => c.completed);
    const latestCp = doneCps.length > 0 ? doneCps[doneCps.length - 1] : (sop.ut_checkpoints || [])[0];
    const measuredMm = latestCp ? Number(latestCp.measured_mm || 13.8) : 13.8;

    const traceColor =
      utRingState === 'coupled' ? '#10B981' :
      utRingState === 'aligning' ? '#F59E0B' : '#22D3EE';

    // Gate threshold bar
    const gateX = Math.round((measuredMm / 20.0) * (w * 0.72) + w * 0.16);
    ctx.strokeStyle = '#F59E0B';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(gateX - 16, h * 0.28);
    ctx.lineTo(gateX + 16, h * 0.28);
    ctx.stroke();

    // Synthesize A-scan RF envelope waveform
    ctx.beginPath();
    const baseLine = h - 7;
    for (let x = 0; x < w; x++) {
      // Initial pulse at x=12, primary backwall echo at gateX, secondary multiple at gateX*1.55
      const d0 = (x - 12) / 4.0;
      const d1 = (x - gateX) / 5.2;
      const d2 = (x - Math.min(w - 12, gateX * 1.48)) / 6.5;
      const env0 = Math.exp(-d0 * d0) * 0.85;
      const env1 = Math.exp(-d1 * d1) * (utRingState === 'coupled' ? 0.92 : 0.62);
      const env2 = Math.exp(-d2 * d2) * 0.34;
      const ripple = Math.abs(Math.sin(x * 0.65 + phaseClock * 4.0));
      const amp = Math.min(1, (env0 + env1 + env2) * (0.75 + 0.25 * ripple));
      const y = baseLine - amp * (h - 13);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = traceColor;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    const gateEl = document.getElementById('arenaUtGateStatus');
    if (gateEl) {
      gateEl.textContent = `${utRingState.toUpperCase()} · ${measuredMm.toFixed(1)}mm`;
      gateEl.style.color = traceColor;
    }
  }

  // Initialize default preset
  setPreset('TACTICAL_SONAR');

  const api = {
    PRESETS: ARENA_HUD_PRESETS,
    ORDER: ARENA_PRESET_ORDER,
    getPreset() {
      return activePresetId;
    },
    setPreset,
    cyclePreset,
    update(s, dt = 0.033) {
      phaseClock += dt;
      if (!s) return;
      const preset = ARENA_HUD_PRESETS[activePresetId] || ARENA_HUD_PRESETS.TACTICAL_SONAR;
      const thrust = s.thrust || [0, 0, 0, 0, 0, 0];
      const health = s.health || [1, 1, 1, 1, 1, 1];
      const w1 = s.wave1 || {};

      // 1. Update Candidate A Hex-Radar
      drawHexRadar(thrust, health, preset);

      // 2. Update Candidate B UT A-Scan & Tether Catenary Meter
      drawUtAScan(w1, preset);
      const tetherN = Number(s.tether?.tension_rov ?? (28 + Math.abs(thrust[0] || 0) * 65));
      const tetherTxt = document.getElementById('arenaTetherTensionText');
      const tetherFill = document.getElementById('arenaTetherBarFill');
      if (tetherTxt) {
        const snag = w1.wave3?.tether_snag_active;
        tetherTxt.textContent = snag ? `⚠️ SNAG ${tetherN.toFixed(0)} N` : `${tetherN.toFixed(1)} N / 250 N WARN`;
        tetherTxt.style.color = snag || tetherN > 250 ? '#EF4444' : tetherN > 160 ? '#F59E0B' : '#10B981';
      }
      if (tetherFill) {
        const pct = Math.min(100, Math.max(8, (tetherN / 250) * 100));
        tetherFill.style.width = `${pct.toFixed(1)}%`;
      }

      // 3. Update Candidate C RPM Acoustic Spectrum & Speedrun Split-Timer
      for (let i = 0; i < 6; i++) {
        const el = document.getElementById(`arenaRpm_${i}`);
        if (el) {
          const isFault = (health[i] ?? 1) <= 0.15;
          const pct = isFault ? 10 : Math.min(100, Math.max(14, Math.round(Math.abs(thrust[i] || 0) * 100)));
          el.style.height = `${pct}%`;
          el.style.background = isFault ? '#EF4444' : `linear-gradient(to top, ${preset.primary}, ${preset.secondary})`;
        }
      }

      const elapsed = Number(s.t ?? w1.sop_evaluation?.elapsed_s ?? 12.4);
      const splitDelta = document.getElementById('arenaSplitDelta');
      if (splitDelta) {
        const mId = w1.mission_id || getWorld?.()?.scenario?.key || 'mission_1_pool';
        if (mId === 'mission_4_pipeline') {
          splitDelta.textContent = `-0.84s GOLD (${elapsed.toFixed(1)}s)`;
          splitDelta.style.color = '#FACC15';
        } else {
          splitDelta.textContent = `T+${elapsed.toFixed(1)}s PACE OK`;
          splitDelta.style.color = preset.secondary;
        }
      }
    },
  };

  if (typeof window !== 'undefined') {
    window.__arenaHud = api;
  }
  return api;
}
