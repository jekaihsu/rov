/*
 * Operation: Deep Link — 海底主幹電纜緊急搶修連貫戰役 (Seamless 4-Stage Cohesive Subsea Cable Campaign)
 * Implements JK's priority gameplay direction (t949u, t950u):
 *  - Stage 1 (LOCATE): 3D Glowing Sonar Waypoint Rings + Sonar Pulse Wave
 *  - Stage 2 (RETRIEVE & TOW): Fallen Industrial Rack Debris + Manipulator Target Lock Reticle + Live 3D Catenary Cable Dragging
 *  - Stage 3 (REPAIR & SECURE): SimReady Subsea Splice Box & Clamp Manifold + 3-Step Underwater Welding/Spark & Cavitation Bubble Particles
 *  - Stage 4 (ENERGIZE & EXTRACT): 400kV/100Gbps Full-Seabed Cable Re-energized Light Pulse + Subsea TMS Recovery Cage + S-Rank Victory Overlay
 *  - Immersive Game HUD: #deepLinkObjectiveBar, #radioCommsOverlay (Bridge Commander CH-16), and Off-Screen 3D Target Direction Indicator
 */

import { nedToThreeVec } from './simready_usd_loader.js';
import { rovAudio } from './rov_audio.js';

const $ = (id) => document.getElementById(id);

