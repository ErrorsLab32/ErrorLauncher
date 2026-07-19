import unittest

import requests

from launcher.config import AuthConfig
from launcher.services.auth_service import (
    AuthError,
    AuthService,
    InvalidCredentialsError,
    PasswordMismatchError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | Exception | list[FakeResponse]) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("post", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AuthConfig(api_base_url="http://backend.test:8000")

    def test_successful_login_keeps_token_in_memory(self) -> None:
        session = FakeSession(
            FakeResponse(
                200,
                {
                    "access_token": "access-token",
                    "token_type": "bearer",
                    "user": {"login": "player", "display_name": "Player One"},
                },
            )
        )
        service = AuthService(self.config, session)

        user = service.login("player", "secret")

        self.assertEqual(user.login, "player")
        self.assertEqual(user.display_name, "Player One")
        self.assertEqual(service.access_token, "access-token")
        self.assertEqual(service.user, user)
        self.assertEqual(session.calls[0][1], "http://backend.test:8000/auth/login")
        self.assertEqual(
            session.calls[0][2]["json"], {"login": "player", "password": "secret"}
        )

    def test_401_shows_server_error_and_does_not_store_token(self) -> None:
        service = AuthService(
            self.config,
            FakeSession(FakeResponse(401, {"detail": "Неверный логин или пароль"})),
        )

        with self.assertRaisesRegex(InvalidCredentialsError, "Неверный логин"):
            service.login("player", "wrong")

        self.assertIsNone(service.access_token)

    def test_network_error_is_reported(self) -> None:
        service = AuthService(
            self.config,
            FakeSession(requests.ConnectionError("connection refused")),
        )

        with self.assertRaisesRegex(AuthError, "Не удалось подключиться"):
            service.login("player", "secret")

        self.assertIsNone(service.access_token)

    def test_successful_registration_keeps_token_in_memory(self) -> None:
        session = FakeSession(
            FakeResponse(
                201,
                {
                    "access_token": "registered-token",
                    "token_type": "bearer",
                    "user": {"login": "new_player", "display_name": "New Player"},
                },
            )
        )
        service = AuthService(self.config, session)

        user = service.register(
            "new_player", "New Player", "secret", "secret", "invite-code"
        )

        self.assertEqual(user.display_name, "New Player")
        self.assertEqual(service.access_token, "registered-token")
        self.assertEqual(service.user, user)
        self.assertEqual(session.calls[0][1], "http://backend.test:8000/auth/register")
        self.assertEqual(
            session.calls[0][2]["json"],
            {
                "login": "new_player",
                "display_name": "New Player",
                "password": "secret",
                "invite_code": "invite-code",
            },
        )

    def test_invalid_invite_code_shows_backend_detail(self) -> None:
        service = AuthService(
            self.config,
            FakeSession(FakeResponse(400, {"detail": "Неверный код приглашения"})),
        )

        with self.assertRaisesRegex(AuthError, "Неверный код приглашения"):
            service.register("new_player", "New Player", "secret", "secret", "bad")

        self.assertIsNone(service.access_token)

    def test_registration_rejects_mismatched_passwords_without_request(self) -> None:
        session = FakeSession(FakeResponse(201, {}))
        service = AuthService(self.config, session)

        with self.assertRaisesRegex(PasswordMismatchError, "Пароли не совпадают"):
            service.register("new_player", "New Player", "secret", "different", "code")

        self.assertEqual(session.calls, [])

    def test_registration_network_error_is_reported(self) -> None:
        service = AuthService(
            self.config,
            FakeSession(requests.ConnectionError("connection refused")),
        )

        with self.assertRaisesRegex(AuthError, "Не удалось подключиться"):
            service.register("new_player", "New Player", "secret", "secret", "code")

    def test_logout_clears_token_and_current_user(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "access_token": "access-token",
                        "token_type": "bearer",
                        "user": {"login": "player", "display_name": "Player One"},
                    },
                ),
                FakeResponse(204, {}),
            ]
        )
        service = AuthService(self.config, session)
        service.login("player", "secret")

        service.logout()

        self.assertIsNone(service.access_token)
        self.assertIsNone(service.user)
        self.assertEqual(session.calls[1][1], "http://backend.test:8000/auth/logout")


if __name__ == "__main__":
    unittest.main()
