"""Tests for check_code_block_parity.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_code_block_parity import (
    ALLOW_DIVERGENCE,
    check_page,
    check_tree,
    extract_blocks,
)

TRANSCRIPT = """\
gpt-oss      <|start|>assistant to=functions.get_weather<|channel|>commentary
Muse Glimmer <|start|>assistant to=get_weather<|message|>
"""


def page(prose: str, body: str = TRANSCRIPT, info: str = "text") -> str:
    return f"{prose}\n\n```{info}\n{body}```\n"


class ExtractBlocksTests(unittest.TestCase):
    def test_it_reads_the_body_verbatim_including_blank_lines(self) -> None:
        blocks = extract_blocks("a\n\n```text\none\n\ntwo\n```\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].body, "one\n\ntwo")
        self.assertEqual(blocks[0].info, "text")

    def test_an_unterminated_fence_is_reported_not_swallowed(self) -> None:
        # Swallowing would make the rest of the file invisible to the check,
        # which is the failure mode that matters: a typo would exempt
        # everything after it and the check would still say it passed.
        with self.assertRaises(ValueError) as caught:
            extract_blocks("a\n\n```text\nnever closed\n")
        self.assertIn("line 3", str(caught.exception))

    def test_a_fence_indented_inside_a_list_is_not_treated_as_a_block(self) -> None:
        self.assertEqual(extract_blocks("1. item\n\n    ```text\n    x\n    ```\n"), [])


class CheckPageTests(unittest.TestCase):
    def test_identical_blocks_under_different_prose_agree(self) -> None:
        self.assertEqual(
            check_page(page("两者渲染出来的对比:"), page("Rendered side by side:")),
            [],
        )

    def test_a_single_changed_character_inside_a_block_is_caught(self) -> None:
        translated = TRANSCRIPT.replace("get_weather", "get_forecast")
        problems = check_page(page("对比:"), page("Comparison:", body=translated))
        self.assertEqual(len(problems), 1)
        self.assertIn("contents differ", problems[0])

    def test_a_translated_comment_inside_a_block_is_caught(self) -> None:
        # The realistic failure: a translator localises the one line in the
        # block that looks like prose.
        source = page("例子:", body="# 有效频道: analysis\n")
        target = page("Example:", body="# Valid channels: analysis\n")
        self.assertEqual(len(check_page(source, target)), 1)

    def test_a_dropped_block_is_reported_as_a_count_mismatch(self) -> None:
        source = page("对比:") + page("再一个:")
        problems = check_page(source, page("Comparison:"))
        self.assertEqual(len(problems), 1)
        self.assertIn("2 code block(s)", problems[0])

    def test_a_changed_fence_language_is_caught(self) -> None:
        problems = check_page(page("x"), page("x", info="json"))
        self.assertEqual(len(problems), 1)
        self.assertIn("fence info differs", problems[0])

    def test_an_exemption_agreed_by_both_editions_allows_divergence(self) -> None:
        source = f"前言\n\n{ALLOW_DIVERGENCE}\n```text\n一句话\n```\n"
        target = f"Intro\n\n{ALLOW_DIVERGENCE}\n```text\na sentence\n```\n"
        self.assertEqual(check_page(source, target), [])

    def test_a_one_sided_exemption_is_refused(self) -> None:
        # Otherwise the translation could exempt itself from the check.
        source = "前言\n\n```text\n一句话\n```\n"
        target = f"Intro\n\n{ALLOW_DIVERGENCE}\n```text\na sentence\n```\n"
        problems = check_page(source, target)
        self.assertEqual(len(problems), 1)
        self.assertIn("must be agreed by both", problems[0])

    def test_an_unterminated_fence_in_either_edition_is_reported(self) -> None:
        self.assertIn("target:", check_page(page("x"), "Intro\n\n```text\nopen\n")[0])
        self.assertIn("source:", check_page("前言\n\n```text\n开\n", page("x"))[0])


class CheckTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.source = root / "zh"
        self.target = root / "en"
        (self.source / "prompting").mkdir(parents=True)
        (self.target / "prompting").mkdir(parents=True)
        self.addCleanup(self.temporary.cleanup)

    def write(self, tree: Path, name: str, text: str) -> None:
        (tree / name).write_text(text, encoding="utf-8")

    def test_a_page_missing_from_the_translation_is_not_this_checks_business(
        self,
    ) -> None:
        # translation_status.py owns that; reporting it here too would make one
        # defect fail two checks with two different explanations.
        self.write(self.source, "prompting/Survey.md", page("对比:"))
        self.assertEqual(check_tree(self.source, self.target), {})

    def test_it_finds_the_divergent_page_among_agreeing_ones(self) -> None:
        self.write(self.source, "prompting/Survey.md", page("对比:"))
        self.write(self.target, "prompting/Survey.md", page("Comparison:"))
        self.write(self.source, "prompting/Other.md", page("另一页:"))
        self.write(
            self.target,
            "prompting/Other.md",
            page("Another:", body=TRANSCRIPT.replace("to=", "recipient=")),
        )
        findings = check_tree(self.source, self.target)
        self.assertEqual(list(findings), ["prompting/Other.md"])


class TheWikiItselfTests(unittest.TestCase):
    def test_the_published_editions_agree(self) -> None:
        # Deliberately not `skipTest` when the trees are absent. The first
        # version of this test pointed one directory too high, found nothing,
        # and skipped — reporting OK while checking nothing at all. A wrong
        # path and an absent tree look identical from here, so the only safe
        # behaviour is to fail.
        content = Path(__file__).resolve().parents[3] / "content"
        source, target = content / "zh", content / "en"
        self.assertTrue(source.is_dir(), f"{source} is not a directory")
        self.assertTrue(target.is_dir(), f"{target} is not a directory")
        self.assertEqual(
            check_tree(source, target),
            {},
            "run `python3 site/scripts/check_code_block_parity.py content/zh "
            "content/en` for the page, line and guidance",
        )


if __name__ == "__main__":
    unittest.main()
