FROM ros:humble-ros-base
# Use few layers so this also builds on rootless Docker's VFS storage driver.
RUN --mount=type=secret,id=pip_ca \
    --mount=type=bind,source=simulator/requirements-server.txt,target=/tmp/requirements-server.txt \
    apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-websocket python3-pytest ros-humble-rviz2 \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi \
    && pip3 install --no-cache-dir -r /tmp/requirements-server.txt
# Includes campaign data required by the unmodified simulator server.
COPY simulator /simulator
RUN mkdir -p /ros_ws/src \
    && ln -s /simulator/integrations/ros2 /ros_ws/src/rov_sim_bridge \
    && cd /ros_ws && . /opt/ros/humble/setup.sh \
    && colcon build --packages-select rov_sim_bridge
CMD ["bash", "-c", "source /ros_ws/install/setup.bash && ros2 launch rov_sim_bridge bridge.launch.py"]
