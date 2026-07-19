from dataclasses import dataclass
from typing import Any

import requests

from launcher.config import AuthConfig
from launcher.services.session_store import DpapiSessionStore, SessionStoreError


class AuthError(RuntimeError):
    """An authentication request could not be completed."""


class InvalidCredentialsError(AuthError):
    """The backend rejected the supplied login credentials."""


class PasswordMismatchError(AuthError):
    """The password confirmation does not match the password."""


class SessionExpiredError(AuthError):
    """The backend no longer accepts the stored access token."""


@dataclass(frozen=True)
class AuthenticatedUser:
    login: str
    display_name: str


class AuthService:
    """Backend authentication with an access token kept only in memory."""

    def __init__(
        self,
        config: AuthConfig,
        session: requests.Session | None = None,
        session_store: DpapiSessionStore | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._session_store = session_store
        self._access_token: str | None = None
        self._user: AuthenticatedUser | None = None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def user(self) -> AuthenticatedUser | None:
        return self._user

    def login(self, login: str, password: str) -> AuthenticatedUser:
        response = self._post(
            "/auth/login", {"login": login, "password": password}
        )
        if response.status_code == 401:
            raise InvalidCredentialsError(self._response_error(response))
        return self._complete_authentication(response)

    def register(
        self,
        login: str,
        display_name: str,
        password: str,
        password_confirmation: str,
        invite_code: str,
    ) -> AuthenticatedUser:
        if password != password_confirmation:
            raise PasswordMismatchError("Пароли не совпадают.")
        response = self._post(
            "/auth/register",
            {
                "login": login,
                "display_name": display_name,
                "password": password,
                "invite_code": invite_code,
            },
        )
        return self._complete_authentication(response)

    def _post(self, path: str, payload: dict[str, str]) -> requests.Response:
        try:
            response = self._session.post(
                self._url(path),
                json=payload,
                timeout=(
                    self._config.connect_timeout,
                    self._config.read_timeout,
                ),
            )
        except requests.RequestException as error:
            raise AuthError("Не удалось подключиться к серверу.") from error

        return response

    def _complete_authentication(
        self, response: requests.Response
    ) -> AuthenticatedUser:
        if response.status_code == 401:
            raise SessionExpiredError(self._response_error(response))
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
        if self._session_store is not None:
            try:
                self._session_store.save(token)
            except SessionStoreError as error:
                raise AuthError(str(error)) from error
        self._access_token = token
        self._user = authenticated_user
        return authenticated_user

    def current_user(self) -> AuthenticatedUser:
        response = self._request_authenticated("get", "/auth/me")
        try:
            payload = response.json()
            user = AuthenticatedUser(
                login=payload["login"], display_name=payload["display_name"]
            )
        except (KeyError, TypeError, ValueError, requests.JSONDecodeError) as error:
            raise AuthError("Сервер вернул некорректный ответ.") from error

        self._user = user
        return user

    def restore_saved_session(self) -> AuthenticatedUser | None:
        if self._session_store is None:
            return None
        token = self._session_store.load()
        if token is None:
            return None
        self._access_token = token
        self._user = None
        try:
            return self.current_user()
        except SessionExpiredError:
            self._clear_session()
            return None

    def logout(self) -> None:
        try:
            if self._access_token is not None:
                self._request_authenticated("post", "/auth/logout")
        except AuthError:
            pass
        finally:
            self._clear_session()

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
        if response.status_code == 401:
            raise SessionExpiredError(self._response_error(response))
        if not 200 <= response.status_code < 300:
            raise AuthError(self._response_error(response))
        return response

    def _clear_session(self) -> None:
        self._access_token = None
        self._user = None
        if self._session_store is not None:
            self._session_store.clear()

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
