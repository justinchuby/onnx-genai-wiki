"""Tests for the site's landing-language choice.

`build_site.py` once had a single `DEFAULT_LOCALE`, which answered two unrelated
questions at the same time:

  * which language an untranslated page falls back to, and
  * which language a visitor to the site root lands in.

The first is a property of the content -- Chinese is the source of truth, and
changing it would republish every untranslated page in a language nobody wrote.
The second is an audience decision, and the audience at the root is mostly
colleagues who read English.

Conflating them meant the second could not be changed without silently changing
the first. These tests keep them apart.
"""

import unittest

import build_site
from inject_language_switcher import HREFLANG


class LandingLocaleTests(unittest.TestCase):
    def test_source_and_landing_are_separate_names(self):
        self.assertTrue(
            hasattr(build_site, "SOURCE_LOCALE") and hasattr(build_site, "LANDING_LOCALE"),
            "build_site must name the source language and the landing language "
            "separately. A single constant cannot be changed for one purpose "
            "without changing the other.",
        )

    def test_source_locale_is_the_authored_language(self):
        self.assertEqual(
            build_site.SOURCE_LOCALE,
            "zh",
            "content/zh is mirrored from the source repository and is the "
            "fallback for untranslated pages. Changing this publishes "
            "untranslated pages in a language no one authored.",
        )

    def test_landing_locale_is_english(self):
        self.assertEqual(
            build_site.LANDING_LOCALE,
            "en",
            "the site root is intended to open in English so that a reader who "
            "does not read Chinese is not the one who has to switch.",
        )

    def test_both_locales_are_actually_built(self):
        for name in ("SOURCE_LOCALE", "LANDING_LOCALE"):
            locale = getattr(build_site, name)
            self.assertIn(
                locale,
                build_site.LOCALES,
                f"{name} is {locale!r}, which is not in LOCALES "
                f"{build_site.LOCALES}. The root would redirect to a prefix the "
                "build never emits, i.e. a 404 on the site's front door.",
            )

    def test_redirect_targets_the_landing_locale(self):
        markup = build_site.REDIRECT.format(
            lang=HREFLANG[build_site.LANDING_LOCALE],
            base_path="/onnx-genai-wiki/",
            default=build_site.LANDING_LOCALE,
        )
        self.assertIn('url=/onnx-genai-wiki/en/', markup)
        self.assertIn('href="/onnx-genai-wiki/en/"', markup)
        self.assertNotIn("/onnx-genai-wiki/zh/", markup)

    def test_redirect_declares_the_language_it_sends_readers_to(self):
        # The stub is a real page for a moment, and it is what a crawler reads
        # first. Declaring zh-CN while forwarding to the English edition would
        # misreport the site's language at its single most-linked URL.
        lang = HREFLANG[build_site.LANDING_LOCALE]
        markup = build_site.REDIRECT.format(
            lang=lang, base_path="/onnx-genai-wiki/", default=build_site.LANDING_LOCALE
        )
        self.assertIn(f'<html lang="{lang}">', markup)
        self.assertNotIn('lang="zh-CN"', markup)

    def test_every_locale_has_an_hreflang(self):
        for locale in build_site.LOCALES:
            self.assertIn(
                locale,
                HREFLANG,
                f"{locale!r} has no hreflang, so the redirect stub could not "
                "declare a language if it were made the landing locale.",
            )


if __name__ == "__main__":
    unittest.main()
