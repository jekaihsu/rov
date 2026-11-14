"""模拟器扩展，非原厂 SDK 接口。Latest subscribed primary-view sonar scan."""
from .sdk._client import get_client


def get_latest_sonar():
    """Return None until a viewer subscribes; 模拟器扩展，非原厂 SDK 接口。"""
    return get_client().request({"type": "sonar_latest"})
