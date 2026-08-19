#!/usr/bin/env python3
"""Check that the two locales published the same set of pages.

Every page in the site derives from something that is identical across the two
content trees: a content page from a filename, a redirect stub from an
``aliases`` entry, a tag page from a ``tags`` entry, a folder page from a
directory. Translation changes prose, never any of those. So the set of emitted
paths must be identical in both locales, and any difference is something the
translation did by accident.

This catches a class of defect that no check of the Markdown can see, because
the Markdown is correct in both languages and only the rendering differs. The
motivating case: Obsidian reads ``#word`` as an inline tag when it follows
whitespace. A Chinese sentence writes ``、#864/#874(WDDM 回退)``, where the
ideographic comma before the ``#`` stops it being a tag. The English sentence
writes ``, #864/#874 (WDDM fallback)`` — same content, same meaning, and now a
tag page called ``864/874`` exists in the English site and nowhere else.

It also keeps the language switcher honest. The switcher falls back to the home
page when a counterpart is missing, which is right for an untranslated page and
wrong as a way of hiding an accidental one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def emitted_pages(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*.html")}


def compare(public: Path, locales: list[str]) -> dict[str, set[str]]:
    """Return, per locale, the pages that locale emitted and the others did not."""
    if len(locales) < 2:
        raise SystemExit(f"need at least two locales to compare, got {locales!r}")

    pages: dict[str, set[str]] = {}
    for locale in locales:
        root = public / locale
        if not root.is_dir():
            raise SystemExit(f"{root}: missing. Build the locale before comparing.")
        emitted = emitted_pages(root)
        if not emitted:
            raise SystemExit(
                f"{root}: no pages emitted. Comparing two empty trees would agree "
                f"perfectly and mean nothing."
            )
        pages[locale] = emitted

    shared = set.intersection(*pages.values())
    return {locale: emitted - shared for locale, emitted in pages.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path)
    parser.add_argument("--locales", default="zh,en")
    args = parser.parse_args()

    locales = [item.strip() for item in args.locales.split(",") if item.strip()]
    only = compare(args.public, locales)

    if not any(only.values()):
        print(f"{', '.join(locales)}: identical page sets")
        return 0

    for locale, extra in only.items():
        for page in sorted(extra):
            print(f"{locale} emitted a page no other locale did: {page}", file=sys.stderr)
    print(
        "\nThe two editions differ in structure, not just in prose. A page that "
        "exists in one language only was produced by the rendering, not by the "
        "author: check for an inline tag, an alias, or a heading that the "
        "translation introduced or dropped.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
