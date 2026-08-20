#!/usr/bin/env python3
"""Stage an English content root, filling in pages that are not translated yet.

The Chinese pages are the source of truth and the English edition is refreshed
periodically, so English lagging behind is the designed steady state rather than
an error. But the two editions are checked for identical page sets before
publishing -- the language switcher is a prefix swap, so a page present in one
edition and absent from the other is a switcher link to a 404 -- which means a
newly written Chinese page would fail the whole build until someone translated
it. That puts the mirror in a position to block its own source.

This stages a build root instead: every translated page is used as written, and
every page that has no translation yet is published in Chinese with a note
saying so. The reader gets a page that exists and is navigable in the language
it was actually written in, and translation_status.py keeps reporting it as
missing, which is the honest signal and the one the translation workflow reads.

The staging tree is a build artifact. Nothing here is written back into
content/en, because a generated page in the translated tree would be
indistinguishable from a real translation and would silently become one.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

NOTICE = """> [!note] Not yet translated
> This page has not been translated into English yet, so the Chinese original
> is shown. The English edition is refreshed from the Chinese pages
> periodically.
"""


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter block including delimiters, remainder)."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 3)
    if end == -1:
        return "", text
    return text[: end + len("\n---\n")], text[end + len("\n---\n") :]


def fallback_page(source_text: str) -> str:
    frontmatter, body = split_frontmatter(source_text)
    # The frontmatter is carried over unchanged, and that includes lang: the
    # body really is Chinese, so declaring it English would put the wrong value
    # in <html lang> and mislead a screen reader about the one page where the
    # language is not what the reader chose.
    return f"{frontmatter}\n{NOTICE}\n{body.lstrip(chr(10))}"


def stage(source: Path, translated: Path, staging: Path) -> tuple[int, int]:
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(translated, staging)

    filled = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if (translated / relative).exists():
            continue
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            target.write_text(
                fallback_page(path.read_text(encoding="utf-8")), encoding="utf-8"
            )
            filled += 1
        else:
            # An asset such as an image has nothing to translate; copying it
            # keeps a translated page that references it from losing it.
            shutil.copy2(path, target)

    translated_count = sum(1 for _ in translated.rglob("*.md"))
    return translated_count, filled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="content root of the source language")
    parser.add_argument("translated", type=Path, help="content root of the translation")
    parser.add_argument("staging", type=Path, help="build root to write")
    args = parser.parse_args()

    for directory in (args.source, args.translated):
        if not directory.is_dir():
            raise SystemExit(f"{directory}: not a directory")

    translated_count, filled = stage(args.source, args.translated, args.staging)
    print(
        f"Staged {args.staging}: {translated_count} translated page(s), "
        f"{filled} shown in the source language."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
