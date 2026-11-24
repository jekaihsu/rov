#!/bin/bash
cd /workspace/rov_sim/blender_cablecut
B=/workspace/tools/blender/blender
OUTBLEND=$PWD/scene_v2.blend $B -b -P scripts/scene.py 2>&1 | grep -E "BUILD|Error|Traceback"
export SRC=$PWD/scene_v2.blend
run(){ n=$1; shift; echo "== $n start $(date +%T)"; env "$@" RES="(1920,1080)" SAMPLES=${SAMP:-44} OUT=renders/$n.png $B -b -P scripts/render.py 2>&1 | grep -E "RENDER_SEC|Error|Traceback" ; }
run hero_scene_full CAM="(4.6,0.4,1.5)" TGT="(0.1,0,0.4)" LENS=34 FRAME=152
run hero_cable_cross_section CAM="(1.0,-0.75,0.30)" TGT="(0.4,0,0.14)" LENS=60 FRAME=212 DOF=1 FSTOP=3.5
run hero_cutter_shear_closing CAM="(-1.0,0.95,0.6)" TGT="(0.35,0.15,0.25)" LENS=50 FRAME=168
run hero_rov01A_holder_closeup CAM="(2.4,-3.3,1.2)" TGT="(-0.5,-1.55,0.7)" LENS=55 FRAME=150
run hero_rov01B_cutter_closeup CAM="(2.9,0.8,1.3)" TGT="(0.63,1.58,0.7)" LENS=45 FRAME=150
run hero_scene_overview CAM="(2.6,-3.8,2.2)" TGT="(0.1,0,0.4)" LENS=32 FRAME=152
echo STILLS_DONE $(date +%T)
echo "== anim start $(date +%T)"
env RES="(960,540)" SAMPLES=14 VSTEP=3 F0=1 F1=240 FSTEP=2 LENS=34 CAM="(5.5,-1.0,1.3)" TGT="(0,0,0.5)" \
 CAMKEYS="1:(5.5,-1.0,1.3):(0,0,0.5);70:(4.6,0.4,1.5):(0.1,0,0.4);130:(2.6,-1.6,0.9):(0.2,0,0.3);160:(1.3,-0.9,0.5):(0.35,0,0.22);192:(1.4,-0.8,0.45):(0.4,0,0.2);240:(4.0,-2.6,1.6):(0.1,0,0.4)" \
 OUT=renders/anim_frames $B -b -P scripts/render.py 2>&1 | grep -E "FRAME|RENDER_SEC|Error|Traceback" 
echo ANIM_DONE $(date +%T)
