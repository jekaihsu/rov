"""Launch the bridge and optionally RViz; all names can be remapped by ROS."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    defaults = {"ws_url": "ws://127.0.0.1:8765", "rpc_host": "127.0.0.1", "rviz": "false"}
    actions = [DeclareLaunchArgument(key, default_value=value) for key, value in defaults.items()]
    actions.append(Node(package="rov_sim_bridge", executable="bridge", output="screen",
                        parameters=[{key: LaunchConfiguration(key) for key in ("ws_url", "rpc_host")}]))
    config = str(Path(get_package_share_directory("rov_sim_bridge")) / "rviz" / "bridge.rviz")
    actions.append(Node(package="rviz2", executable="rviz2", arguments=["-d", config],
                        condition=IfCondition(LaunchConfiguration("rviz"))))
    return LaunchDescription(actions)
