from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Type


@dataclass(slots=True)
class ErrorSpec:
    http_status: int
    code: str
    message: str


class AppError(Exception):
    """应用内部统一异常基类。"""

    spec: ErrorSpec

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            # 允许在默认 message 基础上覆盖说明
            self.spec = ErrorSpec(
                http_status=self.spec.http_status,
                code=self.spec.code,
                message=message,
            )
        super().__init__(self.spec.message)


class UnauthenticatedError(AppError):
    spec = ErrorSpec(
        http_status=HTTPStatus.UNAUTHORIZED,
        code="UNAUTHENTICATED",
        message="Authentication required.",
    )


class UserDisabledError(AppError):
    spec = ErrorSpec(
        http_status=HTTPStatus.FORBIDDEN,
        code="USER_DISABLED",
        message="User is disabled.",
    )


class AccessDeniedError(AppError):
    spec = ErrorSpec(
        http_status=HTTPStatus.FORBIDDEN,
        code="ACCESS_DENIED",
        message="Access denied.",
    )


class RuntimeNotFoundError(AppError):
    spec = ErrorSpec(
        http_status=HTTPStatus.NOT_FOUND,
        code="RUNTIME_NOT_FOUND",
        message="Runtime not found.",
    )


class CredentialNotFoundError(AppError):
    spec = ErrorSpec(
        http_status=HTTPStatus.NOT_FOUND,
        code="CREDENTIAL_NOT_FOUND",
        message="Credential not found.",
    )


ERROR_TYPE_MAP: dict[Type[AppError], ErrorSpec] = {
    UnauthenticatedError: UnauthenticatedError.spec,
    UserDisabledError: UserDisabledError.spec,
    AccessDeniedError: AccessDeniedError.spec,
    RuntimeNotFoundError: RuntimeNotFoundError.spec,
    CredentialNotFoundError: CredentialNotFoundError.spec,
}

