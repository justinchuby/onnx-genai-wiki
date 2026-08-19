"""Tests for the language switcher injection.

The switcher is the only way a reader crosses between the two editions, and it
is produced after every other check has run, so nothing downstream would catch
it being wrong. These tests pin the two things that would be wrong silently:
where the link points, and what happens when a page has no counterpart.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from inject_language_switcher import ANCHOR, inject, page_url  # noqa: E402

PAGE = f"""<!DOCTYPE html>
<html lang="{{lang}}"><body>
<div id="quartz-root" class="page">{ANCHOR}<div class="page-title">t</div></div>
</body></html>
"""

STUB = """<!DOCTYPE html>
<html lang="en-us"><head><meta http-equiv="refresh" content="0; url=./elsewhere">
</head><body></body></html>
"""


class PageUrlTests(unittest.TestCase):
    def test_a_nested_page_keeps_its_path_and_loses_its_extension(self) -> None:
        self.assertEqual(
            page_url("/wiki/", "en", Path("memory/Virtual-Memory.html")),
            "/wiki/en/memory/Virtual-Memory",
        )

    def test_a_locale_home_page_is_the_locale_root(self) -> None:
        self.assertEqual(page_url("/wiki/", "en", Path("index.html")), "/wiki/en/")

    def test_a_nested_index_keeps_its_folder(self) -> None:
        self.assertEqual(page_url("/wiki/", "zh", Path("memory/index.html")), "/wiki/zh/memory/")


class InjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.public = Path(self._tmp.name)
        for locale, lang in (("zh", "zh-CN"), ("en", "en")):
            (self.public / locale / "memory").mkdir(parents=True)
            (self.public / locale / "index.html").write_text(PAGE.format(lang=lang), "utf-8")
            (self.public / locale / "memory" / "Shared.html").write_text(
                PAGE.format(lang=lang), "utf-8"
            )
        # Present in Chinese only: its translation has not been written.
        (self.public / "zh" / "memory" / "OnlyChinese.html").write_text(
            PAGE.format(lang="zh-CN"), "utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def read(self, locale: str, *parts: str) -> str:
        return (self.public / locale / Path(*parts)).read_text(encoding="utf-8")

    def test_a_page_with_a_counterpart_links_to_that_counterpart(self) -> None:
        inject(self.public, ["zh", "en"], "/wiki/")
        self.assertIn('href="/wiki/en/memory/Shared"', self.read("zh", "memory", "Shared.html"))
        self.assertIn('href="/wiki/zh/memory/Shared"', self.read("en", "memory", "Shared.html"))

    def test_a_page_with_no_counterpart_falls_back_to_the_other_home_page(self) -> None:
        inject(self.public, ["zh", "en"], "/wiki/")
        markup = self.read("zh", "memory", "OnlyChinese.html")
        self.assertIn('href="/wiki/en/"', markup)
        self.assertNotIn("/wiki/en/memory/OnlyChinese", markup)

    def test_the_fallback_says_so_rather_than_looking_like_a_translation(self) -> None:
        inject(self.public, ["zh", "en"], "/wiki/")
        self.assertIn("has not been translated yet", self.read("zh", "memory", "OnlyChinese.html"))
        self.assertNotIn("has not been translated yet", self.read("zh", "memory", "Shared.html"))

    def test_each_page_offers_the_other_language_not_its_own(self) -> None:
        inject(self.public, ["zh", "en"], "/wiki/")
        self.assertIn("English", self.read("zh", "index.html"))
        self.assertIn("中文", self.read("en", "index.html"))

    def test_the_switcher_is_added_once(self) -> None:
        inject(self.public, ["zh", "en"], "/wiki/")
        self.assertEqual(self.read("zh", "index.html").count("language-switcher"), 1)

    def test_redirect_stubs_are_skipped_rather_than_failing_the_build(self) -> None:
        (self.public / "zh" / "Alias.html").write_text(STUB, "utf-8")
        results = inject(self.public, ["zh", "en"], "/wiki/")
        self.assertEqual(results["zh"][1], 1)
        self.assertEqual(self.read("zh", "Alias.html"), STUB)

    def test_the_404_page_is_skipped_because_it_has_no_chrome_by_design(self) -> None:
        (self.public / "zh" / "404.html").write_text("<html><body>gone</body></html>", "utf-8")
        inject(self.public, ["zh", "en"], "/wiki/")
        self.assertNotIn("language-switcher", self.read("zh", "404.html"))

    def test_a_page_that_is_neither_a_stub_nor_anchored_is_an_error(self) -> None:
        """A layout change must stop the build, not quietly drop the control."""
        (self.public / "zh" / "Odd.html").write_text("<html><body>no sidebar</body></html>", "utf-8")
        with self.assertRaises(SystemExit):
            inject(self.public, ["zh", "en"], "/wiki/")

    def test_a_locale_with_nothing_to_inject_is_an_error(self) -> None:
        """Injecting into zero pages means the anchor moved, not that we are done."""
        for page in (self.public / "en").rglob("*.html"):
            page.write_text(STUB, "utf-8")
        with self.assertRaises(SystemExit):
            inject(self.public, ["zh", "en"], "/wiki/")

    def test_a_missing_locale_directory_is_an_error(self) -> None:
        with self.assertRaises(SystemExit):
            inject(self.public, ["zh", "fr"], "/wiki/")


if __name__ == "__main__":
    unittest.main()
