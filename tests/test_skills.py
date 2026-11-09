from pathlib import Path
import re
import unittest

from cpscore.harness import SKILLS

SOURCE = Path(__file__).resolve().parents[1]


class SkillsTests(unittest.TestCase):
    def test_exactly_three_portable_manifests(self):
        manifests = sorted((SOURCE / "skills").rglob("SKILL.md"))
        self.assertEqual({p.parent.name for p in manifests}, set(SKILLS))
        self.assertEqual(len(manifests), 3)
        for path in manifests:
            content = path.read_text(encoding="utf-8")
            frontmatter = content.split("---", 2)
            self.assertEqual(frontmatter[0], "")
            self.assertEqual(len(frontmatter), 3)
            self.assertIn(f"name: {path.parent.name}\n", frontmatter[1])
            self.assertRegex(frontmatter[1], r"(?m)^description: .+")
            self.assertTrue(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", path.parent.name))
            self.assertNotIn("/Users/", content)

    def test_canonical_single_adapter_and_protocol_exist(self):
        self.assertTrue((SOURCE / "scripts/skill_entry.py").is_file())
        self.assertTrue((SOURCE / "docs/protocol.md").is_file())
        self.assertEqual(list((SOURCE / "skills").rglob("*.py")), [])


if __name__ == "__main__":
    unittest.main()