export function installCableCampaign({ send, getState }) {
  const style = document.createElement('style');
  style.textContent = `
    #deepLinkObjectiveBar {
      position: fixed;
      top: 90px;
      left: 50%;
      transform: translateX(-50%);
      width: min(690px, 62vw);
      background: linear-gradient(180deg, rgba(6, 18, 34, 0.94) 0%, rgba(4, 12, 24, 0.90) 100%);
      border: 1px solid rgba(34, 211, 238, 0.65);
      border-radius: 10px;
      padding: 8px 14px;
      color: #f8fafc;
      z-index: 42;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.65), 0 0 18px rgba(34, 211, 238, 0.18);
      pointer-events: auto;
    }
    .dl-top-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
    }
    .dl-stage-pills {
      display: flex;
      gap: 4px;
    }
    .dl-spill {
      padding: 2px 8px;
      border-radius: 5px;
      font-size: 10.5px;
      font-weight: 700;
      font-family: monospace;
      background: rgba(15, 32, 52, 0.9);
      color: #94a3b8;
      border: 1px solid rgba(148, 163, 184, 0.28);
      cursor: pointer;
    }
    .dl-spill.active {
      background: rgba(34, 211, 238, 0.22);
      color: #22D3EE;
      border-color: #22D3EE;
      box-shadow: 0 0 8px rgba(34, 211, 238, 0.35);
    }
    .dl-spill.done {
      background: rgba(16, 185, 129, 0.2);
      color: #6ee7b7;
      border-color: #10B981;
    }
    .dl-obj-text {
      font-size: 12.5px;
      font-weight: 700;
      color: #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }
    .dl-prog-track {
      height: 6px;
      background: rgba(30, 41, 59, 0.9);
      border-radius: 99px;
      overflow: hidden;
      margin-top: 5px;
      border: 1px solid rgba(56, 189, 248, 0.25);
    }
    .dl-prog-fill {
      height: 100%;
      background: linear-gradient(90deg, #06B6D4, #10B981);
      width: 20%;
      transition: width 0.2s ease;
    }
    #deepLinkTargetReticle {
      position: fixed;
      top: 52%;
      left: 50%;
      transform: translate(-50%, -50%);
      pointer-events: auto;
      z-index: 44;
      text-align: center;
    }
    #deepLinkTargetReticle[hidden] { display: none !important; }
    .dl-reticle-box {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      background: rgba(6, 20, 36, 0.88);
      border: 2px solid #22D3EE;
      border-radius: 10px;
      padding: 8px 16px;
      box-shadow: 0 0 24px rgba(34, 211, 238, 0.45);
      cursor: pointer;
    }
    .dl-reticle-box.grabbed {
      border-color: #F59E0B;
      box-shadow: 0 0 24px rgba(245, 158, 11, 0.45);
    }
    .dl-reticle-box.energized {
      border-color: #10B981;
      box-shadow: 0 0 26px rgba(16, 185, 129, 0.55);
    }
    #radioCommsOverlay {
      position: fixed;
      bottom: 18px;
      left: 50%;
      transform: translateX(-50%);
      width: min(680px, 60vw);
      background: rgba(5, 15, 28, 0.93);
      border: 1px solid rgba(34, 211, 238, 0.55);
      border-left: 4px solid #22D3EE;
      border-radius: 8px;
      padding: 8px 14px;
      display: flex;
      align-items: center;
      gap: 12px;
      z-index: 43;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
      pointer-events: auto;
    }
    .dl- portrait {
      width: 42px;
      height: 42px;
      border-radius: 8px;
      background: radial-gradient(circle, #0e3a5c 0%, #061526 100%);
      border: 1px solid #22D3EE;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: monospace;
      font-weight: 800;
      font-size: 11px;
      color: #22D3EE;
      flex-shrink: 0;
    }
    #deepLinkVictoryOverlay {
      position: fixed;
      inset: 0;
      background: rgba(2, 8, 18, 0.78);
      z-index: 95;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: auto;
    }
    #deepLinkVictoryOverlay[hidden] { display: none !important; }
    .dl-victory-card {
      width: min(580px, 92vw);
      background: linear-gradient(180deg, rgba(8, 25, 44, 0.97) 0%, rgba(4, 14, 26, 0.98) 100%);
      border: 2px solid #10B981;
      border-radius: 14px;
      padding: 20px 24px;
      color: #f8fafc;
      box-shadow: 0 0 50px rgba(16, 185, 129, 0.45);
    }
  `;
  document.head.appendChild(style);

  // 1. Top Dynamic Objective Bar (#deepLinkObjectiveBar)
  const objBar = document.createElement('div');
  objBar.id = 'deepLinkObjectiveBar';
  objBar.innerHTML = `
    <div class="dl-top-row">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:11px;font-weight:800;color:#22D3EE;font-family:monospace;">⚡ OPERATION: DEEP LINK</span>
        <span id="dlStageTitle" style="font-size:12px;font-weight:700;color:#fde047;">STAGE 1/4：下潛與聲納尋纜 (LOCATE)</span>
      </div>
      <div class="dl-stage-pills" id="dlStagePills">
        <button type="button" class="dl-spill active" data-stage="1" title="切換至 Stage 1：聲納尋纜">S1 尋纜</button>
        <button type="button" class="dl-spill" data-stage="2" title="切換至 Stage 2：機械手臂夾電纜">S2 撿電纜</button>
        <button type="button" class="dl-spill" data-stage="3" title="切換至 Stage 3：接頭盒搶修鎖固">S3 搶修</button>
        <button type="button" class="dl-spill" data-stage="4" title="切換至 Stage 4：全線通電與吊籠回收">S4 通電回收</button>
      </div>
    </div>
    <div class="dl-obj-text">
      <span id="dlObjectiveDesc">穿越 3 座聲納導引光圈，下潛定位 B 區海底主幹光電複合纜斷訊點</span>
      <span style="font-family:monospace;font-size:12px;color:#22D3EE;white-space:nowrap;" id="dlTargetBearing">🎯 距離目標 2.4m ▲</span>
    </div>
    <div class="dl-prog-track"><div class="dl-prog-fill" id="dlOverallProgFill"></div></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:5px;font-size:11px;color:#94a3b8;">
      <span id="dlCableStatusTag">海纜狀態：<b style="color:#F59E0B;">斷落待拾取 (Dislodged)</b> · 懸鏈張力 <b id="dlTensionVal">42.0 N</b></span>
      <div style="display:flex;gap:6px;">
        <button type="button" id="btnDlInteract" style="padding:2px 10px;font-size:11px;font-weight:700;border-radius:5px;border:1px solid #22D3EE;background:rgba(34,211,238,0.18);color:#f8fafc;cursor:pointer;">[E] 執行當前階段互動</button>
      </div>
    </div>
  `;
  document.body.appendChild(objBar);

  // 2. Center 3D Target Reticle & Interactive Action Prompt (#deepLinkTargetReticle)
  const reticle = document.createElement('div');
  reticle.id = 'deepLinkTargetReticle';
  reticle.innerHTML = `
    <div class="dl-reticle-box" id="dlReticleCard">
      <div style="font-family:monospace;font-size:11px;color:#22D3EE;font-weight:800;" id="dlReticleHeader">[TARGET LOCKED · SIMREADY SUBSEA CABLE]</div>
      <div style="font-size:13.5px;font-weight:800;color:#f8fafc;margin:2px 0;" id="dlReticlePrompt">[E] / [Space] 機械手臂夾取斷落海纜 (GRAB CABLE)</div>
      <div style="font-size:11px;color:#cbd5e1;" id="dlReticleSub">距離 1.8m · 機械手臂夾爪就緒 · 懸鏈物理即時演算</div>
    </div>
  `;
  document.body.appendChild(reticle);

  // 3. Bridge Commander Radio Comms Overlay (#radioCommsOverlay)
  const commsBox = document.createElement('div');
  commsBox.id = 'radioCommsOverlay';
  commsBox.innerHTML = `
    <div class="dl-portrait" id="dlCommsBadge">CH-16<br>BRIDGE</div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#22D3EE;font-weight:700;">
        <span id="dlCommsSpeaker">母船指揮官 CH-16 (Mother Vessel Bridge)</span>
        <span style="font-family:monospace;color:#10B981;" id="dlPowerLinkBadge">LINK: STANDBY</span>
      </div>
      <div style="font-size:12.5px;color:#f8fafc;margin-top:2px;line-height:1.35;" id="dlCommsText">
        「ROV-01 注意，B 區海底主幹複合電纜訊號中斷！請順著聲納導引光圈下潛至 5.2m 斷纜座標！」
      </div>
    </div>
  `;
  document.body.appendChild(commsBox);

  // 4. Stage 4 Campaign Victory Overlay (#deepLinkVictoryOverlay)
  let lastCampaignCompleted = false;
  const victoryModal = document.createElement('div');
  victoryModal.id = 'deepLinkVictoryOverlay';
  victoryModal.hidden = true;
  victoryModal.innerHTML = `
    <div class="dl-victory-card">
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(16,185,129,0.35);padding-bottom:10px;margin-bottom:12px;">
        <div>
          <div style="font-family:monospace;font-size:11.5px;color:#10B981;font-weight:800;">⚡ SIGNAL RESTORED: 100% — 400kV / 100Gbps ONLINE</div>
          <h2 style="margin:3px 0 0;font-size:18px;color:#f8fafc;">深海連線戰役完成 (Operation: Deep Link Cleared)</h2>
        </div>
        <div style="text-align:right;">
          <div style="font-size:32px;font-weight:900;color:#fde047;line-height:1;" id="dlVictoryRank">—</div>
          <div style="font-size:11px;color:#6ee7b7;" id="dlVictoryScore">— / 100 分</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;margin-bottom:14px;">
        <div style="background:rgba(15,28,46,0.9);padding:8px 10px;border-radius:8px;border:1px solid rgba(34,211,238,0.3);">
          <span style="color:#94a3b8;font-size:10.5px;display:block;">Stage 1 & 2 尋纜與懸鏈拖曳</span>
          <b style="color:#22D3EE;">3/3 聲納光圈 · 海纜精準入座</b>
        </div>
        <div style="background:rgba(15,28,46,0.9);padding:8px 10px;border-radius:8px;border:1px solid rgba(34,211,238,0.3);">
          <span style="color:#94a3b8;font-size:10.5px;display:block;">Stage 3 SimReady 接頭盒三段式搶修</span>
          <b style="color:#10B981;">100% 鎖固 (240 N·m 扭力合格)</b>
        </div>
        <div style="background:rgba(15,28,46,0.9);padding:8px 10px;border-radius:8px;border:1px solid rgba(34,211,238,0.3);">
          <span style="color:#94a3b8;font-size:10.5px;display:block;">Stage 4 全線通電脈衝與 TMS 吊籠回收</span>
          <b style="color:#fde047;">400kV 主幹光電複合纜通電完成</b>
        </div>
        <div style="background:rgba(15,28,46,0.9);padding:8px 10px;border-radius:8px;border:1px solid rgba(34,211,238,0.3);">
          <span style="color:#94a3b8;font-size:10.5px;display:block;">Steam 成就解鎖</span>
          <b style="color:#6ee7b7;">🏆 DEEP_LINK_CABLE_MASTER</b>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:8px;">
        <button type="button" id="btnReplayCampaign" style="padding:6px 14px;border-radius:6px;border:1px solid #22D3EE;background:rgba(34,211,238,0.18);color:#f8fafc;cursor:pointer;font-weight:700;">重玩連貫戰役</button>
        <button type="button" id="btnCloseVictory" style="padding:6px 14px;border-radius:6px;border:1px solid #10B981;background:rgba(16,185,129,0.25);color:#f8fafc;cursor:pointer;font-weight:700;">繼續自由巡檢 ×</button>
      </div>
    </div>
  `;
  document.body.appendChild(victoryModal);

  // 3D Scene Objects for the Seamless Subsea Cable Campaign
  let campaignGroup = null;
  let sonarRingsGroup = null;
  let trunkCableMesh = null;
  let dynamicCableLine = null;
  let dynamicCableTube = null;
  let spliceBoxGroup = null;
  let sparkParticles = null;
  let energizePulseSpheres = [];
  let tmsCageGroup = null;
  let gripperClawVisual = null;
  let animTime = 0;

  function ensure3DCampaignObjects(viewer) {
    if (!viewer || !viewer.THREE || !viewer.scene) return null;
    const THREE = viewer.THREE;
    if (campaignGroup && campaignGroup.parent === viewer.scene) return campaignGroup;

    campaignGroup = new THREE.Group();
    campaignGroup.name = 'OperationDeepLinkCampaignGroup';
    viewer.scene.add(campaignGroup);

    // 1. Stage 1: 3 Glowing Sonar Guidance Waypoint Rings
    sonarRingsGroup = new THREE.Group();
    sonarRingsGroup.name = 'Stage1_SonarWaypointRings';
    const ringCoords = [
      [2.2, -0.6, 3.0],
      [3.4, -1.1, 4.2],
      [4.5, -1.5, 5.2],
    ];
    ringCoords.forEach((ned, idx) => {
      const rg = new THREE.Group();
      rg.position.copy(nedToThreeVec(THREE, ned));
      const torus = new THREE.Mesh(
        new THREE.TorusGeometry(1.15, 0.055, 16, 48),
        new THREE.MeshBasicMaterial({ color: idx === 0 ? 0x22d3ee : 0x38bdf8 })
      );
      torus.rotation.y = Math.PI * 0.15;
      rg.add(torus);

      const outerHalo = new THREE.Mesh(
        new THREE.TorusGeometry(1.32, 0.02, 12, 48),
        new THREE.MeshBasicMaterial({ color: 0x10b981, transparent: true, opacity: 0.65 })
      );
      outerHalo.rotation.y = Math.PI * 0.15;
      rg.add(outerHalo);
      rg.userData = { ringIndex: idx, torus, outerHalo };
      sonarRingsGroup.add(rg);
    });
    campaignGroup.add(sonarRingsGroup);

    // 2. Fixed Seabed Trunk Cable Corridor + Splice Saddle Cradle (at NED [9.2, -1.8, 6.8])
    spliceBoxGroup = new THREE.Group();
    spliceBoxGroup.name = 'Stage2_3_SpliceJunctionSaddle';
    const saddlePos = nedToThreeVec(THREE, [9.2, -1.8, 6.8]);
    spliceBoxGroup.position.copy(saddlePos);

    const cradleBase = new THREE.Mesh(
      new THREE.BoxGeometry(2.4, 0.32, 1.65),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.4, metalness: 0.65 })
    );
    cradleBase.position.set(0, -0.35, 0);
    spliceBoxGroup.add(cradleBase);

    const spliceChamber = new THREE.Mesh(
      new THREE.CylinderGeometry(0.32, 0.32, 1.6, 24),
      new THREE.MeshStandardMaterial({ color: 0x06b6d4, roughness: 0.3, metalness: 0.72 })
    );
    spliceChamber.rotation.z = Math.PI / 2;
    spliceBoxGroup.add(spliceChamber);

    for (const cx of [-0.55, 0, 0.55]) {
      const clampCollar = new THREE.Mesh(
        new THREE.TorusGeometry(0.38, 0.055, 14, 28),
        new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.28, metalness: 0.78 })
      );
      clampCollar.rotation.y = Math.PI / 2;
      clampCollar.position.set(cx, 0, 0);
      spliceBoxGroup.add(clampCollar);
    }

    const saddleBeacon = new THREE.Mesh(
      new THREE.TorusGeometry(0.85, 0.04, 14, 40),
      new THREE.MeshBasicMaterial({ color: 0x22d3ee })
    );
    saddleBeacon.rotation.x = Math.PI / 2;
    saddleBeacon.position.set(0, 0.55, 0);
    spliceBoxGroup.add(saddleBeacon);
    spliceBoxGroup.userData.saddleBeacon = saddleBeacon;
    campaignGroup.add(spliceBoxGroup);

    // 3. Stage 3 Underwater Repair Welding Spark & Cavitation Bubble Particle Burst
    sparkParticles = new THREE.Group();
    sparkParticles.name = 'Stage3_RepairSparksAndBubbles';
    sparkParticles.position.copy(saddlePos);
    for (let i = 0; i < 36; i++) {
      const isSpark = i % 2 === 0;
      const pMesh = new THREE.Mesh(
        new THREE.SphereGeometry(isSpark ? 0.045 : 0.06, 8, 8),
        new THREE.MeshBasicMaterial({ color: isSpark ? 0xfde047 : 0x22d3ee })
      );
      pMesh.userData = {
        phase: (i / 36) * Math.PI * 2,
        radius: 0.25 + (i % 7) * 0.11,
        speed: 2.2 + (i % 5) * 0.6,
        isSpark,
      };
      sparkParticles.add(pMesh);
    }
    sparkParticles.visible = false;
    campaignGroup.add(sparkParticles);

    // 4. Stage 4 Re-Energized Trunk Cable Network & Traveling Power Pulse Spheres
    const trunkCurvePoints = [
      nedToThreeVec(THREE, [0.5, 4.2, 6.9]),
      nedToThreeVec(THREE, [3.2, 2.8, 6.9]),
      nedToThreeVec(THREE, [9.2, -1.8, 6.8]),
      nedToThreeVec(THREE, [14.5, -3.5, 6.9]),
    ];
    const trunkCurve = new THREE.CatmullRomCurve3(trunkCurvePoints);
    const trunkGeo = new THREE.TubeGeometry(trunkCurve, 48, 0.09, 12, false);
    const trunkMat = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9,
      emissive: 0x083344,
      emissiveIntensity: 0.4,
      roughness: 0.3,
      metalness: 0.6,
    });
    trunkCableMesh = new THREE.Mesh(trunkGeo, trunkMat);
    trunkCableMesh.name = 'SubseaTrunkCableFixed';
    campaignGroup.add(trunkCableMesh);

    energizePulseSpheres = [];
    for (let i = 0; i < 8; i++) {
      const pulse = new THREE.Mesh(
        new THREE.SphereGeometry(0.18, 16, 16),
        new THREE.MeshBasicMaterial({ color: 0x10b981 })
      );
      pulse.visible = false;
      pulse.userData = { offset: i / 8, curve: trunkCurve };
      campaignGroup.add(pulse);
      energizePulseSpheres.push(pulse);
    }

    // 5. Stage 4 Subsea TMS Recovery Cage (at NED [0, 0, 2.2])
    tmsCageGroup = new THREE.Group();
    tmsCageGroup.name = 'Stage4_TMSRecoveryCage';
    tmsCageGroup.position.copy(nedToThreeVec(THREE, [0.0, 0.0, 2.2]));
    const cageFrameMat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, roughness: 0.32, metalness: 0.7 });
    const cageRingTop = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.06, 14, 36), cageFrameMat);
    cageRingTop.rotation.x = Math.PI / 2;
    cageRingTop.position.y = 0.95;
    tmsCageGroup.add(cageRingTop);

    const cageRingBot = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.06, 14, 36), cageFrameMat);
    cageRingBot.rotation.x = Math.PI / 2;
    cageRingBot.position.y = -0.95;
    tmsCageGroup.add(cageRingBot);

    for (let a = 0; a < 4; a++) {
      const ang = (a * Math.PI) / 2;
      const strut = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 1.9, 12), cageFrameMat);
      strut.position.set(Math.cos(ang) * 1.32, 0, Math.sin(ang) * 1.32);
      tmsCageGroup.add(strut);
    }
    campaignGroup.add(tmsCageGroup);

    // 6. Attach Manipulator Gripper Claw to ROV-01 front chassis
    if (viewer.rovG && !gripperClawVisual) {
      gripperClawVisual = new THREE.Group();
      gripperClawVisual.name = 'ROV01_SubseaCableGripper';
      gripperClawVisual.position.set(0, -0.12, -0.52);
      const armShaft = new THREE.Mesh(
        new THREE.CylinderGeometry(0.03, 0.035, 0.42, 12),
        new THREE.MeshStandardMaterial({ color: 0x38bdf8, metalness: 0.7, roughness: 0.3 })
      );
      armShaft.rotation.x = Math.PI / 2;
      gripperClawVisual.add(armShaft);

      const clawRing = new THREE.Mesh(
        new THREE.TorusGeometry(0.11, 0.022, 10, 24, Math.PI * 1.4),
        new THREE.MeshBasicMaterial({ color: 0xf59e0b })
      );
      clawRing.position.set(0, 0, -0.22);
      gripperClawVisual.add(clawRing);
      viewer.rovG.add(gripperClawVisual);
    }

    return campaignGroup;
  }

  function updateDynamicCatenaryCable(viewer, catenaryNedPoints, isGrabbed, isEnergized) {
    if (!viewer || !viewer.THREE || !campaignGroup || !Array.isArray(catenaryNedPoints) || catenaryNedPoints.length < 2) return;
    const THREE = viewer.THREE;
    const vecs = catenaryNedPoints.map((pt) => nedToThreeVec(THREE, pt));

    if ( isGrabbed && viewer.rovG ) {
      // Pin live end directly to ROV-01 front manipulator claw in world coordinates
      const tipWorld = new THREE.Vector3(0, -0.14, -0.68).applyMatrix4(viewer.rovG.matrixWorld);
      vecs[vecs.length - 1].copy(tipWorld);
    }

    const curve = new THREE.CatmullRomCurve3(vecs);
    if (dynamicCableTube) {
      campaignGroup.remove(dynamicCableTube);
      dynamicCableTube.geometry.dispose();
    }
    const tubeGeo = new THREE.TubeGeometry(curve, 32, 0.085, 10, false);
    const tubeColor = isEnergized ? 0x10b981 : isGrabbed ? 0xf59e0b : 0x22d3ee;
    const tubeMat = new THREE.MeshStandardMaterial({
      color: tubeColor,
      emissive: isEnergized ? 0x065f46 : isGrabbed ? 0x78350f : 0x083344,
      emissiveIntensity: 0.75,
      roughness: 0.25,
      metalness: 0.65,
    });
    dynamicCableTube = new THREE.Mesh(tubeGeo, tubeMat);
    dynamicCableTube.name = 'DynamicCatenarySubseaCable';
    campaignGroup.add(dynamicCableTube);
  }

  function focusCameraOnCampaignStage(stageNum) {
    const v = window.__viewer;
    if (!v || !v.THREE || !v.controls || !v.camera) return;
    v.setCam?.('orbit');
    const st = lastRenderedCampaign || getState()?.wave1?.cable_campaign;
    const tgtNed = st?.target_ned || [4.5, -1.5, 5.2];
    const p = nedToThreeVec(v.THREE, tgtNed);

    if (stageNum === 1) {
      v.controls.target.copy(p);
      v.camera.position.set(p.x - 3.6, p.y + 1.8, p.z + 3.8);
    } else if (stageNum === 2) {
      const rovP = v.rovG ? v.rovG.position.clone() : p;
      v.controls.target.copy(rovP);
      v.camera.position.set(rovP.x - 2.6, rovP.y + 1.35, rovP.z + 2.8);
    } else if (stageNum === 3) {
      const sp = nedToThreeVec(v.THREE, [9.2, -1.8, 6.8]);
      v.controls.target.copy(sp);
      v.camera.position.set(sp.x - 2.7, sp.y + 1.3, sp.z + 2.7);
    } else if (stageNum === 4) {
      const cp = nedToThreeVec(v.THREE, [0.0, 0.0, 2.2]);
      v.controls.target.copy(cp);
      v.camera.position.set(cp.x - 3.2, cp.y + 1.5, cp.z + 3.4);
    }
    v.controls.update();
  }

  // The campaign the HUD last rendered; the interact key must act on what the pilot sees,
  // not on a periodic state frame that may omit cable_campaign (that made Stage 4 send advance_ring).
  let lastRenderedCampaign = null;

  // Interaction goes over the pilot's own WebSocket session. HTTP /api/campaign/action always acts on
  // room "training" seat v1, which is not this pilot's vehicle when they hold another seat.
  function triggerStageInteraction() {
    const c = lastRenderedCampaign || getState()?.wave1?.cable_campaign;
    const st = c?.stage_num || 1;
    rovAudio.playSonarPing();
    let msg;
    if (st === 1) {
      msg = { sub_action: 'advance_ring' };
    } else if (st === 2) {
      msg = { sub_action: 'grab_cable', place_in_saddle: !!c?.cable_grabbed };
    } else if (st === 3) {
      msg = { sub_action: 'repair_step', step_delta_pct: 34.0 };
    } else {
      // Victory modal opens only when the server confirms campaign_completed (edge-triggered in render).
      msg = { sub_action: 'extract_complete' };
    }
    rejectionShownAt = 0; // re-arm: the reply's last_rejection (if any) shows for REJECTION_HOLD_MS
    offlineHintAt = 0;
    const ok = send({ type: 'wave1', action: 'campaign_action', ...msg });
    if (!ok) {
      offlineHintAt = performance.now();
      if (c) renderCampaignState(c, 0);
    }
  }

  let offlineHintAt = 0;
  let rejectionShownAt = 0;
  const REJECTION_HOLD_MS = 4000;
  const RADIUS_M = { 1: 3.2, 2: 3.2, 3: 3.5, 4: 3.5 };
  function rejectionHint(c) {
    const why = String(c?.last_rejection || '');
    if (!why) return '';
    if (why.startsWith('OUT_OF_RANGE')) {
      const m = why.match(/OUT_OF_RANGE_([\d.]+)m>([\d.]+)m/);
      const d = m ? Number(m[1]) : Number(c.target_distance_m || 0);
      const lim = m ? Number(m[2]) : RADIUS_M[c.stage_num] || 3.2;
      return `⚠ 距離太遠：目前 ${d.toFixed(1)}m，需 ≤${lim.toFixed(1)}m 才能互動 · 靠近目標或先點階段膠囊傳送 (OUT OF RANGE)`;
    }
    if (why.startsWith('WRONG_STAGE')) return `⚠ 目前階段不能執行這個動作 (${why})`;
    if (why === 'CAMPAIGN_ALREADY_COMPLETED') return '✓ 戰役已完成 · 按「再玩一次」重新開始 (CAMPAIGN_ALREADY_COMPLETED)';
    if (why === 'CABLE_NOT_GRABBED') return '⚠ 先用機械手臂夾住海纜，再入座 (CABLE_NOT_GRABBED)';
    if (why === 'ROV_POSITION_REQUIRED') return '⚠ 讀不到 ROV 位置，稍後再試 (ROV_POSITION_REQUIRED)';
    return `⚠ 互動被拒：${why}`;
  }

  function jumpToCampaignStage(stageNum) {
    const n = Number(stageNum);
    rovAudio.playSonarPing();
    send({ type: 'wave1', action: 'campaign_action', sub_action: 'set_stage', stage_num: n });
    victoryModal.hidden = true; // stage jumps are drills; victory only after a real TMS docking
    focusCameraOnCampaignStage(n);
    setTimeout(() => focusCameraOnCampaignStage(n), 220);
  }

  document.querySelectorAll('#dlStagePills .dl-spill').forEach((btn) => {
    btn.addEventListener('click', () => jumpToCampaignStage(Number(btn.dataset.stage)));
  });
  $('btnDlInteract')?.addEventListener('click', () => triggerStageInteraction());
  $('dlReticleCard')?.addEventListener('click', () => triggerStageInteraction());
  $('btnReplayCampaign')?.addEventListener('click', () => {
    victoryModal.hidden = true;
    send({ type: 'wave1', action: 'campaign_action', sub_action: 'reset' });
    setTimeout(() => focusCameraOnCampaignStage(1), 150);
  });
  $('btnCloseVictory')?.addEventListener('click', () => {
    victoryModal.hidden = true;
  });

  // Capture phase on window so [E] wins over app.js flight binding (KeyE = left_wave) while the HUD is up.
  const campaignHudVisible = () => {
    const bar = $('deepLinkObjectiveBar');
    return !!bar && !bar.hidden && bar.getClientRects().length > 0;
  };
  const isTyping = (el) =>
    !!el && (el.isContentEditable || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' ||
      (el.tagName === 'INPUT' && !['range', 'checkbox', 'button'].includes(el.type)));
  window.addEventListener(
    'keydown',
    (e) => {
      if (e.code !== 'KeyE' && e.code !== 'KeyG') return;
      if (isTyping(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (!campaignHudVisible()) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (e.repeat) return;
      triggerStageInteraction();
    },
    { capture: true }
  );

  return {
    jumpToCampaignStage,
    triggerStageInteraction,
    focusCameraOnCampaignStage,
    setVictoryVisible(vis) {
      victoryModal.hidden = !vis;
    },
    update(s, dt = 0.033) {
      const c = s?.wave1?.cable_campaign;
      if (!c) return;
      lastRenderedCampaign = c;
      renderCampaignState(c, dt);
    },
  };

  function renderCampaignState(c, dt = 0.033) {
      animTime += dt;

      const v = window.__viewer;
      if (v) {
        ensure3DCampaignObjects(v);
        updateDynamicCatenaryCable(v, c.catenary_points_ned, c.cable_grabbed, c.cable_energized);

        // Animate Stage 1 sonar rings
        if (sonarRingsGroup) {
          sonarRingsGroup.children.forEach((rg, idx) => {
            const cleared = idx < (c.waypoint_rings_cleared || 0);
            if (rg.userData.torus) {
              rg.userData.torus.material.color.setHex(cleared ? 0x10b981 : 0x22d3ee);
            }
            const pulseScale = 1.0 + 0.08 * Math.sin(animTime * 4.0 + idx);
            rg.scale.set(pulseScale, pulseScale, pulseScale);
          });
        }

        // Animate Stage 3 underwater welding sparks & cavitation bubbles
        if (sparkParticles) {
          sparkParticles.visible = c.stage_num === 3 || (c.repair_progress_pct > 0 && c.repair_progress_pct < 100);
          if (sparkParticles.visible) {
            sparkParticles.children.forEach((pMesh) => {
              const u = pMesh.userData;
              const ang = u.phase + animTime * u.speed;
              pMesh.position.set(
                Math.cos(ang) * u.radius,
                ((animTime * 0.9 + u.phase) % 1.2) - 0.3,
                Math.sin(ang) * u.radius
              );
            });
          }
        }

        // Animate Stage 4 re-energized power light pulses along the seabed trunk cable
        if (trunkCableMesh) {
          trunkCableMesh.material.color.setHex(c.cable_energized ? 0x10b981 : 0x0ea5e9);
          trunkCableMesh.material.emissive.setHex(c.cable_energized ? 0x059669 : 0x083344);
        }
        energizePulseSpheres.forEach((sp) => {
          sp.visible = !!c.cable_energized;
          if (sp.visible && sp.userData.curve) {
            const u = (sp.userData.offset + animTime * 0.28) % 1.0;
            sp.position.copy(sp.userData.curve.getPointAt(u));
          }
        });
      }

      // Update Top Campaign Bar
      $('dlStageTitle').textContent = c.stage_title_zh;
      $('dlObjectiveDesc').textContent = c.objective_zh;
      $('dlTargetBearing').textContent = `🎯 目標距離 ${Number(c.target_distance_m || 1.8).toFixed(1)}m (${c.simready_focus})`;
      $('dlOverallProgFill').style.width = `${c.overall_progress_pct || 20}%`;
      // dlTensionVal lives inside dlCableStatusTag, whose innerHTML is rebuilt below; guard so the HUD never freezes.
      const tensionEl = $('dlTensionVal');
      if (tensionEl) tensionEl.textContent = `${Number(c.cable_tension_n || 42).toFixed(1)} N`;

      const statusTag = $('dlCableStatusTag');
      if (statusTag) {
        if (c.cable_energized) {
          statusTag.innerHTML = `海纜狀態：<b style="color:#10B981;">⚡ 400kV/100Gbps 全線通電正常 (ONLINE)</b> · 懸鏈張力 <b>${c.cable_tension_n} N</b>`;
        } else if (c.cable_seated_in_saddle) {
          statusTag.innerHTML = `海纜狀態：<b style="color:#22D3EE;">🔧 已入座搶修中 (${c.repair_progress_pct.toFixed(0)}%)</b> · 懸鏈張力 <b>${c.cable_tension_n} N</b>`;
        } else if (c.cable_grabbed) {
          statusTag.innerHTML = `海纜狀態：<b style="color:#F59E0B;">🦾 機械手臂夾持拖曳中 (TOWING CABLE)</b> · 懸鏈張力 <b>${c.cable_tension_n} N</b>`;
        } else {
          statusTag.innerHTML = `海纜狀態：<b style="color:#F59E0B;">⚠️ 斷落待拾取 (Dislodged on Seabed)</b> · 懸鏈張力 <b>${c.cable_tension_n} N</b>`;
        }
      }

      document.querySelectorAll('#dlStagePills .dl-spill').forEach((btn) => {
        const sNum = Number(btn.dataset.stage);
        btn.classList.toggle('active', sNum === c.stage_num);
        btn.classList.toggle('done', sNum < c.stage_num || c.campaign_completed);
      });

      // Update Center 3D Reticle & Action Prompt
      const retCard = $('dlReticleCard');
      if (retCard) {
        retCard.className = 'dl-reticle-box' + (c.cable_energized ? ' energized' : c.cable_grabbed ? ' grabbed' : '');
        $('dlReticleHeader').textContent = c.cable_energized
          ? '[400kV / 100Gbps SUBSEA TRUNK CABLE ENERGIZED]'
          : c.cable_grabbed
            ? `[MANIPULATOR LOCKED · CATENARY TENSION ${c.cable_tension_n} N]`
            : `[TARGET LOCKED · ${c.simready_focus} · ${c.stage_code}]`;
        $('dlReticlePrompt').textContent = c.interaction_prompt;
        // Rejections stick for a few seconds even when a later state frame (which keeps last_rejection) arrives.
        if (c.last_rejection && !rejectionShownAt) rejectionShownAt = performance.now();
        if (!c.last_rejection) rejectionShownAt = 0;
        const now = performance.now();
        const hint = offlineHintAt && now - offlineHintAt < REJECTION_HOLD_MS
          ? '⚠ 未連線到模擬伺服器，互動沒有送出 (OFFLINE)'
          : c.last_rejection && now - rejectionShownAt < REJECTION_HOLD_MS ? rejectionHint(c) : '';
        const subEl = $('dlReticleSub');
        subEl.textContent = hint
          ? hint
          : c.stage_num === 3
            ? `搶修進度 ${c.repair_progress_pct.toFixed(0)}% (Step ${c.repair_step_index}/3) · 定深抗流 1.2 kn · 按 [E] / [G] 執行`
            : `目標距離 ${Number(c.target_distance_m || 1.8).toFixed(1)}m · 點擊或按 [E] / [G] 立即執行`;
        subEl.style.color = hint ? '#FDE68A' : '#cbd5e1';
        subEl.dataset.rejection = hint ? String(c.last_rejection || 'OFFLINE') : '';
        retCard.classList.toggle('rejected', !!hint);
      }

      // Update Bridge Commander Radio Comms Overlay
      if (c.latest_comms) {
        $('dlCommsSpeaker').textContent = c.latest_comms.speaker;
        $('dlCommsText').textContent = c.latest_comms.text;
      }
      const pBadge = $('dlPowerLinkBadge');
      if (pBadge) {
        pBadge.textContent = c.cable_energized ? '⚡ 400kV / 100Gbps ONLINE (100%)' : `STAGE ${c.stage_num}/4 ACTIVE`;
        pBadge.style.color = c.cable_energized ? '#10B981' : '#22D3EE';
      }

      if (c.campaign_completed) {
        $('dlVictoryRank').textContent = c.drill_mode ? '練' : String(c.campaign_rank || '—').slice(0, 1);
        $('dlVictoryScore').textContent = `${Number(c.campaign_score || 0).toFixed(1)} / 100 分 · ${c.campaign_rank || '—'}`;
        if (!lastCampaignCompleted) victoryModal.hidden = false;
      }
      lastCampaignCompleted = !!c.campaign_completed;
  }
}
