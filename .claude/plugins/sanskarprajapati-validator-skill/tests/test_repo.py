"""Repo-wide checks: the eleven skills, their frontmatter, the plugin manifests, the README."""

import json
import os
import re
import unittest

from _load import ROOT, SKILLS_DIR

NAME = "validator-skill"
OWNER = "sanskarprajapati"
SKILLS = [
    "validate-idea", "validate-mine", "validate-cluster", "validate-pain", "validate-segment",
    "validate-wtp", "validate-competitors", "validate-prospects", "validate-interview",
    "validate-smoke", "validate-verdict",
]
# Skills whose method is written. A built skill has a full body and no stub marker.
# Each build phase adds its skills here.
BUILT = ["validate-idea", "validate-mine", "validate-cluster", "validate-pain", "validate-segment", "validate-wtp",
         "validate-competitors", "validate-prospects", "validate-interview", "validate-smoke",
         "validate-verdict"]
STUB_MARKER = "<!-- stub:"
ABOUT = ("Eleven free Claude skills that test a startup idea against up to 1,000 real complaints before you "
         "build it: mine Reddit, Hacker News and app reviews, score the pain, find who pays, then put "
         "the idea on trial. Free, MIT.")
EM_DASH = chr(0x2014)  # built in code so this file does not trip its own check


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return match.group(1) if match else ""


def skill_text(skill):
    return read(os.path.join(SKILLS_DIR, skill, "SKILL.md"))


def text_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            if name.endswith((".md", ".py", ".json", ".jsonl", ".txt")) or name in ("LICENSE", ".gitignore"):
                yield os.path.join(base, name)


class Skills(unittest.TestCase):
    def test_eleven_skill_folders(self):
        found = sorted(
            d for d in os.listdir(SKILLS_DIR) if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))
        )
        self.assertEqual(found, sorted(SKILLS))

    def test_built_list_is_known(self):
        self.assertTrue(set(BUILT) <= set(SKILLS), set(BUILT) - set(SKILLS))

    def test_frontmatter(self):
        for skill in SKILLS:
            fm = frontmatter(skill_text(skill))
            self.assertIn("name: %s\n" % skill, fm + "\n", skill)
            self.assertRegex(fm, r"\ndescription: ", skill)
            self.assertRegex(fm, r"\nargument-hint: ", skill)
            self.assertGreater(len(fm), 300, "%s: description is too thin to trigger well" % skill)

    def test_description_says_when_to_use(self):
        for skill in SKILLS:
            # YAML ">-" folds line breaks into spaces, so compare with whitespace collapsed
            self.assertIn("Use when", " ".join(frontmatter(skill_text(skill)).split()), skill)

    def test_built_skills_are_complete(self):
        for skill in BUILT:
            text = skill_text(skill)
            self.assertNotIn(STUB_MARKER, text, skill)
            self.assertGreater(len(text.splitlines()), 60, "%s: body is too short" % skill)

    def test_stubs_are_marked(self):
        for skill in set(SKILLS) - set(BUILT):
            self.assertIn(STUB_MARKER, skill_text(skill), "%s: unbuilt skill needs a stub marker" % skill)

    def test_tools_named_in_skills_exist(self):
        for skill in SKILLS:
            for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w.\-/]+\.(?:py|md|json))", skill_text(skill)):
                path = os.path.normpath(os.path.join(SKILLS_DIR, skill, rel))
                self.assertTrue(os.path.exists(path), "%s names a missing file: %s" % (skill, rel))

    def test_next_skill_exists(self):
        for skill in SKILLS:
            for named in re.findall(r"`/(validate-[a-z]+)`", skill_text(skill)):
                self.assertIn(named, SKILLS, "%s points to an unknown skill /%s" % (skill, named))


class Manifests(unittest.TestCase):
    def load(self, name):
        return json.loads(read(os.path.join(ROOT, ".claude-plugin", name)))

    def test_plugin(self):
        plugin = self.load("plugin.json")
        self.assertEqual(plugin["name"], NAME)
        self.assertEqual(plugin["description"], ABOUT)
        self.assertEqual(plugin["license"], "MIT")
        self.assertEqual(plugin["repository"], "https://github.com/%s/%s" % (OWNER, NAME))
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")

    def test_marketplace(self):
        market = self.load("marketplace.json")
        self.assertEqual(market["name"], NAME)
        self.assertEqual(len(market["plugins"]), 1)
        self.assertEqual(market["plugins"][0]["name"], NAME)
        self.assertEqual(market["plugins"][0]["source"], "./")


class Files(unittest.TestCase):
    def test_license_is_mit(self):
        self.assertTrue(read(os.path.join(ROOT, "LICENSE")).startswith("MIT License"))

    def test_readme_install_lines(self):
        readme = " ".join(read(os.path.join(ROOT, "README.md")).split())
        self.assertTrue(readme.startswith("# The Validator skill"))
        for line in (
            "https://github.com/%s/%s" % (OWNER, NAME),
            "/plugin marketplace add %s/%s" % (OWNER, NAME),
            "/plugin install %s@%s" % (NAME, NAME),
        ):
            self.assertIn(line, readme)

    def test_no_em_dashes(self):
        for path in text_files():
            self.assertNotIn(EM_DASH, read(path), os.path.relpath(path, ROOT))


if __name__ == "__main__":
    unittest.main()
