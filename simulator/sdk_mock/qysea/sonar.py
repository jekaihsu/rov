"""模擬器擴充，非原廠 SDK 介面。Latest subscribed primary-view sonar scan."""
from .sdk._client import get_client


def get_latest_sonar():
    """Return None until a viewer subscribes; 模擬器擴充，非原廠 SDK 介面。"""
    return get_client().request({"type": "sonar_latest"})
