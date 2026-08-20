"""Tests for the code font stack.

These lock down a fix that is easy to undo by accident, because the broken
version looks correct on macOS and only fails on Windows.

Quartz builds `--codeFont` as `"<typography.code>", ui-monospace,
SFMono-Regular, "SF Mono", Menlo, monospace`. Every named family in that list
is macOS-only, so on Windows the stack depends entirely on `ui-monospace`.

`ui-monospace` is a CSS Fonts 4 extended generic that only Safari implements.
Chromium parses the keyword but has no Windows mapping for it, and rather than
falling through to the next entry it resolves to the browser's *standard* font,
which is Times New Roman. Code blocks in Edge on Windows therefore rendered in
a serif face while the same page on macOS looked correct -- which is why the
bug survived review and reached the published site.

`custom.scss` overrides the variable. The override has to win against Quartz's
own `:root` rule, and it is emitted *before* that rule, so ordering cannot be
relied on -- it wins on specificity, which is what `test_override_outranks`
pins down.
"""

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
CUSTOM_SCSS = REPO_ROOT / "site" / "quartz" / "quartz" / "styles" / "custom.scss"

# Safari-only. Any of these ahead of a real family reintroduces the bug.
EXTENDED_GENERICS = ("ui-monospace", "ui-serif", "ui-sans-serif", "ui-rounded")

# Ships with every supported Windows release.
WINDOWS_MONOSPACE = ("Consolas", "Cascadia Mono", "Cascadia Code")


def read_custom_scss() -> str:
    if not CUSTOM_SCSS.is_file():
        raise AssertionError(
            f"expected the custom stylesheet at {CUSTOM_SCSS}. If the site layout "
            "moved, fix this path rather than skipping: a skipped test here is "
            "indistinguishable from a passing one, and this rule regressed once "
            "already."
        )
    return CUSTOM_SCSS.read_text(encoding="utf-8")


def code_font_declaration(text: str) -> str:
    match = re.search(r"--codeFont\s*:(.*?);", text, re.DOTALL)
    if match is None:
        raise AssertionError(
            "custom.scss no longer declares --codeFont. Without the override the "
            "site falls back to Quartz's macOS-only stack, which renders code "
            "blocks in Times New Roman on Windows."
        )
    return " ".join(match.group(1).split())


class CodeFontStackTests(unittest.TestCase):
    def test_no_extended_generic(self):
        declaration = code_font_declaration(read_custom_scss())
        for generic in EXTENDED_GENERICS:
            self.assertNotIn(
                generic,
                declaration,
                f"{generic!r} is implemented only by Safari. Chromium resolves it "
                "to the standard font on Windows instead of falling through, so "
                "code blocks render in serif there while looking fine on macOS.",
            )

    def test_names_a_windows_font(self):
        declaration = code_font_declaration(read_custom_scss())
        self.assertTrue(
            any(font in declaration for font in WINDOWS_MONOSPACE),
            "the stack names no font that ships with Windows, so Windows readers "
            f"depend entirely on the trailing generic. Expected one of "
            f"{WINDOWS_MONOSPACE}, got: {declaration}",
        )

    def test_ends_with_the_generic(self):
        declaration = code_font_declaration(read_custom_scss())
        self.assertTrue(
            declaration.rstrip().endswith("monospace"),
            "the stack must end in the `monospace` generic so an unlisted "
            f"platform still gets a fixed-pitch face. Got: {declaration}",
        )

    def test_latin_fonts_precede_cjk_fonts(self):
        # Font fallback is per character, so Latin resolves from the first entry
        # that has the glyph. A CJK family ahead of the Latin ones would capture
        # Latin text too and render the whole block in a CJK face.
        declaration = code_font_declaration(read_custom_scss())
        families = [f.strip().strip('"') for f in declaration.split(",")]
        cjk_markers = ("Sarasa", "CJK", "YaHei", "SimSun", "Song", "Gothic")
        first_cjk = next(
            (i for i, f in enumerate(families) if any(m in f for m in cjk_markers)),
            None,
        )
        self.assertIsNotNone(
            first_cjk,
            "no CJK monospace family is listed, so Chinese inside a code block "
            "falls to a proportional face even on platforms that ship one.",
        )
        latin_after = [
            f
            for f in families[first_cjk:]
            if f in ("SF Mono", "SFMono-Regular", "Menlo") or f in WINDOWS_MONOSPACE
        ]
        self.assertEqual(
            latin_after,
            [],
            f"Latin families must come before CJK ones; found {latin_after} after "
            "the first CJK entry.",
        )

    def test_override_outranks_quartz(self):
        # Quartz emits its own `--codeFont` on `:root`, and its rule comes *after*
        # this one in the compiled stylesheet. Equal specificity would mean Quartz
        # wins, so the selector has to outrank a bare `:root`.
        text = read_custom_scss()
        match = re.search(r"([^\s{}][^{}]*?)\{[^{}]*--codeFont", text, re.DOTALL)
        self.assertIsNotNone(match, "could not find the rule declaring --codeFont")
        selector = match.group(1).strip().splitlines()[-1].strip()
        self.assertNotEqual(
            selector,
            ":root",
            "a bare `:root` ties with Quartz's own rule, which is emitted later "
            "and would therefore win. Use a higher-specificity selector such as "
            "`html:root`.",
        )
        self.assertRegex(
            selector,
            r"^[a-zA-Z]+:root$",
            f"expected a selector that outranks `:root`, such as `html:root`; got "
            f"{selector!r}",
        )


if __name__ == "__main__":
    unittest.main()
