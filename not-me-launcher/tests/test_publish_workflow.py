from __future__ import annotations

from pathlib import Path
import unittest

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent


class PublishWorkflowTests(unittest.TestCase):
    def test_workflow_is_manual_and_produces_three_assets(self) -> None:
        workflow_path = REPOSITORY_ROOT / ".github" / "workflows" / "publish-launcher.yml"
        workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

        self.assertEqual(workflow["on"].keys(), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"]["contents"], "write")
        publish_job = workflow["jobs"]["publish"]
        self.assertEqual(publish_job["environment"], "production")
        self.assertEqual(publish_job["defaults"]["run"]["working-directory"], "not-me-launcher")
        rendered = workflow_path.read_text(encoding="utf-8")
        self.assertIn("ErrorLabsPlaytestSetup-${{ steps.version.outputs.version }}.exe", rendered)
        self.assertIn("ErrorLabsPlaytest-${{ steps.version.outputs.version }}-win-x64.zip", rendered)
        self.assertIn("launcher-manifest.json", rendered)
        self.assertIn("git tag $env:TAG $env:GITHUB_SHA", rendered)


if __name__ == "__main__":
    unittest.main()
