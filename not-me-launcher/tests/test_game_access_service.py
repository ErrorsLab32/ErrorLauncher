from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from launcher.services.access_token_store import AccessTokenStore
from launcher.services.game_access_service import GameAccessService
from launcher.services.github_release_service import GitHubReleaseError, GitHubReleaseService
from launcher.config import GitHubConfig
from launcher.services.launcher_update_service import LauncherUpdateService


class FakeProtector:
    def protect(self, value: bytes) -> bytes:
        return b"DPAPI:" + value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        assert value.startswith(b"DPAPI:")
        return value[6:][::-1]


class FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code


class FakeSession:
    def __init__(self, status_code: int = 200) -> None:
        self.response = FakeResponse(status_code)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class GameAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-game-access"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.store = AccessTokenStore(self.root / "token.bin", FakeProtector())

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    @patch.dict("os.environ", {"GITHUB_TOKEN": ""})
    def test_missing_token_returns_no_config(self) -> None:
        self.assertIsNone(GameAccessService(self.store).config())

    def test_protected_token_is_saved_and_read(self) -> None:
        self.store.save("secret-token")
        self.assertEqual(self.store.load(), "secret-token")
        self.assertNotIn(b"secret-token", self.store.path.read_bytes())

    def test_token_can_be_deleted(self) -> None:
        self.store.save("secret-token")
        self.store.delete()
        self.assertIsNone(self.store.load())

    def test_401_and_403_delete_saved_token(self) -> None:
        for status in (401, 403):
            with self.subTest(status=status):
                self.store.save("secret-token")
                session = FakeSession(status)
                service = GitHubReleaseService(GitHubConfig("ErrorsLab32/Not-ME", "secret-token"))
                service._session = session
                with self.assertRaises(GitHubReleaseError) as context:
                    service.get_latest_release()
                self.assertEqual(context.exception.status_code, status)
                GameAccessService(self.store).forget_invalid_token()
                self.assertIsNone(self.store.load())

    def test_public_launcher_requests_never_include_authorization(self) -> None:
        self.assertNotIn("Authorization", LauncherUpdateService._github_headers())
        self.assertNotIn("Authorization", LauncherUpdateService._asset_headers())


if __name__ == "__main__":
    unittest.main()
