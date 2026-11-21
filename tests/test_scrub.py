import os, subprocess, tempfile, unittest

SCRUB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "omakit-scrub")
# Fixture values are built from parts, so this file itself never holds a full match.
HOME = "/ho" + "me/alice/notes"
LAN = "192." + "168.0.42"
MAIL = "alice" + "@" + "example.org"
DASH = chr(0x2014)
MACHINE = "Fake" + "Box42"


class ScrubTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.write("README.md", "A clean public readme.\nContact: 1+bot@users.noreply.github.com\n")
        self.private = os.path.join(tempfile.mkdtemp(), "private.patterns")
        with open(self.private, "w") as f:
            f.write("# comment\n(?i)fake" + "box\\d+\n")

    def write(self, name, text):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def scrub(self, private=None):
        env = dict(os.environ, OMAKIT_SCRUB_PRIVATE=private or self.private)
        return subprocess.run(["bash", SCRUB, self.repo], capture_output=True, text=True, env=env)

    def test_clean_repo_passes(self):
        r = self.scrub()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 private patterns checked", r.stdout)

    def test_builtins_fail(self):
        for text, label in ((HOME, "a home path"), (LAN, "a LAN address"), (MAIL, "an e-mail address"), ("a " + DASH + " b", "an en or em dash")):
            self.write("doc.md", text + "\n")
            r = self.scrub()
            self.assertEqual(r.returncode, 1, text)
            self.assertIn("FOUND " + label, r.stdout)

    def test_private_pattern_fails_in_any_case(self):
        self.write("sub/notes.txt", "built on " + MACHINE.lower() + "\n")
        r = self.scrub()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FOUND a private pattern", r.stdout)

    def test_missing_private_file_is_said(self):
        r = self.scrub(private=os.path.join(self.repo, "..", "none.patterns"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("no private patterns file", r.stdout)

    def test_repo_pattern_with_skip(self):
        self.write(".scrub-patterns", "\\.\\./docs/ !! branding\n")
        self.write("branding/brief.md", "see ../" + "docs/plan.md\n")
        self.assertEqual(self.scrub().returncode, 0)
        self.write("README.md", "see ../" + "docs/plan.md\n")
        r = self.scrub()
        self.assertEqual(r.returncode, 1)
        self.assertIn("README.md", r.stdout)

    def test_bad_pattern_fails_closed(self):
        with open(self.private, "w") as f:
            f.write("(unclosed\n")
        r = self.scrub()
        self.assertEqual(r.returncode, 1)
        self.assertIn("BAD PATTERN", r.stdout)

    def test_private_names_in_the_repo_patterns_file_are_caught(self):
        self.write(".scrub-patterns", MACHINE + "\n")
        self.assertEqual(self.scrub().returncode, 1)
