"""qysim — X1-class ROV flight simulator with a QYSea-OpenSDK-compatible backend.

Layers:
    physics      6-DOF rigid body, thruster allocation, drag, buoyancy, current
    rc           remote-controller state (PWM channels) and operation-mode mapping
    controller   flight controller: motor lock, A/S/C modes, attitude/depth hold
    navigation   DR / H_NAVI / V_NAVI / VCCM autopilots on a local geodetic frame
    engine       ties the above together and renders SDK-format telemetry
    server       asyncio host: physics loop, viewer WebSocket, SDK RPC socket
"""

__version__ = "0.1.0"
