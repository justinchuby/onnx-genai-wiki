#!/usr/bin/env python3
"""Check that fenced code blocks are byte-identical across the two content trees.

A code block in these notes is almost never prose. It is rendered template
output, a shell transcript, a JSON payload, a struct definition — evidence,
copied verbatim from something that was run. Translating prose is the point of
the English edition; translating evidence silently falsifies it.

The motivating page is ``prompting/Chat Template Survey``, whose whole argument
rests on quoting what a template actually rendered. Two families are argued to
share a skeleton by putting their output side by side and observing that
``<|start|>``, ``to=`` and ``<|message|>`` line up. A translator who "helpfully"
localised a word inside one of those blocks would leave the English edition
asserting a comparison that its own evidence no longer supports, and every
existing check would still pass: the Markdown is valid, the page set is
identical, the links resolve, the wikilinks resolve.

Nothing else compares the two editions below the level of "which pages exist".

Divergence is occasionally legitimate — a block that is itself an illustrative
sentence rather than a transcript. Mark such a block by putting

    <!-- code-parity: allow-divergence -->

on the line immediately before its opening fence. The exemption covers exactly
one block, is greppable, and appears in the diff, so it cannot quietly grow into
a blanket exclusion the way a path-based allowlist does.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FENCE = "```"
ALLOW_DIVERGENCE = "<!-- code-parity: allow-divergence -->"


class Block:
    """One fenced block: where it starts, what language it claims, its body."""

    def __init__(self, line: int, info: str, body: str, exempt: bool) -> None:
        self.line = line
        self.info = info
        self.body = body
        self.exempt = exempt

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Block(line={self.line}, info={self.info!r}, exempt={self.exempt})"


def extract_blocks(text: str) -> list[Block]:
    """Return the fenced blocks of ``text`` in document order.

    Only fences that open at the start of a line are considered, which is what
    Quartz's Markdown parser does for the blocks in this wiki. An unterminated
    fence is reported by :func:`check_page` rather than silently swallowing the
    rest of the file.
    """
    blocks: list[Block] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith(FENCE):
            index += 1
            continue
        info = line[len(FENCE) :].strip()
        exempt = index > 0 and lines[index - 1].strip() == ALLOW_DIVERGENCE
        opened_at = index + 1
        body: list[str] = []
        index += 1
        closed = False
        while index < len(lines):
            if lines[index].startswith(FENCE):
                closed = True
                index += 1
                break
            body.append(lines[index])
            index += 1
        if not closed:
            raise ValueError(f"unterminated code fence opened at line {opened_at}")
        blocks.append(Block(opened_at, info, "\n".join(body), exempt))
    return blocks


def check_page(source_text: str, target_text: str) -> list[str]:
    """Return the disagreements between one page and its translation."""
    try:
        source = extract_blocks(source_text)
    except ValueError as error:
        return [f"source: {error}"]
    try:
        target = extract_blocks(target_text)
    except ValueError as error:
        return [f"target: {error}"]

    if len(source) != len(target):
        return [
            f"the source has {len(source)} code block(s) and the translation has "
            f"{len(target)}; a block was added or dropped, so they cannot be compared "
            f"pairwise"
        ]

    problems: list[str] = []
    for position, (left, right) in enumerate(zip(source, target), start=1):
        if left.exempt and right.exempt:
            continue
        if left.exempt != right.exempt:
            problems.append(
                f"block {position} (source line {left.line}, translation line "
                f"{right.line}): only one edition marks it "
                f"`{ALLOW_DIVERGENCE}`; an exemption must be agreed by both"
            )
            continue
        if left.info != right.info:
            problems.append(
                f"block {position} (source line {left.line}, translation line "
                f"{right.line}): fence info differs: {left.info!r} vs {right.info!r}"
            )
        if left.body != right.body:
            problems.append(
                f"block {position} (source line {left.line}, translation line "
                f"{right.line}): contents differ"
            )
    return problems


def check_tree(source_root: Path, target_root: Path) -> dict[str, list[str]]:
    """Compare every page that exists in both trees.

    A page missing from the translation is not this check's business — that is
    what ``translation_status.py`` reports, and duplicating it here would make a
    missing translation fail two checks with two different explanations.
    """
    findings: dict[str, list[str]] = {}
    for source_path in sorted(source_root.rglob("*.md")):
        relative = source_path.relative_to(source_root)
        target_path = target_root / relative
        if not target_path.is_file():
            continue
        problems = check_page(
            source_path.read_text(encoding="utf-8"),
            target_path.read_text(encoding="utf-8"),
        )
        if problems:
            findings[relative.as_posix()] = problems
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="the authored tree, e.g. content/zh")
    parser.add_argument("target", type=Path, help="the translated tree, e.g. content/en")
    args = parser.parse_args()

    for root in (args.source, args.target):
        if not root.is_dir():
            raise SystemExit(f"{root}: not a directory")

    findings = check_tree(args.source, args.target)
    if not findings:
        compared = sum(
            1
            for path in args.source.rglob("*.md")
            if (args.target / path.relative_to(args.source)).is_file()
        )
        print(f"Compared {compared} translated page(s); code blocks agree.")
        return 0

    for page, problems in sorted(findings.items()):
        for problem in problems:
            print(f"{page}: {problem}", file=sys.stderr)
    print(
        "\nCode blocks in these notes are evidence, not prose. A block that "
        "differs between the editions means the English page is quoting "
        "something that was never rendered. Restore the block verbatim, or mark "
        f"it `{ALLOW_DIVERGENCE}` in both editions if the divergence is "
        "deliberate.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
