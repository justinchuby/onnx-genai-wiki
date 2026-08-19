"""Tests for rewrite_repository_links.

The wiki is published from a different repository than the one its notes link
into, so the rewriter resolves repository paths against a manifest rather than
against a checkout on disk. That indirection is the part worth pinning: a
manifest that arrives empty or malformed would make the rewriter quietly stop
rewriting rather than fail, and the published pages would keep dangling
relative links.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rewrite_repository_links import SourceIndex, github_url  # noqa: E402

MANIFEST = """
docs/memory/MEMORY_MANAGEMENT_MODEL_DESIGN.md
crates/onnx-runtime-ep-cuda/src/provider.rs
README.md
""".strip()


def index_from(text: str, tmp: Path) -> SourceIndex:
    manifest = tmp / "manifest.txt"
    manifest.write_text(text, encoding="utf-8")
    return SourceIndex.from_manifest(manifest)


class SourceIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(__file__).resolve().parent / "_tmp"
        self.tmp.mkdir(exist_ok=True)
        self.index = index_from(MANIFEST, self.tmp)

    def tearDown(self) -> None:
        for path in self.tmp.glob("*"):
            path.unlink()
        self.tmp.rmdir()

    def test_a_tracked_file_resolves_as_a_blob(self) -> None:
        self.assertEqual(
            self.index.resolve("crates/onnx-runtime-ep-cuda/src/provider.rs"),
            ("crates/onnx-runtime-ep-cuda/src/provider.rs", False),
        )

    def test_a_slug_without_its_extension_resolves_to_the_markdown_file(self) -> None:
        self.assertEqual(
            self.index.resolve("docs/memory/MEMORY_MANAGEMENT_MODEL_DESIGN"),
            ("docs/memory/MEMORY_MANAGEMENT_MODEL_DESIGN.md", False),
        )

    def test_a_directory_implied_by_the_manifest_resolves_as_a_tree(self) -> None:
        self.assertEqual(self.index.resolve("docs/memory"), ("docs/memory", True))

    def test_an_index_slug_resolves_to_its_parent_directory(self) -> None:
        self.assertEqual(self.index.resolve("docs/memory/index"), ("docs/memory", True))

    def test_a_path_absent_from_the_manifest_is_left_alone(self) -> None:
        self.assertIsNone(self.index.resolve("crates/does-not-exist/src/lib.rs"))

    def test_a_traversal_slug_is_refused(self) -> None:
        self.assertIsNone(self.index.resolve("../../etc/passwd"))
        self.assertIsNone(self.index.resolve("docs/../../secrets"))

    def test_an_empty_manifest_is_a_build_failure_not_a_silent_no_op(self) -> None:
        # A manifest that fails to generate must stop the build. If it were
        # tolerated the rewriter would resolve nothing, rewrite nothing, and
        # publish pages whose repository links point at paths the site does not
        # contain.
        tmp = Path(__file__).resolve().parent / "_empty"
        tmp.mkdir(exist_ok=True)
        try:
            with self.assertRaises(SystemExit):
                index_from("\n  \n", tmp)
        finally:
            for path in tmp.glob("*"):
                path.unlink()
            tmp.rmdir()


class GithubUrlTest(unittest.TestCase):
    def test_a_file_becomes_a_blob_url(self) -> None:
        self.assertEqual(
            github_url("docs/a b.md", False, ""),
            "https://github.com/justinchuby/onnx-genai/blob/main/docs/a%20b.md",
        )

    def test_a_directory_becomes_a_tree_url(self) -> None:
        self.assertEqual(
            github_url("docs/memory", True, ""),
            "https://github.com/justinchuby/onnx-genai/tree/main/docs/memory",
        )

    def test_a_fragment_is_preserved(self) -> None:
        self.assertEqual(
            github_url("docs/a.md", False, "section"),
            "https://github.com/justinchuby/onnx-genai/blob/main/docs/a.md#section",
        )


if __name__ == "__main__":
    unittest.main()
