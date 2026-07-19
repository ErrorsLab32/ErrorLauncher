import os
import unittest
from unittest.mock import patch

from launcher.config import load_auth_config


class AuthConfigTests(unittest.TestCase):
    def _load(self, environment: dict[str, str]) -> str:
        with patch.dict(os.environ, environment, clear=True), patch(
            "launcher.config.dotenv_values", return_value={}
        ):
            return load_auth_config().api_base_url

    def test_runtime_override_has_priority(self) -> None:
        self.assertEqual(
            self._load(
                {
                    "API_BASE_URL": "https://configured.example",
                    "NOT_ME_API_BASE_URL": "https://runtime.example",
                }
            ),
            "https://runtime.example",
        )

    def test_runtime_override_removes_trailing_slash(self) -> None:
        self.assertEqual(
            self._load({"NOT_ME_API_BASE_URL": "https://runtime.example///"}),
            "https://runtime.example",
        )

    def test_absent_override_uses_default_url(self) -> None:
        self.assertEqual(self._load({}), "http://192.168.55.100:8000")

    def test_empty_override_uses_default_url(self) -> None:
        self.assertEqual(
            self._load({"NOT_ME_API_BASE_URL": "   "}),
            "http://192.168.55.100:8000",
        )


if __name__ == "__main__":
    unittest.main()
