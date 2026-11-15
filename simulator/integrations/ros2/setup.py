"""Install the independent simulator ROS package and launch resources."""
from glob import glob
from setuptools import setup

setup(
    name="rov_sim_bridge", version="0.1.0", packages=["rov_sim_bridge"],
    data_files=[("share/ament_index/resource_index/packages", ["resource/rov_sim_bridge"]),
                ("share/rov_sim_bridge", ["package.xml"]),
                ("share/rov_sim_bridge/launch", glob("launch/*.py")),
                ("share/rov_sim_bridge/rviz", glob("rviz/*.rviz"))],
    install_requires=["setuptools", "websocket-client"], tests_require=["pytest"],
    maintainer="ROV SI team", maintainer_email="maintainers@example.com",
    description="Simulator extension, not a hardware SDK", license="Apache-2.0",
    entry_points={"console_scripts": ["bridge = rov_sim_bridge.node:main"]},
)
