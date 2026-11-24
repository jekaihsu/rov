// Wave 1 B2B Fault & Hazard Training HUD + B2C 4-Mission Selector + 6DoF Gamepad + UT SOP Evaluator
// CORR-ROV-01 Compliant: Self-designed ROV-01 Industrial Open-Frame architecture (0 external brand strings)

const $ = (id) => document.getElementById(id);

import { axisDeadzoneExpo, setShaping, sanitize } from './input_shaping.js';
import { rovAudio } from './rov_audio.js';
import { installArenaHudThemes, ARENA_HUD_PRESETS, ARENA_PRESET_ORDER } from './arena_hud_themes.js';
import { SimReadySceneManager, USD_WEB_VIEWER_META, nedToThreeVec } from './simready_usd_loader.js';
import { installCableCampaign } from './cable_campaign.js';

// Wave 2: delegates to input_shaping.js (fixes slider value 0 silently falling back to defaults).
export function applyDeadzoneAndExpoJS(val, deadzone = 0.08, expo = 0.35) {
  return axisDeadzoneExpo(val, deadzone, expo);
}

export function installWave1Hud({ send, getState, getWorld, getActiveModel }) {
  // Inject compact industrial CSS for Wave 1 panels
  const style = document.createElement('style');
  style.textContent = `
    .w1-sec { border: 1px solid rgba(56, 189, 248, 0.28); background: rgba(9, 22, 34, 0.92); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
    .w1-sec h2 { color: #22D3EE; font-size: 13px; letter-spacing: 0.04em; margin: 0 0 6px 0; display: flex; justify-content: space-between; align-items: center; }
    .w1-badge { display: inline-block; padding: 2px 7px; border-radius: 99px; font-size: 11px; font-weight: 700; background: rgba(56,189,248,0.16); color: #22D3EE; border: 1px solid rgba(56,189,248,0.4); }
    .w1-badge.warn { background: rgba(245,158,11,0.2); color: #F59E0B; border-color: rgba(245,158,11,0.5); }
    .w1-badge.fault { background: rgba(239,68,68,0.24); color: #fca5a5; border-color: rgba(239,68,68,0.65); }
    .w1-badge.ok { background: rgba(16,185,129,0.2); color: #6ee7b7; border-color: rgba(16,185,129,0.5); }
    .w1-missions { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 6px; }
    .w1-mbtn { text-align: left; padding: 6px 8px; border-radius: 6px; border: 1px solid rgba(148,163,184,0.25); background: rgba(15,32,48,0.85); color: #e2e8f0; cursor: pointer; font-size: 11px; line-height: 1.25; transition: all 0.15s; }
    .w1-mbtn:hover { border-color: #22D3EE; background: rgba(24,52,76,0.9); }
    .w1-mbtn.active { border-color: #facc15; background: rgba(250,204,21,0.14); color: #fef08a; box-shadow: 0 0 8px rgba(250,204,21,0.2); }
    .w1-mbtn b { display: block; font-size: 11.5px; color: #22D3EE; }
    .w1-mbtn.active b { color: #facc15; }
    .w1-dof-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 5px; }
    .w1-dof-cell { background: rgba(15,23,42,0.75); border: 1px solid rgba(148,163,184,0.18); border-radius: 4px; padding: 3px 5px; font-size: 10.5px; }
    .w1-dof-cell .k { color: #94a3b8; display: flex; justify-content: space-between; }
    .w1-dof-bar { height: 4px; background: rgba(51,65,85,0.8); border-radius: 2px; margin-top: 2px; overflow: hidden; position: relative; }
    .w1-dof-fill { height: 100%; background: #22D3EE; width: 0%; transition: width 0.08s; }
    .w1-thr-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3px; margin: 6px 0; }
    .w1-tbtn { padding: 4px 2px; font-size: 10.5px; font-weight: 700; border-radius: 4px; border: 1px solid rgba(148,163,184,0.3); background: rgba(15,32,48,0.9); color: #cbd5e1; cursor: pointer; text-align: center; }
    .w1-tbtn.faulted { background: rgba(220,38,38,0.32); border-color: #EF4444; color: #fecaca; }
    .w1-ut-list { list-style: none; padding: 0; margin: 5px 0; font-size: 11px; }
    .w1-ut-list li { display: flex; justify-content: space-between; padding: 3px 6px; border-radius: 4px; margin-bottom: 3px; background: rgba(15,23,42,0.7); border-left: 3px solid #475569; }
    .w1-ut-list li.done { border-left-color: #10b981; background: rgba(16,185,129,0.1); }
    .w1-ut-list li.warn { border-left-color: #f59e0b; }
    .w1-kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin: 5px 0; font-size: 11px; }
    .w1-kv { background: rgba(15,23,42,0.72); padding: 4px 6px; border-radius: 4px; border: 1px solid rgba(148,163,184,0.14); }
    .w1-kv span { color: #94a3b8; font-size: 10px; display: block; }
    .w1-kv b { color: #f8fafc; font-size: 12px; }
    .w1-modal { position: fixed; inset: 0; background: rgba(2,6,23,0.82); z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px; }
    .w1-modal[hidden] { display: none !important; }
    .w1-modal-card { width: min(760px, 95vw); max-height: 88vh; overflow-y: auto; background: #0b1929; border: 1px solid #22D3EE; border-radius: 10px; padding: 18px; color: #e2e8f0; box-shadow: 0 20px 50px rgba(0,0,0,0.75); }
    .w1-hud-banner { position: absolute; top: 54px; left: 50%; transform: translateX(-50%); background: rgba(9,22,36,0.88); border: 1px solid rgba(56,189,248,0.45); border-radius: 99px; padding: 4px 14px; font-size: 12px; color: #e2e8f0; pointer-events: auto; z-index: 30; white-space: nowrap; display: flex; gap: 10px; align-items: center; }
    .w1-sr-pill { cursor: pointer; padding: 2px 10px; border-radius: 99px; font-size: 11px; font-weight: 700; background: rgba(34,211,238,0.2); color: #22D3EE; border: 1px solid #22D3EE; transition: all 0.15s; }
    .w1-sr-pill:hover, .w1-sr-pill.active { background: #22D3EE; color: #061320; box-shadow: 0 0 10px rgba(34,211,238,0.5); }
    .w1-sr-overlay { position: fixed; top: 96px; right: 278px; width: 430px; max-height: calc(100vh - 125px); overflow-y: auto; background: rgba(6, 16, 28, 0.93); border: 1px solid #22D3EE; border-radius: 10px; padding: 12px 14px; color: #e2e8f0; z-index: 120; box-shadow: 0 16px 42px rgba(0,0,0,0.75); backdrop-filter: blur(8px); }
    .w1-sr-overlay[hidden] { display: none !important; }
    .w1-sr-list { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin: 6px 0; }
    .w1-sr-item { text-align: left; padding: 5px 7px; border-radius: 6px; border: 1px solid rgba(148,163,184,0.25); background: rgba(15,28,44,0.85); color: #cbd5e1; cursor: pointer; font-size: 10.5px; line-height: 1.25; }
    .w1-sr-item.active { border-color: #22D3EE; background: rgba(34,211,238,0.16); color: #f8fafc; box-shadow: 0 0 8px rgba(34,211,238,0.28); }
    .w1-sr-item b { color: #22D3EE; display: block; font-size: 11px; }
    .w1-sr-code { font-family: monospace; font-size: 10.5px; background: rgba(2, 8, 18, 0.9); border: 1px solid rgba(56,189,248,0.28); border-radius: 6px; padding: 6px 8px; max-height: 120px; overflow-y: auto; color: #7dd3fc; white-space: pre; margin-top: 6px; }
  `;
  document.head.appendChild(style);

  // Add top viewport ROV-01 Wave 1 status pill
  const vp = $('vp');
  const hudPill = document.createElement('div');
  hudPill.className = 'w1-hud-banner';
  hudPill.id = 'w1HudBanner';
  hudPill.innerHTML = `
    <span class="w1-badge ok" id="w1ModelTag">ROV-01 工業開放式框架</span>
    <span id="w1BannerMission">Mission 1：新手訓練池</span>
    <span class="w1-badge" id="w1BannerState">STATE: NORMAL</span>
    <span id="w1BannerHull">機體完整度 100%</span>
    <button type="button" class="w1-sr-pill" id="w1SimReadyBtn" title="開啟 NVIDIA Omniverse SimReady OpenUSD 物理資產庫 (熱鍵 F4)">[F4] SimReady USD 資產庫</button>
  `;
  if (vp) vp.appendChild(hudPill);

  // Left Rack: 4-Mission Selector + 6DoF Gamepad Shaping
  const leftRack = document.querySelector('aside.rack.left');
  const missionSec = document.createElement('div');
  missionSec.className = 'w1-sec';
  missionSec.id = 'wave1MissionPanel';
  missionSec.innerHTML = `
    <h2><span>B2C / B2B 四大訓練關卡 (ROV-01)</span><span class="w1-badge" id="w1ActiveMissionCode">M1</span></h2>
    <div class="w1-missions" id="w1MissionButtons">
      <button type="button" class="w1-mbtn active" data-mission-id="mission_1_pool"><b>M1 新手訓練池</b>Pool 6DoF & 搖桿校準</button>
      <button type="button" class="w1-mbtn" data-mission-id="mission_2_hull_ut"><b>M2 港灣船體巡檢</b>船底巡檢 & UT 測厚 SOP</button>
      <button type="button" class="w1-mbtn" data-mission-id="mission_3_sar_fault"><b>M3 暗流深海搜救</b>T3 失效重分配 & 緊急返航</button>
      <button type="button" class="w1-mbtn" data-mission-id="mission_4_pipeline"><b>M4 狹窄管線計時賽</b>雙管線廊道穿越計時</button>
    </div>
    <div class="w1-dof-grid" id="w1DofGrid">
      <div class="w1-dof-cell"><div class="k"><span>進退 Surge</span><b id="w1Dof_surge">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_surge"></div></div></div>
      <div class="w1-dof-cell"><div class="k"><span>橫移 Sway</span><b id="w1Dof_sway">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_sway"></div></div></div>
      <div class="w1-dof-cell"><div class="k"><span>升降 Heave</span><b id="w1Dof_heave">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_heave"></div></div></div>
      <div class="w1-dof-cell"><div class="k"><span>橫滾 Roll</span><b id="w1Dof_roll">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_roll"></div></div></div>
      <div class="w1-dof-cell"><div class="k"><span>俯仰 Pitch</span><b id="w1Dof_pitch">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_pitch"></div></div></div>
      <div class="w1-dof-cell"><div class="k"><span>偏航 Yaw</span><b id="w1Dof_yaw">0.00</b></div><div class="w1-dof-bar"><div class="w1-dof-fill" id="w1Bar_yaw"></div></div></div>
    </div>
    <div class="row gap" style="margin-top:6px;font-size:11px;">
      <label style="flex:1">死區 Deadzone <b id="w1DzVal">0.08</b><input type="range" id="w1Deadzone" min="0.00" max="0.30" step="0.01" value="0.08"></label>
      <label style="flex:1">曲線 Expo <b id="w1ExpoVal">0.35</b><input type="range" id="w1Expo" min="0.00" max="0.85" step="0.05" value="0.35"></label>
    </div>
    <hr style="border:none;border-top:1px solid rgba(148,163,184,0.18);margin:6px 0;">
    <h2><span>Wave 3 飛手閉迴路控制</span><span class="w1-badge ok" id="w3LoopBadge">PID / 聲效就緒</span></h2>
    <div class="btns c2" style="margin-bottom:4px;">
      <button type="button" id="btnDepthHold" style="border-color:#22D3EE;color:#7dd3fc;">定深 PID (Depth Hold)</button>
      <button type="button" id="btnHeadingHold" style="border-color:#22D3EE;color:#7dd3fc;">定艏向 PID (Heading)</button>
    </div>
    <div class="btns c2" style="margin-bottom:4px;">
      <button type="button" id="btnEmergencySurface" style="border-color:#F59E0B;color:#fde68a;">緊急上浮 (Surface)</button>
      <button type="button" id="btnResolveSnag" style="border-color:#10B981;color:#6ee7b7;">纜線纏繞告警解除</button>
    </div>
    <div class="w1-kv-grid">
      <div class="w1-kv"><span>定深 / 定艏向誤差</span><b id="w3PidErrVal">0.00m / 0.0°</b></div>
      <div class="w1-kv"><span>UT 3s 穩定鎖定</span><b id="w3UtHoldVal">SEARCHING (0.0/3.0s)</b></div>
    </div>
  `;
  if (leftRack) leftRack.prepend(missionSec);

  // Right Rack: B2B Thruster Fault Reallocation + Hazard / Emergency RTH + UT Gauging SOP Evaluator
  const rightRack = document.querySelector('aside.rack.right');
  const b2bSec = document.createElement('div');
  b2bSec.className = 'w1-sec';
  b2bSec.id = 'wave1B2BPanel';
  b2bSec.innerHTML = `
    <h2><span>B2B 故障重分配與緊急返航</span><span class="w1-badge ok" id="w1ReallocBadge">6 推進器正常</span></h2>
    <div class="w1-thr-grid" id="w1ThrFaultGrid">
      <button type="button" class="w1-tbtn" data-fault-idx="0" title="切換 T1 左前水平推進器故障">T1<br><small id="w1Th_0">100%</small></button>
      <button type="button" class="w1-tbtn" data-fault-idx="1" title="切換 T2 右前水平推進器故障">T2<br><small id="w1Th_1">100%</small></button>
      <button type="button" class="w1-tbtn" data-fault-idx="2" id="btnToggleT3" title="切換 T3 左後水平推進器故障">T3<br><small id="w1Th_2">100%</small></button>
      <button type="button" class="w1-tbtn" data-fault-idx="3" title="切換 T4 右後水平推進器故障">T4<br><small id="w1Th_3">100%</small></button>
      <button type="button" class="w1-tbtn" data-fault-idx="4" title="切換 T5 左垂直推進器故障">T5<br><small id="w1Th_4">100%</small></button>
      <button type="button" class="w1-tbtn" data-fault-idx="5" title="切換 T6 右垂直推進器故障">T6<br><small id="w1Th_5">100%</small></button>
    </div>
    <div class="btns c2" style="margin-bottom:5px;">
      <button type="button" id="btnInjectT3Fault" style="border-color:#EF4444;color:#fca5a5;">注入 T3 卡死失效</button>
      <button type="button" id="btnClearFaults">恢復 6 推進器</button>
    </div>
    <div class="btns c2" style="margin-bottom:6px;">
      <button type="button" id="btnEmergencyRth" style="border-color:#f59e0b;color:#fde68a;">啟動緊急返航 (RTH)</button>
      <button type="button" id="btnSimCollision">模擬碰撞衝量</button>
    </div>
    <div class="w1-kv-grid">
      <div class="w1-kv"><span>機體完整度 Hull Integrity</span><b id="w1HullVal">100.0%</b></div>
      <div class="w1-kv"><span>水體濁度 / 能見度</span><b id="w1TurbVal">1.2 NTU / 26m</b></div>
      <div class="w1-kv"><span>定深穩定度 / 航向穩定</span><b id="w1StabVal">96.4% / 95.8%</b></div>
      <div class="w1-kv"><span>緊急返航計時 RTH</span><b id="w1RthVal">待命</b></div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(148,163,184,0.18);margin:7px 0;">
    <h2><span>船體巡檢與超音波測厚 SOP</span><span class="w1-badge ok" id="w1SopScoreBadge">SOP 91.5 分</span></h2>
    <ul class="w1-ut-list" id="w1UtList"></ul>
    <div class="btns c2">
      <button type="button" id="btnSampleUt" style="border-color:#22D3EE;color:#7dd3fc;">UT 測厚取樣</button>
      <button type="button" id="btnOpenSopReport">檢視 / 下載 SOP 報告</button>
    </div>
  `;
  if (rightRack) rightRack.prepend(b2bSec);

  // Wave 3 /arena 3-Candidate HUD & Underwater Lighting Theme Engine (F2 or Pill switch)
  const arenaHud = installArenaHudThemes({ getState, getWorld });

  // SOP Evaluation Report Modal
  const modal = document.createElement('div');
  modal.className = 'w1-modal';
  modal.id = 'w1SopModal';
  modal.hidden = true;
  modal.innerHTML = `
    <div class="w1-modal-card">
      <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:10px;">
        <h3 style="margin:0;color:#22D3EE;">ROV-01 水下船體巡檢與超音波測厚 (UT) SOP 評估報告</h3>
        <button type="button" id="btnCloseSopModal">關閉 ×</button>
      </div>
      <div id="w1SopReportBody" style="font-size:12.5px;line-height:1.55;"></div>
      <div class="btns c2" style="margin-top:12px;">
        <button type="button" id="btnDownloadSopJson">下載 JSON 報告 (sop_evaluation_report.json)</button>
        <button type="button" id="btnDownloadSopHtml">下載 HTML 報告 (sop_evaluation_report.html)</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  // Wave 4+: NVIDIA Omniverse SimReady OpenUSD + @huggingface/usd-web-viewer Scene Manager & Inspector Overlay
  const simReadyMgr = new SimReadySceneManager();
  let selectedSimReadyId = 'SR-IND-03';
  let lastSyncedMission = null;

  const srOverlay = document.createElement('div');
  srOverlay.className = 'w1-sr-overlay';
  srOverlay.id = 'w1SimReadyModal';
  srOverlay.hidden = true;
  srOverlay.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <div>
        <div style="font-size:10px;color:#22D3EE;font-family:monospace;">NVIDIA Omniverse SimReady · @huggingface/usd-web-viewer</div>
        <h3 style="margin:0;font-size:13.5px;color:#f8fafc;">OpenUSD 水下工業物理資產庫 (8 Assets)</h3>
      </div>
      <div style="display:flex;gap:5px;align-items:center;">
        <a href="simready_preview.html" target="_blank" style="font-size:10.5px;color:#22D3EE;text-decoration:none;border:1px solid rgba(34,211,238,0.45);padding:2px 7px;border-radius:5px;background:rgba(34,211,238,0.1);">獨立檢視器 ↗</a>
        <button type="button" id="btnCloseSimReadyModal" style="padding:2px 7px;font-size:11px;">關閉 ×</button>
      </div>
    </div>
    <div style="display:flex;gap:8px;font-size:11px;margin-bottom:6px;background:rgba(15,23,42,0.75);padding:5px 8px;border-radius:6px;">
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="chkSrCollider" checked> <span style="color:#22D3EE;">Collision 碰撞框</span></label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="chkSrCoM" checked> <span style="color:#F59E0B;">CoM 質心軸</span></label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="chkSrAllMissions"> <span>同場顯示全部 8 件</span></label>
    </div>
    <div class="w1-sr-list" id="w1SrAssetList"></div>
    <div id="w1SrInspectorBody" style="font-size:11px;margin-top:6px;"></div>
    <div class="btns c3" style="margin-top:6px;">
      <button type="button" id="btnSrTeleport" style="border-color:#22D3EE;color:#7dd3fc;font-size:11px;">導航至資產</button>
      <button type="button" id="btnSrCollide" style="border-color:#F59E0B;color:#fde68a;font-size:11px;">UsdPhysics 碰撞測試</button>
      <button type="button" id="btnSrUtCouple" style="border-color:#10B981;color:#6ee7b7;font-size:11px;">UT 測厚耦合</button>
    </div>
    <div id="w1SrCollisionResult" style="font-size:10.5px;color:#fde68a;margin-top:5px;"></div>
    <div class="w1-sr-code" id="w1SrUsdaPreview"># Loading OpenUSD (.usda) stage schema...</div>
  `;
  document.body.appendChild(srOverlay);

  const renderSimReadyInspector = async (assetId) => {
    await simReadyMgr.loadCatalog();
    const assets = simReadyMgr.assets || [];
    const asset = assets.find((a) => a.asset_id === assetId) || assets[0];
    if (!asset) return;
    selectedSimReadyId = asset.asset_id;

    const listEl = $('w1SrAssetList');
    if (listEl) {
      listEl.innerHTML = assets.map((a) => `
        <button type="button" class="w1-sr-item ${a.asset_id === selectedSimReadyId ? 'active' : ''}" data-sr-id="${a.asset_id}">
          <b>${a.asset_id} [${a.mission_code}] ${a.ut_checkpoint_id ? '· ' + a.ut_checkpoint_id : ''}</b>
          <span>${a.title_zh}</span>
        </button>
      `).join('');
      listEl.querySelectorAll('.w1-sr-item').forEach((btn) => {
        btn.addEventListener('click', () => renderSimReadyInspector(btn.dataset.srId));
      });
    }

    const phys = asset.usd_physics || {};
    const bodyEl = $('w1SrInspectorBody');
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="w1-kv-grid">
          <div class="w1-kv"><span>HF SimReady Package (${asset.license})</span><b style="color:#22D3EE;font-family:monospace;font-size:10.5px;">${asset.hf_package}</b></div>
          <div class="w1-kv"><span>USD API Schemas</span><b style="font-size:10px;color:#a7f3d0;">CollisionAPI · MassAPI · MaterialAPI</b></div>
          <div class="w1-kv"><span>乾重 Mass / 水中淨重</span><b>${phys.mass_kg ?? asset.mass_kg} kg / ${phys.submerged_weight_n ?? 1600} N</b></div>
          <div class="w1-kv"><span>靜摩擦 μs / 動摩擦 μd / 彈性 e</span><b>${phys.static_friction ?? 0.65} / ${phys.dynamic_friction ?? 0.52} / ${phys.restitution ?? 0.16}</b></div>
          <div class="w1-kv"><span>質心 CoM (m) / 碰撞框尺寸 (m)</span><b>(${(phys.center_of_mass || [0,0,0]).join(', ')}) · ${(asset.bounding_box_size_m || [2,1.6,2]).join('×')}m</b></div>
          <div class="w1-kv"><span>B2B 超音波測厚標稱 / 實測壁厚</span><b style="color:#10B981;">${asset.ut_checkpoint_id || '結構件'}：${asset.ut_nominal_mm}mm → ${asset.ut_actual_mm}mm</b></div>
        </div>
      `;
    }

    try {
      const res = await fetch(`/api/simready/usd/${asset.asset_id}`);
      if (res.ok) {
        const data = await res.json();
        const codeEl = $('w1SrUsdaPreview');
        if (codeEl && data.raw_usda) {
          codeEl.textContent = data.raw_usda.trim();
        }
      }
    } catch {}
  };

  const focusCameraOnSimReadyAsset = (assetId) => {
    const v = window.__viewer;
    const asset = (simReadyMgr.assets || []).find((a) => a.asset_id === assetId);
    if (!v || !asset) return;
    const p = nedToThreeVec(v.THREE, asset.ned_pos);
    v.setCam?.('orbit');
    if (v.controls) {
      v.controls.target.copy(p);
      v.camera.position.set(p.x - 2.6, p.y + 1.4, p.z + 2.8);
      v.controls.update();
    }
  };

  const toggleSimReadyModal = async (forceOpen = null) => {
    const nextHidden = forceOpen !== null ? !forceOpen : !srOverlay.hidden;
    srOverlay.hidden = nextHidden;
    $('w1SimReadyBtn')?.classList.toggle('active', !nextHidden);
    if (!nextHidden) {
      await renderSimReadyInspector(selectedSimReadyId);
      if (window.__viewer) {
        simReadyMgr.syncMissionAssets(window.__viewer, lastSyncedMission || 'mission_2_hull_ut');
      }
    }
  };

  $('w1SimReadyBtn')?.addEventListener('click', () => toggleSimReadyModal());
  $('btnCloseSimReadyModal')?.addEventListener('click', () => toggleSimReadyModal(false));

  $('chkSrCollider')?.addEventListener('change', (e) => {
    simReadyMgr.setColliderVisible(e.target.checked);
  });
  $('chkSrCoM')?.addEventListener('change', (e) => {
    simReadyMgr.setCoMVisible(e.target.checked);
  });
  $('chkSrAllMissions')?.addEventListener('change', (e) => {
    simReadyMgr.setShowAllMissions(e.target.checked, window.__viewer);
  });

  $('btnSrTeleport')?.addEventListener('click', () => {
    send({ type: 'wave1', action: 'simready_teleport', asset_id: selectedSimReadyId });
    focusCameraOnSimReadyAsset(selectedSimReadyId);
  });

  $('btnSrCollide')?.addEventListener('click', async () => {
    send({ type: 'wave1', action: 'simready_collide', asset_id: selectedSimReadyId, impact_speed_mps: 0.95 });
    try {
      const res = await fetch('/api/simready/collide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_id: selectedSimReadyId, impact_speed_mps: 0.95 }),
      });
      if (res.ok) {
        const data = await res.json();
        const c = data.collision || {};
        const el = $('w1SrCollisionResult');
        if (el) {
          el.innerHTML = `⚡ <b>UsdPhysics 碰撞衝量結果 (${c.asset_id})</b>：法向衝量 <b>${c.normal_impulse_ns} N·s</b> · 摩擦衝量 <b>${c.friction_impulse_ns} N·s</b> · 反彈速度 <b>[${(c.rebound_velocity_ned || []).join(', ')}] m/s</b>`;
        }
      }
    } catch {}
  });

  $('btnSrUtCouple')?.addEventListener('click', () => {
    const asset = (simReadyMgr.assets || []).find((a) => a.asset_id === selectedSimReadyId);
    const cpId = asset?.ut_checkpoint_id || 'UT-SR-01';
    rovAudio.playSonarPing();
    send({ type: 'wave1', action: 'start_ut_coupling', checkpoint_id: cpId, tilt_deg: 1.2, distance_m: 0.38 });
    const el = $('w1SrCollisionResult');
    if (el) {
      el.innerHTML = `🟢 <b>UT 超音波探頭已耦合至 ${cpId}</b>：標稱 ${asset?.ut_nominal_mm ?? 14.0}mm / 實測 ${asset?.ut_actual_mm ?? 12.6}mm (定深保持 <3° 3.0s 鎖定)`;
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.code === 'F4') {
      e.preventDefault();
      toggleSimReadyModal();
    }
  });

  // Preload catalog and spawn initial mission SimReady assets
  simReadyMgr.loadCatalog().then(() => {
    if (window.__viewer) {
      simReadyMgr.syncMissionAssets(window.__viewer, getState()?.wave1?.mission_id || 'mission_1_pool');
    }
  });

  // Wire mission selector buttons
  const selectMission = (missionId) => {
    document.querySelectorAll('#w1MissionButtons .w1-mbtn').forEach((b) => {
      b.classList.toggle('active', b.dataset.missionId === missionId);
    });
    send({ type: 'wave1', action: 'select_mission', mission_id: missionId, seed: 42 });
  };
  document.querySelectorAll('#w1MissionButtons .w1-mbtn').forEach((btn) => {
    btn.addEventListener('click', () => selectMission(btn.dataset.missionId));
  });

  // Wire Deadzone & Expo sliders
  let deadzone = 0.08;
  let expo = 0.35;
  $('w1Deadzone')?.addEventListener('input', (e) => {
    deadzone = sanitize(e.target.value, expo)[0];
    setShaping({ deadzone, expo });
    $('w1DzVal').textContent = deadzone.toFixed(2);
    send({ type: 'wave1', action: 'gamepad_6dof', axes: {}, deadzone, expo });
  });
  $('w1Expo')?.addEventListener('input', (e) => {
    expo = sanitize(deadzone, e.target.value)[1];
    setShaping({ deadzone, expo });
    $('w1ExpoVal').textContent = expo.toFixed(2);
    send({ type: 'wave1', action: 'gamepad_6dof', axes: {}, deadzone, expo });
  });

  // Wire Thruster Fault buttons
  document.querySelectorAll('#w1ThrFaultGrid .w1-tbtn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.faultIdx, 10);
      const isFaulted = btn.classList.contains('faulted');
      send({ type: 'wave1', action: 'inject_fault', thruster_index: idx, jammed: !isFaulted });
    });
  });
  $('btnInjectT3Fault')?.addEventListener('click', () => {
    send({ type: 'wave1', action: 'inject_fault', thruster_index: 2, jammed: true });
  });
  $('btnClearFaults')?.addEventListener('click', () => {
    send({ type: 'wave1', action: 'clear_faults' });
  });

  // Wire Emergency RTH & Collision Test & UT Sample
  let rthEnabled = false;
  $('btnEmergencyRth')?.addEventListener('click', () => {
    rthEnabled = !rthEnabled;
    send({ type: 'wave1', action: 'emergency_return', enable: rthEnabled });
  });
  $('btnSimCollision')?.addEventListener('click', () => {
    send({ type: 'wave1', action: 'collision_impulse', speed_mps: 0.92, zone: 'front-stbd' });
  });
  $('btnSampleUt')?.addEventListener('click', () => {
    rovAudio.playSonarPing();
    send({ type: 'wave1', action: 'sample_ut' });
  });

  let depthHoldEnabled = false;
  let headingHoldEnabled = false;
  let surfaceEnabled = false;
  $('btnDepthHold')?.addEventListener('click', () => {
    depthHoldEnabled = !depthHoldEnabled;
    send({ type: 'wave1', action: 'depth_hold', enable: depthHoldEnabled });
  });
  $('btnHeadingHold')?.addEventListener('click', () => {
    headingHoldEnabled = !headingHoldEnabled;
    send({ type: 'wave1', action: 'heading_hold', enable: headingHoldEnabled });
  });
  $('btnEmergencySurface')?.addEventListener('click', () => {
    surfaceEnabled = !surfaceEnabled;
    send({ type: 'wave1', action: 'emergency_surface', enable: surfaceEnabled });
  });
  $('btnResolveSnag')?.addEventListener('click', () => {
    send({ type: 'wave1', action: 'resolve_tether_snag' });
  });

  // SOP Report Modal & Download
  const renderSopReportHtml = (rep) => {
    if (!rep) return '<p>尚無評估資料</p>';
    const m = rep.metrics || {};
    const b = rep.breakdown || {};
    const rows = (rep.ut_checkpoints || []).map((c) => `
      <tr>
        <td><b>${c.id}</b> · ${c.label}</td>
        <td>${c.nominal_mm.toFixed(1)} mm</td>
        <td><b>${c.measured_mm.toFixed(1)} mm</b></td>
        <td>${c.diminution_pct.toFixed(1)}%</td>
        <td>${c.completed ? `<span style="color:#10b981;font-weight:700;">已測厚 (${c.status})</span>` : '<span style="color:#94a3b8;">待測</span>'}</td>
      </tr>
    `).join('');
    return `
      <div style="display:flex;justify-content:space-between;align-items:center;background:#0f2438;padding:10px 14px;border-radius:8px;margin-bottom:10px;">
        <div>
          <div style="font-size:11px;color:#7dd3fc;">${rep.report_version} · ${rep.vehicle_model}</div>
          <div style="font-size:15px;font-weight:700;">${rep.mission_title}</div>
          <div style="font-size:12px;color:#fde047;">評等：${rep.grade}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:28px;font-weight:800;color:#22D3EE;">${rep.total_score.toFixed(1)} <small style="font-size:13px;">/ 100</small></div>
          <div style="font-size:11px;color:#94a3b8;">任務時間 ${rep.elapsed_s}s</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px;font-size:11.5px;">
        <div style="background:#112233;padding:6px 8px;border-radius:6px;">航點與 UT 完成度<br><b style="color:#22D3EE;">${b.waypoint_ut_completion_pts} / 40</b></div>
        <div style="background:#112233;padding:6px 8px;border-radius:6px;">定深與航向穩定度<br><b style="color:#22D3EE;">${b.stability_hold_pts} / 25</b></div>
        <div style="background:#112233;padding:6px 8px;border-radius:6px;">機體無碰撞安全分<br><b style="color:#22D3EE;">${b.hull_integrity_safety_pts} / 20</b></div>
        <div style="background:#112233;padding:6px 8px;border-radius:6px;">單推進器失效應變<br><b style="color:#22D3EE;">${b.fault_compensation_rth_pts} / 15</b></div>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;">
        <thead><tr style="border-bottom:1px solid #334155;color:#94a3b8;text-align:left;">
          <th style="padding:4px;">UT 測厚檢查點</th><th>標稱厚度</th><th>實測厚度</th><th>減薄率</th><th>狀態</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div style="font-size:11.5px;color:#cbd5e1;">
        定深穩定度：<b>${m.depth_hold_stability_pct}%</b> · 航向穩定度：<b>${m.heading_stability_pct}%</b> · 碰撞次數：<b>${m.collision_count}</b> · 機體完整度：<b>${m.hull_integrity_pct}%</b> · 失效推進器：<b>${(m.faulted_thrusters || []).join(', ') || '無'}</b> · 緊急返航耗時：<b>${m.emergency_return_time_s != null ? m.emergency_return_time_s + 's' : 'N/A'}</b>
      </div>
    `;
  };

  $('btnOpenSopReport')?.addEventListener('click', () => {
    const rep = getState()?.wave1?.sop_evaluation;
    $('w1SopReportBody').innerHTML = renderSopReportHtml(rep);
    modal.hidden = false;
  });
  $('btnCloseSopModal')?.addEventListener('click', () => { modal.hidden = true; });

  const downloadBlob = (filename, content, mime) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2500);
  };
  $('btnDownloadSopJson')?.addEventListener('click', () => {
    const rep = getState()?.wave1?.sop_evaluation || {};
    downloadBlob('sop_evaluation_report.json', JSON.stringify(rep, null, 2), 'application/json');
  });
  $('btnDownloadSopHtml')?.addEventListener('click', () => {
    const rep = getState()?.wave1?.sop_evaluation || {};
    const html = `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>ROV-01 SOP Evaluation Report</title></head><body style="background:#061320;color:#e2e8f0;font-family:sans-serif;padding:24px;">${renderSopReportHtml(rep)}</body></html>`;
    downloadBlob('sop_evaluation_report.html', html, 'text/html');
  });

  // Expose programmatic E2E helpers on window.__wave1
  window.__wave1 = {
    selectMission,
    inject6Dof(axes, dz = deadzone, ex = expo) {
      send({ type: 'wave1', action: 'gamepad_6dof', axes, deadzone: dz, expo: ex });
    },
    injectThrusterFault(index = 2, jammed = true) {
      send({ type: 'wave1', action: 'inject_fault', thruster_index: index, jammed });
    },
    clearFaults() {
      send({ type: 'wave1', action: 'clear_faults' });
    },
    triggerEmergencyReturn(enable = true) {
      rthEnabled = enable;
      send({ type: 'wave1', action: 'emergency_return', enable });
    },
    injectCollision(speed_mps = 0.9, zone = 'front-stbd') {
      send({ type: 'wave1', action: 'collision_impulse', speed_mps, zone });
    },
    sampleUt(checkpoint_id = null) {
      rovAudio.playSonarPing();
      send({ type: 'wave1', action: 'sample_ut', checkpoint_id });
    },
    startUtCoupling(checkpoint_id = null, tilt_deg = 1.4, distance_m = 0.42) {
      rovAudio.playSonarPing();
      send({ type: 'wave1', action: 'start_ut_coupling', checkpoint_id, tilt_deg, distance_m });
    },
    setDepthHold(enable = true, target_depth_m = null) {
      depthHoldEnabled = !!enable;
      send({ type: 'wave1', action: 'depth_hold', enable, target_depth_m });
    },
    setHeadingHold(enable = true, target_heading_deg = null) {
      headingHoldEnabled = !!enable;
      send({ type: 'wave1', action: 'heading_hold', enable, target_heading_deg });
    },
    triggerEmergencySurface(enable = true) {
      surfaceEnabled = !!enable;
      send({ type: 'wave1', action: 'emergency_surface', enable });
    },
    injectTetherSnag() {
      send({ type: 'wave1', action: 'inject_tether_snag' });
    },
    resolveTetherSnag() {
      send({ type: 'wave1', action: 'resolve_tether_snag' });
    },
    audio: rovAudio,
    arenaHud,
    setHudTheme(presetId) {
      return arenaHud.setPreset(presetId);
    },
    cycleHudTheme() {
      return arenaHud.cyclePreset();
    },
    getHudTheme() {
      return arenaHud.getPreset();
    },
    simReadyMgr,
    openSimReadyModal: (assetId = null) => {
      if (assetId) selectedSimReadyId = assetId;
      return toggleSimReadyModal(true);
    },
    closeSimReadyModal: () => toggleSimReadyModal(false),
    focusSimReadyAsset: focusCameraOnSimReadyAsset,
    collideSimReadyAsset: (assetId = 'SR-IND-03', speed = 0.95) => {
      send({ type: 'wave1', action: 'simready_collide', asset_id: assetId, impact_speed_mps: speed });
    },
    campaign: null,
    jumpToCampaignStage: (stageNum = 1) => campaignUI.jumpToCampaignStage(stageNum),
    triggerStageInteraction: () => campaignUI.triggerStageInteraction(),
    teleportSimReadyAsset: (assetId = 'SR-IND-03') => {
      send({ type: 'wave1', action: 'simready_teleport', asset_id: assetId });
      focusCameraOnSimReadyAsset(assetId);
    },
    getSopReport() {
      return getState()?.wave1?.sop_evaluation || null;
    },
  };

  const campaignUI = installCableCampaign({ send, getState });
  window.__wave1.campaign = campaignUI;

  return {
    update(s, dt = 0.033) {
      if (!s) return;
      // Sync Web Audio procedural synthesizer
      rovAudio.syncWithTelemetry(s);
      arenaHud.update(s, dt);
      campaignUI.update(s, dt);

      // Update 3D ROV-01 mesh thruster plumes & fault ring highlights
      // Art Director Fix #1: M1/M3/M4 lock UT probe ring to 'searching' (#22D3EE Sonar Cyan) when uncoupled/standby
      const model = getActiveModel?.();
      if (model?.updateThrusters) {
        const utState = s.wave1?.wave3?.ut_ring_state || 'searching';
        model.updateThrusters(s.thrust || [0, 0, 0, 0, 0, 0], dt, s.health || [1, 1, 1, 1, 1, 1], utState);
      }

      const w1 = s.wave1;
      if (!w1) return;

      const w3 = w1.wave3 || {};
      const pidEl = $('w3PidErrVal');
      if (pidEl) {
        const dErr = Number(w3.depth_hold_error_m || 0).toFixed(2);
        const hErr = Number(w3.heading_hold_error_deg || 0).toFixed(1);
        pidEl.textContent = `${dErr}m / ${hErr}°`;
      }
      const utHoldEl = $('w3UtHoldVal');
      if (utHoldEl) {
        const stLabel = (w3.ut_state || 'ut_searching').replace('ut_', '').toUpperCase();
        utHoldEl.textContent = `${stLabel} (${Number(w3.ut_hold_elapsed_s || 0).toFixed(1)}/3.0s)`;
      }

      // Mission active state + SimReady OpenUSD 3D Stage sync
      const mId = w1.mission_id || getWorld()?.scenario?.key || 'mission_1_pool';
      if (window.__viewer && simReadyMgr.assets.length && (lastSyncedMission !== mId || !simReadyMgr.group)) {
        lastSyncedMission = mId;
        simReadyMgr.syncMissionAssets(window.__viewer, mId);
      }
      const mMeta = (w1.mission_catalog || []).find((m) => m.id === mId);
      if (mMeta) {
        $('w1ActiveMissionCode').textContent = mMeta.code;
        $('w1BannerMission').textContent = `${mMeta.title} (${mMeta.subtitle})`;
      }
      document.querySelectorAll('#w1MissionButtons .w1-mbtn').forEach((b) => {
        b.classList.toggle('active', b.dataset.missionId === mId);
      });

      // 6DoF telemetry bars (use shaped_6dof if non-zero, otherwise derive from RC sticks)
      const rc = s.rc || {};
      const rcAxes = {
        surge: ((rc.left_ud || 1500) - 1500) / 500,
        sway: ((rc.left_lr || 1500) - 1500) / 500,
        heave: ((rc.right_ud || 1500) - 1500) / 500,
        roll: ((rc.right_wave || 1500) - 1500) / 500,
        pitch: ((rc.left_wave || 1500) - 1500) / 500,
        yaw: ((rc.right_lr || 1500) - 1500) / 500,
      };
      const shaped = w1.gamepad?.shaped_6dof || {};
      for (const k of ['surge', 'sway', 'heave', 'roll', 'pitch', 'yaw']) {
        const val = Math.abs(shaped[k] || 0) > 0.001 ? shaped[k] : applyDeadzoneAndExpoJS(rcAxes[k], deadzone, expo);
        const lbl = $(`w1Dof_${k}`);
        const bar = $(`w1Bar_${k}`);
        if (lbl) lbl.textContent = (val >= 0 ? '+' : '') + val.toFixed(2);
        if (bar) {
          bar.style.width = `${Math.min(100, Math.abs(val) * 100)}%`;
          bar.style.background = val < 0 ? '#f59e0b' : '#22D3EE';
        }
      }

      // Thruster health & reallocation status
      const health = s.health || [1, 1, 1, 1, 1, 1];
      const thrust = s.thrust || [0, 0, 0, 0, 0, 0];
      const faulted = w1.thrusters?.faulted_indices || [];
      document.querySelectorAll('#w1ThrFaultGrid .w1-tbtn').forEach((btn) => {
        const idx = parseInt(btn.dataset.faultIdx, 10);
        const h = health[idx] ?? 1;
        const t = thrust[idx] ?? 0;
        const isFault = h <= 0.15 || faulted.includes(idx);
        btn.classList.toggle('faulted', isFault);
        const sub = $(`w1Th_${idx}`);
        if (sub) sub.textContent = isFault ? 'FAULT 0%' : `${Math.round(Math.abs(t) * 100)}%`;
      });

      const reallocBadge = $('w1ReallocBadge');
      if (reallocBadge) {
        if (w1.thrusters?.reallocation_active) {
          reallocBadge.className = 'w1-badge fault';
          reallocBadge.textContent = `⚠️ ${w1.thrusters.faulted_names.join(',')} 失效 · 5 推進器重分配中`;
        } else {
          reallocBadge.className = 'w1-badge ok';
          reallocBadge.textContent = '6 推進器向量正常';
        }
      }

      // Hazards & State Machine Banner
      const hz = w1.hazards || {};
      const stBanner = $('w1BannerState');
      if (stBanner) {
        stBanner.textContent = `STATE: ${(w1.mode_state || 'normal').toUpperCase()}`;
        stBanner.className = 'w1-badge ' + (
          w1.mode_state === 'normal' ? 'ok' :
          w1.mode_state === 'emergency_return' ? 'warn' : 'fault'
        );
      }
      const hullPct = hz.hull_integrity ?? 100;
      $('w1BannerHull').textContent = `機體完整度 ${hullPct.toFixed(1)}%`;
      $('w1HullVal').textContent = `${hullPct.toFixed(1)}% (${hz.collision_count || 0} 碰撞)`;
      $('w1HullVal').style.color = hullPct <= 50 ? '#EF4444' : hullPct < 90 ? '#F59E0B' : '#6ee7b7';
      $('w1TurbVal').textContent = `${(hz.turbidity_ntu ?? 1.2).toFixed(1)} NTU / ${(hz.visibility_m ?? 12).toFixed(1)}m`;

      const sop = w1.sop_evaluation || {};
      const sm = sop.metrics || {};
      $('w1StabVal').textContent = `${(sm.depth_hold_stability_pct ?? 96).toFixed(1)}% / ${(sm.heading_stability_pct ?? 95).toFixed(1)}%`;
      rthEnabled = !!hz.emergency_return_active;
      $('btnEmergencyRth').textContent = rthEnabled ? '⚡ 緊急返航導引中 (點擊取消)' : '啟動緊急返航 (RTH)';
      $('w1RthVal').textContent = hz.emergency_return_completed
        ? `已完成 (${hz.emergency_return_time_s}s)`
        : rthEnabled
          ? `返航中 (${hz.emergency_return_time_s || 0}s)`
          : '待命';

      // SOP Score & UT Checkpoints
      const scoreBadge = $('w1SopScoreBadge');
      if (scoreBadge && sop.total_score != null) {
        scoreBadge.textContent = `SOP ${sop.total_score.toFixed(1)} 分`;
      }
      const utList = $('w1UtList');
      if (utList && sop.ut_checkpoints) {
        utList.innerHTML = sop.ut_checkpoints.map((c) => `
          <li class="${c.completed ? 'done' : ''} ${c.status === 'WARN_CORROSION' ? 'warn' : ''}">
            <span><b>${c.id}</b> ${c.label.replace(/^UT-\d+\s*/, '')}</span>
            <span>${c.completed ? `<b>${c.measured_mm.toFixed(1)}mm</b> (-${c.diminution_pct}%)` : '待測厚'}</span>
          </li>
        `).join('');
      }
    },
  };
}
