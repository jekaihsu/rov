#!/bin/bash
cd /workspace/rov_sim/blender_cablecut
B=/workspace/tools/blender/blender
while pgrep -f "blender -b -P scripts/render.py" >/dev/null; do sleep 5; done
export SRC=$PWD/scene_v2.blend
run(){ n=$1; shift; echo "== $n start $(date +%T)"; env "$@" RES="(1920,1080)" SAMPLES=${SAMP:-40} OUT=renders/$n.png $B -b -P scripts/render.py 2>&1 | grep -E "RENDER_SEC|Error|Traceback" ; }
run hero_rov01B_cutter_closeup CAM="(2.9,0.8,1.3)" TGT="(0.63,1.58,0.7)" LENS=45 FRAME=150
echo "== anim start $(date +%T)"
env RES="(960,540)" SAMPLES=12 VSTEP=3 F0=1 F1=240 FSTEP=3 LENS=34 CAM="(5.5,-1.0,1.3)" TGT="(0,0,0.5)" \
 CAMKEYS="1:(5.5,-1.0,1.3):(0,0,0.5);70:(4.6,0.4,1.5):(0.1,0,0.4);130:(2.6,-1.6,0.9):(0.2,0,0.3);160:(1.3,-0.9,0.5):(0.35,0,0.22);192:(1.4,-0.8,0.45):(0.4,0,0.2);240:(4.0,-2.6,1.6):(0.1,0,0.4)" \
 OUT=renders/anim_frames $B -b -P scripts/render.py 2>&1 | grep -E "FRAME|RENDER_SEC|Error|Traceback" 
echo ANIM_DONE $(date +%T)
run hero_scene_overview CAM="(2.6,-3.8,2.2)" TGT="(0.1,0,0.4)" LENS=32 FRAME=152
echo ALL_DONE $(date +%T)
