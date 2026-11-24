from __future__ import annotations

import unittest

from support import ROOT, cli_path, platforms


class SkillMetadataTests(unittest.TestCase):
    def test_required_public_package_files(self) -> None:
        for platform in platforms():
            base = ROOT / "skills" / f"{platform}-fill" if (ROOT / "skills").is_dir() else ROOT
            for relative in ("SKILL.md", "README.md", "requirements.txt", "docs/fill-only.md"):
                self.assertTrue((base / relative).is_file(), f"{platform}: {relative}")
            self.assertTrue(cli_path(platform).is_file())
            text = (base / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            self.assertIn(f"name: {platform}-fill", text)
            self.assertIn("description:", text)
            self.assertIn("never clicks publish", text)


if __name__ == "__main__":
    unittest.main()
