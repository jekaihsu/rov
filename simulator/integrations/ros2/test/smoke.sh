#!/usr/bin/env bash
# Run inside the compose bridge container after both services have started.
set -eo pipefail
source /ros_ws/install/setup.bash
set -u
publisher=''
cleanup() {
  if [[ -n "$publisher" ]]; then kill "$publisher" 2>/dev/null || true; fi
}
trap cleanup EXIT
set -x
timeout 15 ros2 topic echo /odom nav_msgs/msg/Odometry --once --field pose.pose.position
timeout 15 ros2 topic echo /dvl/velocity --once
timeout 15 ros2 topic echo /range/forward --once
timeout 15 ros2 topic echo /range/down --once
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.2}}' >/tmp/d4-velocity.log 2>&1 &
publisher=$!
sleep 2
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: true}'
sleep 3
timeout 15 ros2 topic echo /odom --once --field twist.twist.linear
timeout 15 ros2 topic echo /tf --once
ros2 topic pub --once /lights std_msgs/msg/UInt8 '{data: 2}'
timeout 15 ros2 topic echo /diagnostics --once
python3 /ros_ws/src/rov_sim_bridge/test/check_rpc.py moving
kill "$publisher"
wait "$publisher" || true
publisher=''
sleep 1
python3 /ros_ws/src/rov_sim_bridge/test/check_rpc.py locked
ros2 topic pub -r 10 /depth/setpoint std_msgs/msg/Float64 '{data: 3.0}' >/tmp/d4-depth.log 2>&1 &
publisher=$!
sleep 2
# A fresh producer by itself must not unlock after timeout.
python3 /ros_ws/src/rov_sim_bridge/test/check_rpc.py locked
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: true}'
sleep 3
timeout 15 ros2 topic echo /depth --once
python3 /ros_ws/src/rov_sim_bridge/test/check_rpc.py depth
python3 /ros_ws/src/rov_sim_bridge/test/watchdog.py
# Re-arm explicitly to verify the separate lock subscription as well.
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: true}'
ros2 topic pub --once /arm std_msgs/msg/Bool '{data: false}'
python3 /ros_ws/src/rov_sim_bridge/test/check_rpc.py locked
