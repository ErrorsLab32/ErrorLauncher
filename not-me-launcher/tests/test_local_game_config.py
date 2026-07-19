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

    def test_missing_local_value_leaves_game_access_unavailable(self) -> None:
        with patch("launcher.config.ENV_PATH", self.env_path), patch.dict(
            os.environ, {"GITHUB_TOKEN": "environment-value"}
        ):
            config = load_github_config()
        self.assertEqual(config.repository, "ErrorsLab32/Not-ME")
        self.assertEqual(config.token, "")

    def test_local_development_value_is_loaded_from_dotenv(self) -> None:
        self.env_path.write_text("GITHUB_TOKEN=development-value\n", encoding="utf-8")
        with patch("launcher.config.ENV_PATH", self.env_path):
            config = load_github_config()
        self.assertEqual(config.token, "development-value")


if __name__ == "__main__":
    unittest.main()
