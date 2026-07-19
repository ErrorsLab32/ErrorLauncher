from pathlib import Path
import os
import shutil
import unittest
from unittest.mock import patch

from launcher.config import load_github_config


class LocalGameConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-local-game-config"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.env_path = self.root / ".env"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_missing_local_value_does_not_read_environment(self) -> None:
        with patch("launcher.config.ENV_PATH", self.env_path), patch.dict(os.environ, {"GITHUB_TOKEN": "environment-value"}):
            config = load_github_config()
        self.assertEqual(config.repository, "ErrorsLab32/Not-ME")
        self.assertEqual(config.token, "")

    def test_local_development_value_is_loaded_from_dotenv(self) -> None:
        self.env_path.write_text("GITHUB_TOKEN=development-value\n", encoding="utf-8")
        with patch("launcher.config.ENV_PATH", self.env_path):
            config = load_github_config()
        self.assertEqual(config.token, "development-value")

    def test_built_value_is_used_when_dotenv_is_empty(self) -> None:
        with patch("launcher.config.ENV_PATH", self.env_path), patch(
            "launcher.config.BUILT_GAME_RELEASES_TOKEN_B64", "YnVpbHQtdmFsdWU="
        ):
            self.assertEqual(load_github_config().token, "built-value")

    def test_dotenv_value_has_priority_over_built_value(self) -> None:
        self.env_path.write_text("GITHUB_TOKEN=development-value\n", encoding="utf-8")
        with patch("launcher.config.ENV_PATH", self.env_path), patch(
            "launcher.config.BUILT_GAME_RELEASES_TOKEN_B64", "YnVpbHQtdmFsdWU="
        ):
            self.assertEqual(load_github_config().token, "development-value")


if __name__ == "__main__":
    unittest.main()
