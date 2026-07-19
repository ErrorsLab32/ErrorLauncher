from pathlib import Path
import shutil
import unittest

from launcher.config import GitHubConfig
from launcher.models.release_info import ReleaseAsset, ReleaseInfo
from launcher.services.github_release_service import (
    GitHubReleaseError,
    GitHubReleaseService,
    natural_sort_key,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict | None = None,
        content: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self._content = content

    def json(self) -> dict:
        return self._payload

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self._content), chunk_size):
            yield self._content[offset : offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class GitHubReleaseServiceTests(unittest.TestCase):
    def test_natural_sort_orders_numeric_parts(self) -> None:
        names = ["part10", "part2", "part1", "Windows.7z.010", "Windows.7z.002"]
        self.assertEqual(
            sorted(names, key=natural_sort_key),
            ["part1", "part2", "part10", "Windows.7z.002", "Windows.7z.010"],
        )

    def test_missing_token_has_readable_error(self) -> None:
        config = GitHubConfig("ErrorsLab32/Not-ME", "")
        with self.assertRaisesRegex(GitHubReleaseError, "GITHUB_TOKEN"):
            GitHubReleaseService(config).get_latest_release()

    def test_latest_release_parses_and_naturally_sorts_assets(self) -> None:
        payload = {
            "tag_name": "v0.2.0",
            "name": "Test build",
            "body": "Line one\nLine two",
            "published_at": "2026-07-18T12:00:00Z",
            "assets": [
                self._asset(10, "Windows.7z.010", 10),
                self._asset(2, "Windows.7z.002", 20),
                self._asset(1, "Windows.7z.001", 30, "sha256:abc"),
            ],
        }
        service = GitHubReleaseService(self._config(Path("downloads")))
        session = FakeSession([FakeResponse(payload=payload)])
        service._session = session

        release = service.get_latest_release()

        self.assertEqual(release.tag_name, "v0.2.0")
        self.assertEqual(
            [asset.name for asset in release.assets],
            ["Windows.7z.001", "Windows.7z.002", "Windows.7z.010"],
        )
        self.assertEqual(release.assets[0].digest, "sha256:abc")
        headers = session.calls[0][1]["headers"]
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertNotIn("token-value", str(release))

    def test_download_uses_api_assets_and_ignores_installer(self) -> None:
        root = Path(__file__).parent / "test-download-output"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir()
        try:
            first = b"first-volume"
            second = b"second-volume"
            release = ReleaseInfo(
                tag_name="v0.3.0",
                name="Build",
                body="",
                published_at="",
                assets=(
                    ReleaseAsset(1, "Windows.7z.001", len(first), "application/octet-stream", "https://api.github.test/assets/1"),
                    ReleaseAsset(2, "Windows.7z.002", len(second), "application/octet-stream", "https://api.github.test/assets/2"),
                    ReleaseAsset(3, "7z2602-x64.exe", 999, "application/octet-stream", "https://api.github.test/assets/3"),
                ),
                http_status=200,
            )
            service = GitHubReleaseService(self._config(root))
            session = FakeSession(
                [FakeResponse(content=first), FakeResponse(content=second)]
            )
            service._session = session
            progress = []

            destination = service.download_archive_parts(
                release,
                root / "v0.3.0",
                progress.append,
            )

            self.assertEqual((destination / "Windows.7z.001").read_bytes(), first)
            self.assertEqual((destination / "Windows.7z.002").read_bytes(), second)
            self.assertFalse((destination / "7z2602-x64.exe").exists())
            self.assertFalse(list(destination.glob("*.part")))
            self.assertEqual(len(session.calls), 2)
            self.assertTrue(all(call[1]["stream"] for call in session.calls))
            self.assertTrue(all(call[1]["allow_redirects"] for call in session.calls))
            self.assertEqual(progress[-1].percent, 100)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_asset_name_cannot_escape_destination(self) -> None:
        root = Path(__file__).parent / "test-traversal-output"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir()
        try:
            content = b"safe"
            release = ReleaseInfo(
                tag_name="v1",
                name="Build",
                body="",
                published_at="",
                assets=(
                    ReleaseAsset(
                        1,
                        "../Windows.7z.001",
                        len(content),
                        "application/octet-stream",
                        "https://api.github.test/assets/1",
                    ),
                ),
                http_status=200,
            )
            destination = root / "release"
            service = GitHubReleaseService(self._config(root))
            service._session = FakeSession([FakeResponse(content=content)])

            service.download_archive_parts(release, destination, lambda _value: None)

            self.assertEqual((destination / "Windows.7z.001").read_bytes(), content)
            self.assertFalse((root / "Windows.7z.001").exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @staticmethod
    def _asset(asset_id: int, name: str, size: int, digest: str | None = None) -> dict:
        return {
            "id": asset_id,
            "name": name,
            "size": size,
            "content_type": "application/octet-stream",
            "url": f"https://api.github.test/assets/{asset_id}",
            "digest": digest,
        }

    @staticmethod
    def _config(downloads: Path) -> GitHubConfig:
        return GitHubConfig("ErrorsLab32/Not-ME", "token-value")


if __name__ == "__main__":
    unittest.main()
