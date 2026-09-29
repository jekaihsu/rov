"""Alias module (import compatibility only)."""

from qysea.sdk.manage.QY_Rov_Manage import (  # noqa: F401
    QYRovAddOnsManage as QYRovAddOnsService,
    QYRovCalibrationManage as QYRovCalibrationService,
    QYRovCheckManage as QYRovCheckService,
    QYRovNavigationManage as QYRovNavigationService,
    QYRovParameterManage as QYRovParamterService,
    QYRovRealTimeStatusManage as QYRovRealTimeStatusService,
    QYRovVCCMManage as QYRovVCCMService,
    QyRovHighFreqRealTimeStatusManage as QyRovHighFreqRealTimeStatusService,
)
