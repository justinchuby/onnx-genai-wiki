#!/usr/bin/env python3
"""Report which English pages are missing, stale, or current.

The Chinese tree under ``content/zh`` is mirrored from onnx-genai and is the
source of truth. The English tree under ``content/en`` is a translation that an
agent refreshes periodically. The only thing that keeps the two from drifting
apart silently is provenance: every English page records the exact bytes of the
Chinese page it was translated from.

Each English page carries in its frontmatter::

    translated_from: <git blob sha of the Chinese source at translation time>
    translated_at: <YYYY-MM-DD>

Comparing that recorded hash against the current hash of the Chinese file gives
a precise answer to "what changed since we last translated". The hash covers
the whole file, frontmatter included. That over-reports slightly -- bumping
``updated:`` alone marks a page stale -- which is the safe direction to be
wrong in. A page needlessly re-translated costs a little work; a page wrongly
reported current is a page that quietly stops matching its source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

MISSING = "missing"
STALE = "stale"
CURRENT = "current"
ORPHANED = "orphaned"


def blob_sha(path: Path) -> str:
    """Git's blob hash for a file, computed without invoking git.

    Using git's own object hash rather than a bare sha256 means the value can
    be cross-checked with ``git hash-object`` by hand when a report is
    surprising.
    """
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - git's format


def frontmatter_field(path: Path, field: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---")
    block, delimiter, _ = rest.partition("\n---")
    if not delimiter:
        return None
    for line in block.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == field:
            return value.strip().strip("'\"") or None
    return None


@dataclass
class Entry:
    path: str
    state: str
    source_sha: str | None = None
    recorded_sha: str | None = None


def compare(source_root: Path, target_root: Path) -> list[Entry]:
    entries: list[Entry] = []
    source_pages = {
        path.relative_to(source_root).as_posix(): path
        for path in sorted(source_root.rglob("*.md"))
    }
    target_pages = {
        path.relative_to(target_root).as_posix(): path
        for path in sorted(target_root.rglob("*.md"))
    }

    for relative, source in source_pages.items():
        source_sha = blob_sha(source)
        target = target_pages.get(relative)
        if target is None:
            entries.append(Entry(relative, MISSING, source_sha, None))
            continue
        recorded = frontmatter_field(target, "translated_from")
        state = CURRENT if recorded == source_sha else STALE
        entries.append(Entry(relative, state, source_sha, recorded))

    for relative in target_pages:
        if relative not in source_pages:
            entries.append(Entry(relative, ORPHANED))

    return entries


def markdown_report(
    entries: list[Entry], counts: dict[str, int], source: Path, target: Path
) -> str:
    """Render the work list for a tracking issue.

    Only pages that need work are listed. A report that also listed the current
    ones would be mostly noise, and whoever picks the issue up would have to
    re-derive which pages they are actually being asked to touch — which is the
    step this is meant to remove.
    """
    lines = [
        f"`{source}` is the source of truth. This lists the pages of `{target}` "
        f"that do not match it.",
        "",
        f"current {counts[CURRENT]} · stale {counts[STALE]} · "
        f"missing {counts[MISSING]} · orphaned {counts[ORPHANED]}",
        "",
    ]
    headings = {
        MISSING: ("Missing", "No English page exists. Translate from the Chinese page."),
        STALE: (
            "Stale",
            "The Chinese page changed after the English one was written. Update the "
            "English page to match, then re-stamp.",
        ),
        ORPHANED: (
            "Orphaned",
            "No Chinese page of this name. The source page was renamed or deleted; "
            "delete or rename the English one to match.",
        ),
    }
    for state in (MISSING, STALE, ORPHANED):
        named = [entry for entry in entries if entry.state == state]
        if not named:
            continue
        title, explanation = headings[state]
        lines += [f"### {title} ({len(named)})", "", explanation, ""]
        for entry in named:
            lines.append(f"- [ ] `{entry.path}`")
        lines.append("")
    lines += [
        "After editing, run:",
        "",
        "```",
        f"python3 site/scripts/stamp_translations.py {source} {target}",
        "```",
        "",
        "The stamp records which revision of the Chinese page each translation was "
        "made from. Do not write `translated_from` by hand: a value typed rather "
        "than computed cannot be checked by reading the diff, and would mark a "
        "translation current whether or not it is.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Chinese content root (content/zh)")
    parser.add_argument("target", type=Path, help="English content root (content/en)")
    parser.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="output format",
    )
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="exit non-zero when any page is missing, stale, or orphaned",
    )
    args = parser.parse_args()

    if not args.source.is_dir():
        raise SystemExit(f"{args.source}: not a directory")
    args.target.mkdir(parents=True, exist_ok=True)

    entries = compare(args.source, args.target)
    counts = {
        state: sum(1 for entry in entries if entry.state == state)
        for state in (CURRENT, STALE, MISSING, ORPHANED)
    }

    if args.format == "json":
        print(json.dumps({"counts": counts, "entries": [asdict(e) for e in entries]}, indent=2))
    elif args.format == "markdown":
        print(markdown_report(entries, counts, args.source, args.target))
    else:
        for state in (MISSING, STALE, ORPHANED):
            named = [entry for entry in entries if entry.state == state]
            if named:
                print(f"{state} ({len(named)}):")
                for entry in named:
                    print(f"  {entry.path}")
        print(
            f"current: {counts[CURRENT]}, stale: {counts[STALE]}, "
            f"missing: {counts[MISSING]}, orphaned: {counts[ORPHANED]}"
        )

    needs_work = counts[STALE] + counts[MISSING] + counts[ORPHANED]
    if args.fail_on_stale and needs_work:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
