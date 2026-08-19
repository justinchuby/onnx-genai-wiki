#!/usr/bin/env python3
"""Rewrite generated links to repository files as GitHub source links."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from urllib.parse import quote, urlparse

ANCHOR = re.compile(r"<a\b(?P<attrs>[^>]*\bdata-slug=\"(?P<slug>[^\"]+)\"[^>]*)>")
BODY_SLUG = re.compile(r"<body\b[^>]*\bdata-slug=\"([^\"]+)\"")
HREF = re.compile(r'\bhref="([^"]*)"')
CLASS = re.compile(r'\bclass="([^"]*)"')
FOOTER_YEAR = re.compile(
    r'(Created with <a href="https://quartz\.jzhao\.xyz/">Quartz</a>) © \d{4}'
)


class SourceIndex:
    """The set of paths that exist in the source repository.

    The wiki is published from a different repository than the one it links
    into, so the source tree is not on disk here. A manifest -- one tracked
    path per line, as produced by ``git ls-files`` in the source repository --
    stands in for it, which keeps the existence check real rather than
    rewriting every link that merely looks like a repository path.
    """

    def __init__(self, files: set[str]) -> None:
        self.files = files
        self.directories: set[str] = set()
        for path in files:
            parts = path.split("/")
            for index in range(1, len(parts)):
                self.directories.add("/".join(parts[:index]))

    @classmethod
    def from_manifest(cls, manifest: Path) -> "SourceIndex":
        files = {
            line.strip().strip("/")
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        if not files:
            raise SystemExit(
                f"{manifest}: manifest is empty. Without it every repository link "
                f"silently stays unrewritten, so this is a build failure rather "
                f"than a no-op."
            )
        return cls(files)

    @classmethod
    def from_directory(cls, repository: Path) -> "SourceIndex":
        repository = repository.resolve()
        files = {
            path.relative_to(repository).as_posix()
            for path in repository.rglob("*")
            if path.is_file()
        }
        return cls(files)

    def resolve(self, slug: str) -> tuple[str, bool] | None:
        clean_slug = html.unescape(slug).strip("/")
        if not clean_slug or clean_slug.startswith("../") or ".." in clean_slug.split("/"):
            return None
        for candidate in (clean_slug, f"{clean_slug}.md"):
            if candidate in self.files:
                return candidate, False
        if clean_slug.endswith("/index"):
            parent = clean_slug.removesuffix("/index")
            if parent in self.directories:
                return parent, True
        if clean_slug in self.directories:
            return clean_slug, True
        return None


def github_url(relative: str, is_directory: bool, fragment: str) -> str:
    kind = "tree" if is_directory else "blob"
    url = f"https://github.com/justinchuby/onnx-genai/{kind}/main/{quote(relative, safe='/')}"
    if fragment:
        url += f"#{quote(fragment, safe='-._~')}"
    return url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("public", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--manifest",
        type=Path,
        help="file listing every tracked path in the source repository",
    )
    source.add_argument(
        "--repository",
        type=Path,
        help="local checkout of the source repository, when one is available",
    )
    args = parser.parse_args()
    public = args.public.resolve()
    index = (
        SourceIndex.from_manifest(args.manifest)
        if args.manifest
        else SourceIndex.from_directory(args.repository)
    )
    html_files = sorted(public.rglob("*.html"))
    site_slugs: set[str] = set()
    documents: dict[Path, str] = {}

    for path in html_files:
        document = path.read_text(encoding="utf-8")
        documents[path] = document
        if match := BODY_SLUG.search(document):
            site_slugs.add(html.unescape(match.group(1)))

    rewritten = 0
    for path, document in documents.items():

        def replace_anchor(match: re.Match[str]) -> str:
            nonlocal rewritten
            slug = html.unescape(match.group("slug"))
            attrs = match.group("attrs")
            href_match = HREF.search(attrs)
            href = html.unescape(href_match.group(1)) if href_match else ""
            repository_reference = "/./../" in href
            if slug in site_slugs and not repository_reference:
                return match.group(0)
            target = index.resolve(slug)
            if target is None:
                return match.group(0)
            relative, is_directory = target
            fragment = urlparse(html.unescape(href_match.group(1))).fragment if href_match else ""
            url = html.escape(github_url(relative, is_directory, fragment), quote=True)
            if href_match:
                attrs = HREF.sub(f'href="{url}"', attrs, count=1)
            else:
                attrs = f' href="{url}"{attrs}'
            attrs = re.sub(r'\sdata-slug="[^"]*"', "", attrs, count=1)

            def external_class(class_match: re.Match[str]) -> str:
                classes = class_match.group(1).split()
                classes = ["external" if value == "internal" else value for value in classes]
                if "external" not in classes:
                    classes.append("external")
                return f'class="{" ".join(classes)}"'

            if CLASS.search(attrs):
                attrs = CLASS.sub(external_class, attrs, count=1)
            else:
                attrs += ' class="external"'
            rewritten += 1
            return f"<a{attrs}>"

        updated = ANCHOR.sub(replace_anchor, document)
        updated = FOOTER_YEAR.sub(r"\1 · onnx-genai", updated)
        if updated != document:
            path.write_text(updated, encoding="utf-8")

    print(f"Rewrote {rewritten} repository source link(s) to GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
