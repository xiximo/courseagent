class SprsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SprsGatewayBlockedError(SprsError):
    def __init__(self, message: str = "SPRS 接口访问未授权或网关未放行，请联系管理员") -> None:
        super().__init__("ATRUST_BLOCKED", message)


class SprsTimeoutError(SprsError):
    def __init__(self, message: str = "SPRS 响应超时，请稍后重试") -> None:
        super().__init__("SPRS_TIMEOUT", message)


class SprsApiError(SprsError):
    pass
