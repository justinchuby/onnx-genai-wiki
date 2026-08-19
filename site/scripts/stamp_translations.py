#!/usr/bin/env python3
"""Record which revision of a source page a translation was made from.

A translation is only trustworthy while the page it was made from has not
moved. The link between the two is recorded in the translated file's
frontmatter:

    translated_from: <git blob sha of the source page>
    translated_at: <YYYY-MM-DD>

``translation_status.py`` compares the recorded sha against the source page's
current sha to decide whether a translation is current or stale.

The stamp is written by this script rather than by whoever wrote the
translation, for two reasons. A hand-written sha is a claim about a file the
author did not hash, and it is not checkable by reading the diff. And a
translator working from a stale copy would otherwise stamp the sha it read in
the frontmatter of the file it was given, laundering staleness into currency.

The sha covers the whole source file, frontmatter included, so a source edit
that only touches ``updated:`` marks the translation stale. That is the
harmless direction to be wrong in: retranslating a page that did not need it
costs one agent run, whereas failing to notice a changed page publishes a
translation that quietly says something else.

Only files that need a stamp are rewritten, so a no-op run produces no diff.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translation_status import blob_sha, frontmatter_field  # noqa: E402


def _split_frontmatter(text: str) -> tuple[list[str], str] | None:
    """Return the frontmatter lines and the remainder, or None if absent."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    return text[4 : end + 1].splitlines(), text[end + 5 :]


def stamp(target: Path, sha: str, date: str) -> bool:
    """Write ``translated_from``/``translated_at`` into ``target``.

    Returns True when the file was changed.
    """
    text = target.read_text(encoding="utf-8")
    split = _split_frontmatter(text)
    if split is None:
        raise SystemExit(
            f"{target}: no frontmatter block. Every page carries frontmatter, so "
            f"this file is malformed rather than merely unstamped."
        )
    lines, body = split

    kept = [
        line
        for line in lines
        if not line.startswith("translated_from:") and not line.startswith("translated_at:")
    ]
    kept += [f"translated_from: {sha}", f"translated_at: {date}"]

    updated = "---\n" + "\n".join(kept) + "\n---\n" + body
    if updated == text:
        return False
    target.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, help="directory of source pages")
    parser.add_argument("target_root", type=Path, help="directory of translated pages")
    parser.add_argument(
        "--date",
        default=_datetime.date.today().isoformat(),
        help="value for translated_at (default: today)",
    )
    parser.add_argument(
        "--only-unstamped",
        action="store_true",
        help="leave files that already carry a translated_from value alone",
    )
    args = parser.parse_args()

    for root in (args.source_root, args.target_root):
        if not root.is_dir():
            raise SystemExit(f"{root}: not a directory")

    sources = sorted(args.source_root.rglob("*.md"))
    if not sources:
        raise SystemExit(
            f"{args.source_root}: no pages found. Stamping nothing would report "
            f"success while leaving every translation unstamped."
        )

    changed = 0
    skipped = 0
    absent = []
    for source in sources:
        relative = source.relative_to(args.source_root)
        target = args.target_root / relative
        if not target.is_file():
            absent.append(relative)
            continue
        if args.only_unstamped and frontmatter_field(target, "translated_from"):
            skipped += 1
            continue
        if stamp(target, blob_sha(source), args.date):
            changed += 1

    for relative in absent:
        print(f"untranslated: {relative}", file=sys.stderr)
    print(f"stamped {changed}, unchanged {len(sources) - changed - len(absent) - skipped}, "
          f"skipped {skipped}, untranslated {len(absent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
