"""ROS node: bounded synchronous IO leaves the server watchdog authoritative."""
import json
import math
import socket
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped, Twist, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Range
from std_msgs.msg import Bool, Float64, UInt8
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster
import websocket

from .conversion import CommandGate, frd_to_flu, ned_to_enu, quaternion

STRINGS = {
    "connected": "Simulator session connected; explicit arm required",
    "connection": "Simulator connection unavailable: {}",
    "command": "Command rejected: {}",
    "seat": "Bridge requires training/v1; free the first pilot seat and restart",
    "tether": "Simulator tether and control state",
    "ok": "Telemetry connected (simulator truth)",
    "stale": "Telemetry unavailable; controls locked",
    "rpc": "SDK telemetry unavailable: {}",
}


def xyz(target, values):
    target.x, target.y, target.z = map(float, values)


class Bridge(Node):
    def __init__(self):
        super().__init__("rov_sim_bridge")
        defaults = {"ws_url": "ws://127.0.0.1:8765", "rpc_host": "127.0.0.1",
                    "rpc_port": 9760, "command_timeout": 0.4,
                    "odom_frame": "odom", "base_frame": "base_link"}
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        self.config = {key: self.get_parameter(key).value for key in defaults}
        timeout = self.config["command_timeout"]
        if not math.isfinite(timeout) or not 0.1 <= timeout <= 0.5:
            raise ValueError(STRINGS["command"].format("command_timeout must be 0.1..0.5 s"))
        self.gate = CommandGate(timeout)
        self.ws = None
        self.session = False
        self.token = None
        self.state = None
        self.world = {}
        self.generation = None
        self.last_state = -math.inf
        self.retry_at = 0.0
        self.seq = 0
        self.led = 0
        self.rpc_id = 0
        self.odom = self.create_publisher(Odometry, "odom", 10)
        self.depth = self.create_publisher(Float64, "depth", 10)
        self.dvl = self.create_publisher(TwistStamped, "dvl/velocity", 10)
        self.front = self.create_publisher(Range, "range/forward", 10)
        self.down = self.create_publisher(Range, "range/down", 10)
        self.diagnostics = self.create_publisher(DiagnosticArray, "diagnostics", 10)
        self.tf = TransformBroadcaster(self)
        self.static_tf = StaticTransformBroadcaster(self)
        self.create_subscription(Twist, "cmd_vel", self.on_velocity, 1)
        self.create_subscription(Float64, "depth/setpoint", self.on_depth, 1)
        self.create_subscription(UInt8, "lights", self.on_lights, 1)
        self.create_subscription(Bool, "arm", self.on_arm, 1)
        self.publish_sensor_frames()
        self.create_timer(0.1, self.tick)
        self.create_timer(0.2, self.poll_sdk)

    def ready(self):
        state = self.state or {}
        altitude = self.world.get("seabed_depth", -math.inf) - state.get("pos", [0, 0, 0])[2]
        return (self.session and time.monotonic() - self.last_state < 0.3
                and isinstance(state.get("assist"), dict) and 0.1 < altitude < 100
                and not state.get("input_latched", True) and not state.get("remote_control", True)
                and state.get("operation_mode") == "ROV_USA" and not state.get("paused", True)
                and not state.get("tether", {}).get("broken", True))

    def on_velocity(self, message):
        try:
            if self.ready():
                self.gate.velocity((message.linear.x, message.linear.y, message.linear.z,
                                    message.angular.x, message.angular.y, message.angular.z), time.monotonic())
        except ValueError as error:
            self.gate.reset()
            self.get_logger().warning(STRINGS["command"].format(error))

    def on_depth(self, message):
        try:
            if self.ready():
                self.gate.set_depth(message.data, time.monotonic())
        except ValueError as error:
            self.gate.reset()
            self.get_logger().warning(STRINGS["command"].format(error))

    def on_lights(self, message):
        if message.data <= 2:
            self.led = message.data

    def on_arm(self, message):
        self.gate.arm(message.data and self.ready(), time.monotonic())

    def send(self, message):
        self.ws.send(json.dumps(message, allow_nan=False))

    def disconnect(self):
        self.gate.reset()
        self.session = False
        self.state = None
        self.generation = None
        self.last_state = -math.inf
        if self.ws is not None:
            self.ws.close(timeout=0)
        self.ws = None
        self.retry_at = time.monotonic() + 1

    def receive(self, message):
        kind = message.get("type")
        if kind == "session":
            self.token = message["resume_token"]
            if message["room_id"] != "training" or message["vehicle_id"] != "v1":
                raise RuntimeError(STRINGS["seat"])
            self.gate.reset()
            self.seq = 0
            self.session = True
            self.send({"type": "operation_mode", "value": "ROV_USA"})
            self.send({"type": "shaping", "throttle_curvature": 0, "throttle_limit": 100,
                       "rotate_curvature": 0, "rotate_limit": 100})
            self.get_logger().info(STRINGS["connected"])
        elif kind == "world":
            self.world = message
        elif kind == "state" and self.session:
            if message.get("input_latched") or message.get("control_generation") != self.generation:
                self.gate.reset()
            self.generation = message.get("control_generation")
            self.state = message
            self.last_state = time.monotonic()
        elif kind == "error":
            self.gate.reset()
            raise RuntimeError(message.get("code", "protocol_error"))

    def tick(self):
        now = time.monotonic()
        try:
            if self.ws is None and now >= self.retry_at:
                self.ws = websocket.create_connection(self.config["ws_url"], timeout=0.15)
                self.send({"type": "join", "room_id": "training", "name": "ROS 2",
                           "resume_token": self.token})
                self.ws.settimeout(0.001)
            if self.ws is None:
                self.publish_diagnostics(False)
                return
            updated = False
            for _ in range(32):
                try:
                    payload = self.ws.recv()
                except websocket.WebSocketTimeoutException:
                    break
                if not payload:
                    raise ConnectionError("closed")
                message = json.loads(payload)
                self.receive(message)
                updated = updated or message.get("type") == "state"
            if not self.ready():
                self.gate.reset()
            if self.session:
                self.send({"type": "rc", "seq": self.seq,
                           "rc": self.gate.packet(self.state or {}, time.monotonic(), self.led)})
                self.seq += 1
            if updated and self.state:
                self.publish_state()
            self.publish_diagnostics(time.monotonic() - self.last_state < 0.3)
        except (OSError, ValueError, KeyError, RuntimeError, websocket.WebSocketException) as error:
            self.get_logger().warning(STRINGS["connection"].format(error))
            self.disconnect()
            self.publish_diagnostics(False)

    def publish_state(self):
        state = self.state
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.config["odom_frame"]
        msg.child_frame_id = self.config["base_frame"]
        xyz(msg.pose.pose.position, ned_to_enu(state["pos"]))
        q = msg.pose.pose.orientation
        q.x, q.y, q.z, q.w = quaternion(state["q"])
        xyz(msg.twist.twist.linear, frd_to_flu(state["vel"]))
        # Truth pose/linear velocity; angular velocity isn't supplied by this stream.
        for i in (3, 4, 5):
            msg.twist.covariance[i * 6 + i] = 1e6
        self.odom.publish(msg)
        transform = TransformStamped()
        transform.header = msg.header
        transform.child_frame_id = msg.child_frame_id
        xyz(transform.transform.translation, ned_to_enu(state["pos"]))
        transform.transform.rotation = q
        self.tf.sendTransform(transform)
        self.depth.publish(Float64(data=float(state["pos"][2])))

    def publish_diagnostics(self, fresh):
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = STRINGS["tether"]
        status.hardware_id = "simulator/training/v1"
        tether = (self.state or {}).get("tether", {})
        status.level = DiagnosticStatus.OK if fresh else DiagnosticStatus.STALE
        if fresh and (tether.get("warn") or tether.get("broken")):
            status.level = DiagnosticStatus.ERROR if tether.get("broken") else DiagnosticStatus.WARN
        status.message = STRINGS["ok"] if fresh else STRINGS["stale"]
        values = {**tether, "bridge_armed": self.gate.armed, "ready": bool(self.ready())}
        for key in ("locked", "input_latched", "control_generation", "rc"):
            values[key] = (self.state or {}).get(key)
        status.values = [KeyValue(key=k, value=json.dumps(v)) for k, v in values.items() if k != "nodes"]
        msg.status = [status]
        self.diagnostics.publish(msg)

    def publish_sensor_frames(self):
        transforms = []
        for name, offset, rotation in (("range_forward", (0.4, 0, 0), (0, 0, 0, 1)),
                                       ("range_down", (0, 0, -0.2), (0, math.sqrt(0.5), 0, math.sqrt(0.5)))):
            msg = TransformStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.config["base_frame"]
            msg.child_frame_id = self.config["base_frame"] + "/" + name
            xyz(msg.transform.translation, offset)
            q = msg.transform.rotation
            q.x, q.y, q.z, q.w = map(float, rotation)
            transforms.append(msg)
        self.static_tf.sendTransform(transforms)

    def poll_sdk(self):
        # Read-only RPC is fixed by the server to training/v1. No remote-control takeover.
        if not self.session or time.monotonic() - self.last_state >= 0.3:
            return
        self.rpc_id += 1
        request = {"id": self.rpc_id, "type": "sdk", "cls": "QYRovRealTimeStatusManage",
                   "method": "get_rov_status", "args": [], "kwargs": {}}
        try:
            with socket.create_connection((self.config["rpc_host"], self.config["rpc_port"]), timeout=0.1) as sock:
                sock.sendall((json.dumps(request) + "\n").encode())
                with sock.makefile("rb") as stream:
                    result = json.loads(stream.readline(65536))
            if not result.get("ok") or result.get("id") != self.rpc_id:
                raise ValueError("RPC response rejected")
            status = result["result"]
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.config["base_frame"]
            xyz(msg.twist.linear, frd_to_flu([status["QDVL"]["QDVL_" + axis + "speed"] for axis in "XYZ"]))
            self.dvl.publish(msg)
            for publisher, frame, value, maximum in (
                (self.front, "range_forward", status["Distance"], 50.0),
                (self.down, "range_down", status["Altitude"], 100.0),
            ):
                measurement = Range()
                measurement.header = msg.header
                measurement.header.frame_id = self.config["base_frame"] + "/" + frame
                measurement.radiation_type = Range.ULTRASOUND
                measurement.field_of_view = 0.0  # ideal single ray, not a beam model
                measurement.min_range = 0.0
                measurement.max_range = maximum
                measurement.range = math.inf if value >= maximum else float(value)
                publisher.publish(measurement)
        except (OSError, ValueError, KeyError) as error:
            self.get_logger().warning(STRINGS["rpc"].format(error), throttle_duration_sec=5.0)


def main(args=None):
    rclpy.init(args=args)
    node = Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.ws is not None and node.session:
            try:
                node.gate.reset()
                node.send({"type": "rc", "seq": node.seq, "rc": node.gate.packet({}, time.monotonic(), node.led)})
            except (OSError, websocket.WebSocketException):
                pass
        node.disconnect()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
