import importlib
import unittest


MODULES = (
    "launcher.app",
    "launcher.navigation",
    "launcher.config",
    "launcher.installation_preferences",
    "launcher.models.release_info",
    "launcher.models.installation_state",
    "launcher.models.launcher_update",
    "launcher.services.github_release_service",
    "launcher.services.auth_service",
    "launcher.services.game_installation_service",
    "launcher.services.game_process_service",
    "launcher.services.launcher_update_service",
    "launcher.workers.release_check_worker",
    "launcher.workers.download_worker",
    "launcher.workers.installation_worker",
    "launcher.workers.launcher_update_check_worker",
    "launcher.workers.launcher_update_download_worker",
    "launcher.launcher_update_controller",
    "launcher.views.login_view",
    "launcher.views.register_view",
    "launcher.views.recovery_view",
    "launcher.views.launcher_view",
    "launcher.views.settings_view",
    "launcher.views.launcher_update_view",
    "updater.update_engine",
    "updater.main",
)


class ImportTests(unittest.TestCase):
    def test_project_modules_import(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main()
