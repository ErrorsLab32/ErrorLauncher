import hashlib
from pathlib import Path
import shutil
import unittest

from launcher.models.launcher_update import (
    LauncherUpdateAsset,
    LauncherUpdateManifest,
    LauncherUpdateRelease,
)
from launcher.services.launcher_update_service import (
    LauncherUpdateError,
    LauncherUpdateService,
    normalize_version,
)


class FakeResponse:
    def __init__(self, payload=None, content: bytes = b"", status_code: int = 200):
        self._payload = payload
        self._content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self._content), chunk_size):
            yield self._content[offset : offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class LauncherUpdateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-launcher-update-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_normalizes_optional_v_prefix(self) -> None:
        self.assertEqual(normalize_version("v0.1.0"), normalize_version("0.1.0"))

    def test_manifest_is_parsed(self) -> None:
        manifest = LauncherUpdateService.parse_manifest(
            {
                "version": "0.2.0",
                "platform": "windows-x64",
                "asset": "ErrorLabsPlaytest-0.2.0-win-x64.zip",
                "entrypoint": "ErrorLabsPlaytest.exe",
                "sha256": "a" * 64,
            }
        )
        self.assertEqual(manifest.version, "0.2.0")
        self.assertEqual(manifest.entrypoint, Path("ErrorLabsPlaytest.exe"))

    def test_missing_manifest_selected_asset_is_rejected(self) -> None:
        release_payload = {
            "tag_name": "v0.2.0",
            "assets": [
                self._asset("launcher-manifest.json", 100),
                self._asset("wrong.zip", 20),
            ],
        }
        manifest_payload = {
            "version": "0.2.0",
            "platform": "windows-x64",
            "asset": "expected.zip",
            "entrypoint": "ErrorLabsPlaytest.exe",
            "sha256": "b" * 64,
        }
        session = FakeSession(
            [FakeResponse(release_payload), FakeResponse(manifest_payload)]
        )
        service = LauncherUpdateService(
            "ErrorsLab32/ErrorLauncher", self.root, session
        )

        with self.assertRaisesRegex(LauncherUpdateError, "отсутствует пакет"):
            service.check_for_update("0.1.0")

        self.assertTrue(
            all(
                "Authorization" not in call[1].get("headers", {})
                for call in session.calls
            )
        )

    def test_sha256_mismatch_removes_partial_download(self) -> None:
        content = b"bad"
        expected = hashlib.sha256(b"good").hexdigest()
        manifest = LauncherUpdateManifest(
            "0.2.0",
            "windows-x64",
            "launcher.zip",
            Path("ErrorLabsPlaytest.exe"),
            expected,
        )
        release = LauncherUpdateRelease(
            "v0.2.0",
            manifest,
            LauncherUpdateAsset(
                "launcher.zip",
                "https://example.test/launcher.zip",
                len(content),
                None,
            ),
        )
        session = FakeSession([FakeResponse(content=content)])
        service = LauncherUpdateService(
            "ErrorsLab32/ErrorLauncher", self.root, session
        )

        with self.assertRaisesRegex(LauncherUpdateError, "целостности"):
            service.download_update(release, lambda _progress: None)

        self.assertFalse(list(self.root.rglob("*.part")))
        self.assertNotIn("Authorization", session.calls[0][1]["headers"])

    @staticmethod
    def _asset(name: str, size: int) -> dict:
        return {
            "name": name,
            "size": size,
            "browser_download_url": f"https://example.test/{name}",
        }


if __name__ == "__main__":
    unittest.main()
