from dataclasses import dataclass
from typing import Any

import requests

from launcher.config import AuthConfig


class AuthError(RuntimeError):
    """An authentication request could not be completed."""


class InvalidCredentialsError(AuthError):
    """The backend rejected the supplied login credentials."""


@dataclass(frozen=True)
class AuthenticatedUser:
    login: str
    display_name: str


class AuthService:
    """Backend authentication with an access token kept only in memory."""

    def __init__(
        self, config: AuthConfig, session: requests.Session | None = None
    ) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._access_token: str | None = None
        self._user: AuthenticatedUser | None = None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def user(self) -> AuthenticatedUser | None:
        return self._user

    def login(self, login: str, password: str) -> AuthenticatedUser:
        try:
            response = self._session.post(
                self._url("/auth/login"),
                json={"login": login, "password": password},
                timeout=(
                    self._config.connect_timeout,
                    self._config.read_timeout,
                ),
            )
        except requests.RequestException as error:
            raise AuthError("Не удалось подключиться к серверу.") from error

        if response.status_code == 401:
            raise InvalidCredentialsError(self._response_error(response))
        if not 200 <= response.status_code < 300:
            raise AuthError(self._response_error(response))

        try:
            payload = response.json()
            token = payload["access_token"]
            user = payload["user"]
            authenticated_user = AuthenticatedUser(
                login=user["login"], display_name=user["display_name"]
            )
        except (KeyError, TypeError, ValueError, requests.JSONDecodeError) as error:
            raise AuthError("Сервер вернул некорректный ответ.") from error

        if not isinstance(token, str) or not token:
            raise AuthError("Сервер вернул некорректный ответ.")
        self._access_token = token
        self._user = authenticated_user
        return authenticated_user

    def current_user(self) -> AuthenticatedUser:
        response = self._request_authenticated("get", "/auth/me")
        try:
            payload = response.json()
            return AuthenticatedUser(
                login=payload["login"], display_name=payload["display_name"]
            )
        except (KeyError, TypeError, ValueError, requests.JSONDecodeError) as error:
            raise AuthError("Сервер вернул некорректный ответ.") from error

    def logout(self) -> None:
        if self._access_token is None:
            return
        try:
            self._request_authenticated("post", "/auth/logout")
        except AuthError:
            pass
        finally:
            self._access_token = None
            self._user = None

    def _request_authenticated(self, method: str, path: str) -> requests.Response:
        if self._access_token is None:
            raise AuthError("Сессия не найдена.")
        try:
            response = getattr(self._session, method)(
                self._url(path),
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=(
                    self._config.connect_timeout,
                    self._config.read_timeout,
                ),
            )
        except requests.RequestException as error:
            raise AuthError("Не удалось подключиться к серверу.") from error
        if not 200 <= response.status_code < 300:
            raise AuthError(self._response_error(response))
        return response

    def _url(self, path: str) -> str:
        return f"{self._config.api_base_url}{path}"

    @staticmethod
    def _response_error(response: requests.Response) -> str:
        try:
            payload: Any = response.json()
        except (ValueError, requests.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("message")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
        return "Ошибка авторизации."
