"""Mock of the SDK info manage layer."""

from qysea.sdk._client import Remote


class QYSDKInfoManage(Remote):
    """SDK version information."""

    _CLS = "QYSDKInfoManage"

    def get_sdk_info(self):
        return self._call("get_sdk_info")
