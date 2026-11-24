# ROV-01 cable-cut — progress (Asia/Taipei)
- 07:36 task started. Box had no Blender.
- 07:37 Blender 4.2.23 LTS portable installed at /workspace/tools/blender (headless OK).
- 08:20 Python Blender pipeline works: scripts/{lib,mats,rov,cable,env,scene,render}.py. Models: ROV-01A holder (grip jaws), ROV-01B cutter (guillotine shear), armoured 3-core cable (helical armour wires, yarn serving, cut-face cores), seabed+rocks+growth, volumetric fog, spot lights, animation keyed (cable lift, grip, shear, stub falls).
- 08:20 hero stills queued: scripts/phase1_stills.sh -> renders/hero_*.png (log: logs_stills.txt)
- 08:30 v1 hero (renders/v1_*.png) OK. Applying feedback: ROV-01A/B labels, anodes/manifold/hose loops, volumetric beam cones, red-absorbing water, High Contrast look. v2 queue: scripts/phase1_all.sh (log logs_phase1_all.txt): stills -> anim frames (renders/anim_frames).
- Phase 2 files drafted: viewer/cablecut.html, viewer/cablecut.js, viewer/cablecut_vendor/three (npm three 0.170 copy, existing vendor untouched).
