#!/usr/bin/env python3
"""Add a language switcher to every built page.

The two locales are published at sibling prefixes, so a page's counterpart in
the other language is the same path with the prefix exchanged. The switcher is
therefore a plain link, computed at build time and written into the HTML.

Writing a static link into every page rather than shipping a script matters
because the site is a single-page application: navigation replaces the body
with the *target page's* markup. A switcher injected by script at load time
would disappear on the first internal navigation, and would do so only in the
built site, where it is least likely to be noticed. A link that is present in
every page's markup survives navigation because the page navigated to has one
too.

The link is absolute, which is why this step runs after ``validate_site.py``.
That validator checks each locale's output in isolation and against its own
base path, so a link pointing into the *other* locale is exactly the thing it
is built to reject. Injecting first would either fail the build or force the
validator to be loosened, and loosening it would also stop it catching real
escapes from the published tree.

A page whose counterpart does not exist links to the other locale's home page
instead. That is the honest fallback for a translation that has not been
written yet: a link to a page that does not exist would be a 404, and no link
at all would leave the reader with no way across.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

# Rendered into the left sidebar, which every content, folder and tag page has.
ANCHOR = '<div class="left sidebar">'

LABELS = {"zh": "中文", "en": "English"}
HREFLANG = {"zh": "zh-CN", "en": "en"}

STYLE = (
    "display:flex;justify-content:flex-end;font-size:0.9rem;"
    "opacity:0.8;margin-bottom:0.4rem"
)


def is_redirect_stub(markup: str) -> bool:
    """Alias stubs redirect immediately and render no chrome to attach to."""
    return 'http-equiv="refresh"' in markup


def page_url(base_path: str, locale: str, relative: Path) -> str:
    """URL for a built page, in the extensionless form Quartz links to."""
    parts = list(relative.parts)
    if parts[-1] == "index.html":
        parts.pop()
        # A folder page's URL keeps its trailing slash, matching what Quartz
        # emits; without it the server redirects and the SPA router loses the
        # navigation.
        suffix = "".join(f"{part}/" for part in parts)
    else:
        parts[-1] = parts[-1][: -len(".html")]
        suffix = "/".join(parts)
    return f"{base_path}{locale}/{suffix}"


def switcher(base_path: str, other: str, relative: Path, counterpart_exists: bool) -> str:
    href = page_url(base_path, other, relative) if counterpart_exists else f"{base_path}{other}/"
    title = (
        ""
        if counterpart_exists
        else ' title="This page has not been translated yet; the link goes to the home page."'
    )
    label = html.escape(LABELS[other])
    lang = HREFLANG[other]
    return (
        f'<div class="language-switcher" style="{STYLE}">'
        f'<a href="{html.escape(href)}" hreflang="{lang}" lang="{lang}"{title}>{label}</a>'
        f"</div>"
    )


def inject(public: Path, locales: list[str], base_path: str) -> dict[str, tuple[int, int]]:
    """Inject the switcher into every page of every locale.

    Returns per-locale (injected, skipped-as-redirect-stub) counts.
    """
    results: dict[str, tuple[int, int]] = {}
    unknown = [locale for locale in locales if locale not in LABELS]
    if unknown:
        raise SystemExit(
            f"no label or hreflang defined for {unknown!r}. Adding a locale means "
            f"naming it in the reader's own language, which cannot be derived."
        )
    for locale in locales:
        others = [candidate for candidate in locales if candidate != locale]
        if len(others) != 1:
            raise SystemExit(
                f"the switcher is a two-language control; got locales {locales!r}"
            )
        other = others[0]
        root = public / locale
        if not root.is_dir():
            raise SystemExit(f"{root}: missing. Build the locale before injecting.")

        injected = 0
        stubs = 0
        unanchored = []
        for page in sorted(root.rglob("*.html")):
            markup = page.read_text(encoding="utf-8")
            if is_redirect_stub(markup):
                stubs += 1
                continue
            if ANCHOR not in markup:
                unanchored.append(page.relative_to(root))
                continue
            relative = page.relative_to(root)
            counterpart = (public / other / relative).is_file()
            control = switcher(base_path, other, relative, counterpart)
            page.write_text(markup.replace(ANCHOR, ANCHOR + control, 1), encoding="utf-8")
            injected += 1

        if unanchored:
            listing = ", ".join(str(path) for path in unanchored[:5])
            raise SystemExit(
                f"{root}: {len(unanchored)} page(s) have no {ANCHOR!r} to attach the "
                f"switcher to ({listing}). The layout changed; a silent skip here "
                f"would publish pages with no way to reach the other language."
            )
        if injected == 0:
            raise SystemExit(
                f"{root}: no pages received a switcher. An empty result means the "
                f"anchor or the output layout moved, not that there was nothing to do."
            )
        results[locale] = (injected, stubs)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path, help="directory holding the per-locale output")
    parser.add_argument("--locales", default="zh,en")
    parser.add_argument("--base-path", default="/onnx-genai-wiki/")
    args = parser.parse_args()

    if not args.base_path.startswith("/") or not args.base_path.endswith("/"):
        raise SystemExit(f"--base-path must start and end with '/', got {args.base_path!r}")

    locales = [item.strip() for item in args.locales.split(",") if item.strip()]
    results = inject(args.public, locales, args.base_path)
    for locale, (injected, stubs) in results.items():
        print(f"{locale}: switcher on {injected} page(s), {stubs} redirect stub(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
