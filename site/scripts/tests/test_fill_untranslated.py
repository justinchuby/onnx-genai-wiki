"""Tests for fill_untranslated.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fill_untranslated import fallback_page, split_frontmatter, stage

PAGE = """\
---
title: Chat Templates
lang: zh-CN
---

正文第一段。
"""


class FillUntranslatedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.source = root / "zh"
        self.translated = root / "en"
        self.staging = root / "staging"
        (self.source / "prompting").mkdir(parents=True)
        self.translated.mkdir()

    def write_source(self, relative: str, text: str = PAGE) -> None:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_translated(self, relative: str, text: str) -> None:
        path = self.translated / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_an_untranslated_page_is_published_in_the_source_language(self) -> None:
        # The point of the whole script: a new Chinese page must not be able to
        # fail the build of a site whose English edition is refreshed on a
        # schedule.
        self.write_source("prompting/Survey.md")
        translated_count, filled = stage(self.source, self.translated, self.staging)
        staged = self.staging / "prompting/Survey.md"
        self.assertTrue(staged.is_file())
        self.assertIn("正文第一段。", staged.read_text(encoding="utf-8"))
        self.assertEqual((translated_count, filled), (0, 1))

    def test_the_filled_page_says_it_is_untranslated(self) -> None:
        # Without the notice a reader on the English site is given a Chinese
        # page with no explanation and no reason to think anything is missing.
        self.write_source("prompting/Survey.md")
        stage(self.source, self.translated, self.staging)
        text = (self.staging / "prompting/Survey.md").read_text(encoding="utf-8")
        self.assertIn("Not yet translated", text)

    def test_a_translated_page_is_left_exactly_as_written(self) -> None:
        english = "---\ntitle: Chat Templates\nlang: en\n---\n\nReal translation.\n"
        self.write_source("prompting/Survey.md")
        self.write_translated("prompting/Survey.md", english)
        _, filled = stage(self.source, self.translated, self.staging)
        self.assertEqual(filled, 0)
        self.assertEqual(
            (self.staging / "prompting/Survey.md").read_text(encoding="utf-8"), english
        )

    def test_the_notice_goes_after_the_frontmatter(self) -> None:
        # Ahead of it, the frontmatter stops being frontmatter and every field
        # the site reads -- title, lang, dates -- is lost.
        self.write_source("prompting/Survey.md")
        stage(self.source, self.translated, self.staging)
        text = (self.staging / "prompting/Survey.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertLess(text.index("---\n", 3), text.index("Not yet translated"))

    def test_the_declared_language_is_not_rewritten(self) -> None:
        # The body is Chinese whatever directory it is built from, so claiming
        # lang: en would put a false value in <html lang>.
        self.write_source("prompting/Survey.md")
        stage(self.source, self.translated, self.staging)
        self.assertIn(
            "lang: zh-CN", (self.staging / "prompting/Survey.md").read_text(encoding="utf-8")
        )

    def test_assets_without_a_counterpart_are_copied(self) -> None:
        (self.source / "diagram.png").write_bytes(b"\x89PNG\r\n")
        stage(self.source, self.translated, self.staging)
        self.assertEqual((self.staging / "diagram.png").read_bytes(), b"\x89PNG\r\n")

    def test_staging_is_rebuilt_rather_than_accumulated(self) -> None:
        # A page deleted upstream would otherwise stay in the staging tree and
        # be published forever, and would also break parity in the other
        # direction.
        self.write_source("prompting/Survey.md")
        stage(self.source, self.translated, self.staging)
        (self.source / "prompting/Survey.md").unlink()
        stage(self.source, self.translated, self.staging)
        self.assertFalse((self.staging / "prompting/Survey.md").exists())

    def test_a_page_without_frontmatter_still_gets_the_notice(self) -> None:
        self.write_source("prompting/Survey.md", "只有正文。\n")
        stage(self.source, self.translated, self.staging)
        text = (self.staging / "prompting/Survey.md").read_text(encoding="utf-8")
        self.assertIn("Not yet translated", text)
        self.assertIn("只有正文。", text)

    def test_split_frontmatter_leaves_a_body_only_page_alone(self) -> None:
        self.assertEqual(split_frontmatter("body\n"), ("", "body\n"))

    def test_split_frontmatter_does_not_swallow_a_horizontal_rule(self) -> None:
        # An unterminated block is not frontmatter; treating it as one would
        # delete the page.
        text = "---\ntitle: x\n"
        self.assertEqual(split_frontmatter(text), ("", text))

    def test_fallback_keeps_every_byte_of_the_body(self) -> None:
        result = fallback_page(PAGE)
        self.assertIn("正文第一段。", result)
        self.assertIn("title: Chat Templates", result)


if __name__ == "__main__":
    unittest.main()
