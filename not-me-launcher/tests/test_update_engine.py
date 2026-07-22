from pathlib import Path
import shutil
import unittest
from unittest.mock import Mock
import zipfile

from updater.update_engine import UpdateEngine, UpdateEngineError, UpdateRequest


class FakeProcess:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code

    def terminate(self) -> None:
        self.exit_code = 1

    def wait(self, timeout=None):
        return self.exit_code


class UpdateEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-updater-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.target = self.root / "installed-launcher"
        self.target.mkdir()
        (self.target / "ErrorLabsPlaytest.exe").write_bytes(b"old")
        self.package = self.root / "update.zip"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_zip_path_traversal_is_rejected(self) -> None:
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("../escape.exe", b"bad")
            archive.writestr("ErrorLabsPlaytest.exe", b"new")
        engine = self._engine(lambda *_args: FakeProcess())

        with self.assertRaisesRegex(UpdateEngineError, "небезопасный"):
            engine._prepare_staging(
                self.package,
                Path("ErrorLabsPlaytest.exe"),
            )

        self.assertFalse((self.root / "escape.exe").exists())

    def test_damaged_zip_keeps_old_installation(self) -> None:
        self.package.write_bytes(b"not a zip")
        engine = self._engine(lambda *_args: FakeProcess())

        with self.assertRaisesRegex(UpdateEngineError, "повреждён"):
            engine.apply(lambda _status, _indeterminate: None)

        self.assertEqual(
            (self.target / "ErrorLabsPlaytest.exe").read_bytes(),
            b"old",
        )

    def test_successful_replacement_waits_for_health_marker(self) -> None:
        self._write_valid_package()
        engine_holder = {}

        def launch(_executable: Path, _working: Path):
            engine_holder["engine"].health_marker.parent.mkdir(parents=True, exist_ok=True)
            engine_holder["engine"].health_marker.write_text("ok", encoding="utf-8")
            return FakeProcess(None)

        engine = self._engine(launch)
        engine_holder["engine"] = engine
        engine.apply(lambda _status, _indeterminate: None)

        self.assertEqual(
            (self.target / "ErrorLabsPlaytest.exe").read_bytes(),
            b"new",
        )
        self.assertFalse(engine.backup.exists())

    def test_failed_new_process_rolls_back_old_installation(self) -> None:
        self._write_valid_package()
        launches = []

        def launch(executable: Path, _working: Path):
            launches.append(executable)
            return FakeProcess(1)

        engine = self._engine(launch)
        with self.assertRaisesRegex(UpdateEngineError, "не подтвердила"):
            engine.apply(lambda _status, _indeterminate: None)

        self.assertEqual(
            (self.target / "ErrorLabsPlaytest.exe").read_bytes(),
            b"old",
        )
        self.assertGreaterEqual(len(launches), 2)

    def test_locked_replacement_is_retried(self) -> None:
        engine = self._engine(lambda *_args: FakeProcess())
        source = Mock()
        source.__str__ = Mock(return_value="source")
        destination = Path("destination")
        source.replace.side_effect = [OSError("locked"), OSError("locked"), None]
        engine._replace_with_retry(source, destination)  # type: ignore[arg-type]
        self.assertEqual(source.replace.call_count, 3)

    def _write_valid_package(self) -> None:
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("ErrorLabsPlaytest.exe", b"new")
            archive.writestr("ErrorLabsUpdater.exe", b"updater")

    def _engine(self, launcher) -> UpdateEngine:
        return UpdateEngine(
            UpdateRequest(
                self.package,
                self.target,
                Path("ErrorLabsPlaytest.exe"),
                0,
                "0.2.0",
            ),
            self.root / "local-data",
            wait_timeout=0.1,
            health_timeout=0.1,
            process_launcher=launcher,
        )


if __name__ == "__main__":
    unittest.main()
