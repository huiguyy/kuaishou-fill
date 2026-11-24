from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT


@unittest.skipUnless((ROOT / "src" / "fillup_core").is_dir(), "workspace-only staging test")
class StagingTests(unittest.TestCase):
    def test_staged_repositories_are_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "dist"
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(ROOT / "tools" / "stage_repos.py"), "--output", str(output)],
                text=True, capture_output=True, timeout=20, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for platform in ("douyin", "kuaishou"):
                repo = output / f"{platform}-fill"
                self.assertFalse((repo / "src").exists())
                self.assertTrue((repo / "scripts" / "fillup_core" / "policy.py").is_file())
                self.assertTrue((repo / "LICENSE").is_file())
                help_run = subprocess.run(
                    [sys.executable, "-I", "-B", "-S", str(repo / "scripts" / f"{platform}_fill.py"), "--help"],
                    text=True, capture_output=True, timeout=20, check=False,
                )
                self.assertEqual(help_run.returncode, 0, help_run.stderr)
                gate = subprocess.run(
                    [sys.executable, "-I", "-B", str(repo / "tools" / "check_fill_only.py"), "--root", str(repo)],
                    text=True, capture_output=True, timeout=20, check=False,
                )
                self.assertEqual(gate.returncode, 0, gate.stderr)


if __name__ == "__main__":
    unittest.main()
