"""Tests for the cross-locale page-set check."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from check_locale_parity import compare  # noqa: E402


class ParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.public = Path(self._tmp.name)
        for locale in ("zh", "en"):
            (self.public / locale / "tags").mkdir(parents=True)
            (self.public / locale / "index.html").write_text("x", "utf-8")
            (self.public / locale / "tags" / "memory.html").write_text("x", "utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_identical_trees_agree(self) -> None:
        self.assertEqual(compare(self.public, ["zh", "en"]), {"zh": set(), "en": set()})

    def test_a_tag_page_only_one_locale_emitted_is_reported(self) -> None:
        """The motivating case: an inline tag created by English spacing."""
        (self.public / "en" / "tags" / "864").mkdir()
        (self.public / "en" / "tags" / "864" / "874.html").write_text("x", "utf-8")
        only = compare(self.public, ["zh", "en"])
        self.assertEqual(only["en"], {"tags/864/874.html"})
        self.assertEqual(only["zh"], set())

    def test_a_page_missing_from_one_locale_is_reported_against_the_other(self) -> None:
        (self.public / "zh" / "Extra.html").write_text("x", "utf-8")
        only = compare(self.public, ["zh", "en"])
        self.assertEqual(only["zh"], {"Extra.html"})

    def test_an_empty_locale_is_an_error_not_a_perfect_match(self) -> None:
        for page in (self.public / "en").rglob("*.html"):
            page.unlink()
        with self.assertRaises(SystemExit):
            compare(self.public, ["zh", "en"])

    def test_a_missing_locale_directory_is_an_error(self) -> None:
        with self.assertRaises(SystemExit):
            compare(self.public, ["zh", "fr"])

    def test_comparing_one_locale_is_an_error(self) -> None:
        """A single-locale comparison would always pass and check nothing."""
        with self.assertRaises(SystemExit):
            compare(self.public, ["zh"])


if __name__ == "__main__":
    unittest.main()
