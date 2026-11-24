#!/bin/bash
cd /workspace/rov_sim/blender_cablecut
B=/workspace/tools/blender/blender
run(){ n=$1; shift; env "$@" RES="(640,360)" SAMPLES=10 OUT=renders/p_$n.png $B -b -P scripts/render.py 2>&1 | grep -E "RENDER_SEC|Error" ; }
run s1 CAM="(5.2,-3.9,1.6)" TGT="(0.1,0,0.45)" LENS=30 FRAME=190
run s2 CAM="(2.4,-2.2,0.95)" TGT="(-0.35,-1.35,0.5)" LENS=45 FRAME=150
run s3 CAM="(-1.2,1.0,0.65)" TGT="(0.35,0.1,0.25)" LENS=50 FRAME=165
run s4 CAM="(1.1,-0.7,0.35)" TGT="(0.4,0,0.13)" LENS=60 FRAME=215
echo PREVIEWS_DONE
