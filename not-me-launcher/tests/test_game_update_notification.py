import unittest

from launcher.views.launcher_view import LauncherView


class Preferences:
    def __init__(self) -> None:
        self.last_notified_game_version: str | None = None

    def mark_game_version_notified(self, version: str) -> None:
        self.last_notified_game_version = version


class GameUpdateNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.view = type("NotificationView", (), {})()
        self.preferences = Preferences()
        self.view._preferences = self.preferences

    def test_new_version_calls_notifier_and_then_persists(self) -> None:
        called: list[str] = []
        self.view._game_update_notifier = lambda version: called.append(version) or True
        LauncherView._notify_game_update_if_needed(self.view, "v1.2.0")
        self.assertEqual(called, ["v1.2.0"])
        self.assertEqual(self.preferences.last_notified_game_version, "v1.2.0")

    def test_unavailable_tray_does_not_persist_and_retries(self) -> None:
        calls: list[str] = []
        self.view._game_update_notifier = lambda version: calls.append(version) and False
        LauncherView._notify_game_update_if_needed(self.view, "v1.2.0")
        LauncherView._notify_game_update_if_needed(self.view, "v1.2.0")
        self.assertEqual(calls, ["v1.2.0", "v1.2.0"])
        self.assertIsNone(self.preferences.last_notified_game_version)

    def test_same_version_is_not_sent_twice_but_newer_is(self) -> None:
        calls: list[str] = []
        self.view._game_update_notifier = lambda version: calls.append(version) or True
        LauncherView._notify_game_update_if_needed(self.view, "v1.2.0")
        LauncherView._notify_game_update_if_needed(self.view, "v1.2.0")
        LauncherView._notify_game_update_if_needed(self.view, "v1.3.0")
        self.assertEqual(calls, ["v1.2.0", "v1.3.0"])


if __name__ == "__main__":
    unittest.main()
