from pathlib import Path
import shutil
import unittest

import requests

from launcher.config import AuthConfig
from launcher.services.auth_service import AuthError, AuthService
from launcher.services.session_store import DpapiSessionStore


class Response:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class Session:
    def __init__(self, responses: list[Response | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, url: str, **kwargs):
        return self._call("post", url, kwargs)

    def get(self, url: str, **kwargs):
        return self._call("get", url, kwargs)

    def _call(self, method: str, url: str, kwargs: dict):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class SessionPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "session-persistence-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.config = AuthConfig(api_base_url="http://backend.test")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _store(self) -> DpapiSessionStore:
        return DpapiSessionStore(
            self.root / "auth-session.bin",
            protect=lambda value: bytes(byte ^ 0xA5 for byte in value),
            unprotect=lambda value: bytes(byte ^ 0xA5 for byte in value),
        )

    def _auth_response(self) -> Response:
        return Response(200, {"access_token": "secret-token", "user": {"login": "player", "display_name": "Player"}})

    def test_login_and_register_save_protected_token(self) -> None:
        for path, response in (("login", self._auth_response()), ("register", Response(201, self._auth_response().payload))):
            with self.subTest(path=path):
                store = self._store()
                service = AuthService(self.config, Session([response]), store)
                if path == "login": service.login("player", "password")
                else: service.register("player", "Player", "password", "password", "code")
                self.assertEqual(store.load(), "secret-token")
                self.assertNotIn(b"secret-token", store.path.read_bytes())

    def test_restore_uses_me_and_401_removes_session(self) -> None:
        store = self._store(); store.save("secret-token")
        service = AuthService(self.config, Session([Response(200, {"login": "player", "display_name": "Player"})]), store)
        self.assertEqual(service.restore_saved_session().display_name, "Player")
        self.assertEqual(service._session.calls[0][1], "http://backend.test/auth/me")
        expired = AuthService(self.config, Session([Response(401, {"detail": "expired"})]), store)
        self.assertIsNone(expired.restore_saved_session())
        self.assertFalse(store.path.exists())

    def test_network_error_keeps_file_logout_clears_and_corruption_is_safe(self) -> None:
        store = self._store(); store.save("secret-token")
        service = AuthService(self.config, Session([requests.ConnectionError("offline")]), store)
        with self.assertRaises(AuthError): service.restore_saved_session()
        self.assertTrue(store.path.exists())
        service._session.responses.append(Response(204, {}))
        service.logout(); self.assertFalse(store.path.exists())
        store.path.write_bytes(b"not-dpapi")
        broken = DpapiSessionStore(store.path, protect=lambda v: v, unprotect=lambda _v: (_ for _ in ()).throw(ValueError()))
        self.assertIsNone(broken.load()); self.assertFalse(store.path.exists())

    def test_token_is_not_written_to_json_or_logs(self) -> None:
        store = self._store(); store.save("secret-token")
        self.assertFalse(list(self.root.glob("*.json")))
        self.assertNotIn(b"secret-token", store.path.read_bytes())
