"""Tests for the translation stamp.

The stamp exists so that ``translation_status.py`` can tell a current
translation from a stale one. So the property worth testing is not the shape of
the frontmatter but the round trip: a page stamped by this script must be
reported ``current``, and the same page must become ``stale`` the moment its
source changes. A test that only checked the field was present would pass on a
stamp that wrote a constant.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from stamp_translations import stamp  # noqa: E402
from translation_status import CURRENT, MISSING, STALE, blob_sha, compare  # noqa: E402

PAGE = """---
title: Example
lang: {lang}
updated: 2026-01-01
---

# Example

{body}
"""


class StampTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.source = root / "zh"
        self.target = root / "en"
        (self.source / "nested").mkdir(parents=True)
        (self.target / "nested").mkdir(parents=True)
        self.source_page = self.source / "nested" / "Example.md"
        self.target_page = self.target / "nested" / "Example.md"
        self.source_page.write_text(PAGE.format(lang="zh-CN", body="源"), encoding="utf-8")
        self.target_page.write_text(PAGE.format(lang="en", body="source"), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def statuses(self) -> dict[str, str]:
        return {str(e.path): e.state for e in compare(self.source, self.target)}

    def test_an_unstamped_translation_is_not_reported_current(self) -> None:
        self.assertNotEqual(self.statuses()["nested/Example.md"], CURRENT)

    def test_a_stamped_translation_is_reported_current(self) -> None:
        stamp(self.target_page, blob_sha(self.source_page), "2026-01-02")
        self.assertEqual(self.statuses()["nested/Example.md"], CURRENT)

    def test_a_stamped_translation_goes_stale_when_its_source_changes(self) -> None:
        stamp(self.target_page, blob_sha(self.source_page), "2026-01-02")
        self.source_page.write_text(
            PAGE.format(lang="zh-CN", body="源改了"), encoding="utf-8"
        )
        self.assertEqual(self.statuses()["nested/Example.md"], STALE)

    def test_restamping_an_unchanged_page_writes_nothing(self) -> None:
        sha = blob_sha(self.source_page)
        self.assertTrue(stamp(self.target_page, sha, "2026-01-02"))
        before = self.target_page.read_bytes()
        self.assertFalse(stamp(self.target_page, sha, "2026-01-02"))
        self.assertEqual(self.target_page.read_bytes(), before)

    def test_stamping_replaces_rather_than_appends(self) -> None:
        stamp(self.target_page, "a" * 40, "2026-01-02")
        stamp(self.target_page, blob_sha(self.source_page), "2026-01-03")
        text = self.target_page.read_text(encoding="utf-8")
        self.assertEqual(text.count("translated_from:"), 1)
        self.assertEqual(text.count("translated_at:"), 1)
        self.assertNotIn("a" * 40, text)

    def test_the_stamp_leaves_the_body_and_other_fields_alone(self) -> None:
        stamp(self.target_page, blob_sha(self.source_page), "2026-01-02")
        text = self.target_page.read_text(encoding="utf-8")
        self.assertIn("title: Example", text)
        self.assertIn("lang: en", text)
        self.assertIn("updated: 2026-01-01", text)
        self.assertTrue(text.endswith("# Example\n\nsource\n"))

    def test_a_file_without_frontmatter_is_an_error_not_a_silent_skip(self) -> None:
        self.target_page.write_text("# Example\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            stamp(self.target_page, blob_sha(self.source_page), "2026-01-02")

    def test_an_untranslated_page_is_reported_missing_not_stamped(self) -> None:
        self.target_page.unlink()
        self.assertEqual(self.statuses()["nested/Example.md"], MISSING)

    def test_the_recorded_sha_is_the_git_blob_sha_of_the_source(self) -> None:
        """The value must be reproducible with ``git hash-object``.

        Cross-checking a stamp by hand is the only way to audit it without
        trusting this script, so an internal hash of our own invention would
        make the field unfalsifiable.
        """
        stamp(self.target_page, blob_sha(self.source_page), "2026-01-02")
        expected = subprocess.run(
            ["git", "hash-object", str(self.source_page)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertIn(f"translated_from: {expected}", self.target_page.read_text(encoding="utf-8"))


class StampCommandTests(unittest.TestCase):
    """The command refuses to report success over an empty source tree."""

    def test_an_empty_source_tree_fails_rather_than_stamping_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "zh").mkdir()
            (root / "en").mkdir()
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "stamp_translations.py"), str(root / "zh"), str(root / "en")],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
