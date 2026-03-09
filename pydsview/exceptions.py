"""pydsview 自定义异常"""


class PyDSViewError(Exception):
    """pydsview 基础异常"""
    pass


class LibraryNotFoundError(PyDSViewError):
    """找不到 libsigrok4DSL 库文件"""
    pass


class DeviceNotFoundError(PyDSViewError):
    """找不到 DSLogic 设备"""
    pass


class DeviceError(PyDSViewError):
    """设备操作错误，包含 libsigrok 错误码"""
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        if self.error_code is not None:
            return f"{super().__str__()} (error_code={self.error_code})"
        return super().__str__()


class CaptureError(PyDSViewError):
    """采集过程中出错"""
    pass
