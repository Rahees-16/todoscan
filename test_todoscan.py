import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout

import todoscan


def write(root, rel, content, mode="w"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, mode) as f:
        f.write(content)
    return p


class TodoscanTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name
        self.addCleanup(self._td.cleanup)
        write(self.root, "a.py", "x = 1\n# TODO: first\n# FIXME(bob): second\n")
        write(self.root, "src/b.js", "// HACK - ugly\n/* XXX check */\n")

    def test_finds_all_tags(self):
        items = todoscan.scan(self.root)
        self.assertEqual({i["tag"] for i in items}, {"TODO", "FIXME", "HACK", "XXX"})
        todo = [i for i in items if i["tag"] == "TODO"][0]
        self.assertEqual((todo["file"], todo["line"], todo["text"]), ("a.py", 2, "first"))

    def test_tag_filter(self):
        items = todoscan.scan(self.root, ["todo"])
        self.assertEqual(len(items), 1)

    def test_skips_dirs_and_binary(self):
        write(self.root, "node_modules/x.js", "// TODO no\n")
        write(self.root, "build/y.py", "# TODO no\n")
        write(self.root, ".git/z.py", "# TODO no\n")
        write(self.root, "venv1/pyvenv.cfg", "")
        write(self.root, "venv1/lib.py", "# TODO no\n")
        write(self.root, "bin.py", b"# TODO no\0\x00", mode="wb")
        files = {i["file"] for i in todoscan.scan(self.root)}
        self.assertEqual(files, {"a.py", os.path.join("src", "b.js")})

    def test_non_comment_ignored(self):
        write(self.root, "c.py", "x = 'TODO'\n")
        self.assertFalse([i for i in todoscan.scan(self.root) if i["file"] == "c.py"])

    def test_cli_json_and_summary(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            todoscan.main([self.root, "--json"])
        self.assertEqual(len(json.loads(buf.getvalue())), 4)
        buf = io.StringIO()
        with redirect_stdout(buf):
            todoscan.main([self.root, "--summary"])
        self.assertIn("Total: 4", buf.getvalue())
        self.assertIn("TODO: 1", buf.getvalue())

    def test_text_grouped(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            todoscan.main([self.root])
        self.assertIn("a.py:2: TODO first", buf.getvalue())

    def test_blame(self):
        env = dict(os.environ, GIT_AUTHOR_NAME="Tester", GIT_AUTHOR_EMAIL="t@e.x",
                   GIT_COMMITTER_NAME="Tester", GIT_COMMITTER_EMAIL="t@e.x")
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "i"]):
            subprocess.run(["git", "-C", self.root] + cmd, check=True, env=env,
                           capture_output=True)
        items = todoscan.scan(self.root, ["TODO"], use_blame=True)
        self.assertEqual(items[0]["author"], "Tester")
        # off by default
        self.assertNotIn("author", todoscan.scan(self.root)[0])

    def test_blame_non_repo(self):
        items = todoscan.scan(self.root, ["TODO"], use_blame=True)
        self.assertIsNone(items[0]["author"])

    def test_exclude_flag(self):
        write(self.root, "private-repo/x.py", "# TODO secret\n")
        self.assertIn("private-repo/x.py", {i["file"] for i in todoscan.scan(self.root)})
        files = {i["file"] for i in todoscan.scan(self.root, exclude={"private-repo"})}
        self.assertNotIn("private-repo/x.py", files)
        buf = io.StringIO()
        with redirect_stdout(buf):
            todoscan.main([self.root, "--json", "--exclude", "private-repo"])
        self.assertNotIn("private-repo", buf.getvalue())

    def test_exclude_file(self):
        write(self.root, "private-repo/x.py", "# TODO secret\n")
        write(self.root, "other/y.py", "# TODO fine\n")
        cfg = write(self.root + "_cfg", "exclude", "# comment\n\nprivate-repo  # trailing\n")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root + "_cfg", True))
        old = os.environ.get("DEVTOOLS_EXCLUDE_FILE")
        os.environ["DEVTOOLS_EXCLUDE_FILE"] = cfg
        try:
            self.assertEqual(todoscan.load_exclude_file(), {"private-repo"})
            buf = io.StringIO()
            with redirect_stdout(buf):
                todoscan.main([self.root, "--json"])
            out = buf.getvalue()
            self.assertNotIn("private-repo", out)
            self.assertIn("other", out)
        finally:
            if old is None:
                del os.environ["DEVTOOLS_EXCLUDE_FILE"]
            else:
                os.environ["DEVTOOLS_EXCLUDE_FILE"] = old

    def test_missing_exclude_file(self):
        os.environ["DEVTOOLS_EXCLUDE_FILE"] = os.path.join(self.root, "nope")
        self.addCleanup(os.environ.pop, "DEVTOOLS_EXCLUDE_FILE", None)
        self.assertEqual(todoscan.load_exclude_file(), set())

    def test_bad_path(self):
        self.assertEqual(todoscan.main([os.path.join(self.root, "nope")]), 2)


if __name__ == "__main__":
    unittest.main()
