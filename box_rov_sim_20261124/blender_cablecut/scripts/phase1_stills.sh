#!/bin/bash
cd /workspace/rov_sim/blender_cablecut
B=/workspace/tools/blender/blender
mkdir -p renders logs
echo "== build $(date)" 
$B -b -P scripts/scene.py 2>&1 | grep -E "BUILD|Error|Traceback"
run(){ n=$1; shift; echo "== $n start $(date +%T)"; env "$@" RES="(1920,1080)" SAMPLES=${SAMP:-56} OUT=renders/$n.png $B -b -P scripts/render.py 2>&1 | grep -E "RENDER_SEC|Error|Traceback" ; }
run hero_scene_full CAM="(3.9,-3.2,1.25)" TGT="(0.1,0,0.45)" LENS=30 FRAME=200
run hero_cable_cross_section CAM="(1.0,-0.75,0.30)" TGT="(0.4,0,0.14)" LENS=60 FRAME=212 DOF=1 FSTOP=3.5
run hero_cutter_shear_closing CAM="(-1.0,0.95,0.6)" TGT="(0.35,0.15,0.25)" LENS=50 FRAME=168
run hero_holder_grip_spread CAM="(2.9,-3.0,1.1)" TGT="(-0.3,-1.3,0.5)" LENS=38 FRAME=150
run hero_rov01A_holder_closeup CAM="(2.4,-3.3,1.2)" TGT="(-0.5,-1.55,0.7)" LENS=55 FRAME=150
run hero_rov01B_cutter_closeup CAM="(2.9,0.8,1.3)" TGT="(0.63,1.58,0.7)" LENS=45 FRAME=150
echo STILLS_DONE $(date)
