"""Simulator-backed stand-in for the QYSea OpenSDK ``qysea`` package.

Put ``simulator/sdk_mock`` on ``sys.path`` (or PYTHONPATH) instead of the vendor SDK and
the usual ``from qysea.sdk.manage.QY_Rov_Manage import ...`` imports talk to the qysim
simulator over TCP (QYSIM_HOST / QYSIM_RPC_PORT). See ``simulator/sdk_mock/README.md``.
"""

IS_QYSIM_MOCK = True
__version__ = "1.2.1-qysim"
