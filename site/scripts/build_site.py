#!/usr/bin/env python3
"""Build the bilingual wiki site.

Quartz reads its configuration from ``quartz.config.yaml`` in the working
directory and builds one content root at a time, so a bilingual site is two
builds. Both are emitted under a single ``public/`` tree:

    public/index.html   redirect to the default locale
    public/zh/...       built from content/zh
    public/en/...       built from content/en

Keeping the two locales at sibling prefixes means the language switcher is a
pure prefix swap: any page's counterpart is the same path with ``/zh/``
exchanged for ``/en/``. That is worth more than prettier URLs for the primary
language, because a switcher that has to special-case the root locale breaks on
exactly the pages where it is hardest to notice.

The plugin install and lockfile verification run once. Both locales use the
same plugin set; only ``locale``, ``pageTitle`` and ``baseUrl`` differ.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
QUARTZ = SITE / "quartz"
SCRIPTS = SITE / "scripts"
REPOSITORY = SITE.parent
BASE_CONFIG = QUARTZ / "quartz.config.base.yaml"
CONFIG = QUARTZ / "quartz.config.yaml"

LOCALES = ("zh", "en")
DEFAULT_LOCALE = "zh"

REDIRECT = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>ONNX GenAI Wiki</title>
<link rel="canonical" href="{base_path}{default}/">
<meta http-equiv="refresh" content="0; url={base_path}{default}/">
</head>
<body>
<p><a href="{base_path}{default}/">ONNX GenAI Wiki</a></p>
</body>
</html>
"""


def run(command: list[str], cwd: Path) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def build_locale(locale: str, host: str, base_path: str, public: Path, manifest: Path) -> None:
    content = REPOSITORY / "content" / locale
    if not any(content.rglob("*.md")):
        raise SystemExit(
            f"{content}: no pages to build. An empty locale would publish an "
            f"empty site rather than fail, so this is an error."
        )

    base_url = f"{host}{base_path}{locale}"
    run(
        [
            "python3",
            str(SCRIPTS / "render_config.py"),
            str(BASE_CONFIG),
            locale,
            base_url,
            str(CONFIG),
        ],
        cwd=QUARTZ,
    )
    output = public / locale
    run(["npx", "quartz", "build", "-d", str(content), "-o", str(output)], cwd=QUARTZ)
    run(
        [
            "python3",
            str(SCRIPTS / "rewrite_repository_links.py"),
            str(output),
            "--manifest",
            str(manifest),
        ],
        cwd=QUARTZ,
    )
    run(
        [
            "python3",
            str(SCRIPTS / "validate_site.py"),
            str(output),
            f"{base_path}{locale}/",
            "--site-base",
            base_path,
        ],
        cwd=QUARTZ,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default="www.justinchuby.com",
        help="site host, without a trailing slash or scheme",
    )
    parser.add_argument(
        "--base-path",
        default="/onnx-genai-wiki/",
        help="path the site is published under, with leading and trailing slashes",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY / "content" / "source-manifest.txt",
        help="listing of tracked paths in the source repository",
    )
    parser.add_argument("--skip-plugins", action="store_true")
    parser.add_argument(
        "--serve",
        choices=LOCALES,
        help="preview one locale locally instead of building both",
    )
    args = parser.parse_args()

    base_path = args.base_path
    if not base_path.startswith("/") or not base_path.endswith("/"):
        raise SystemExit(f"--base-path must start and end with '/', got {base_path!r}")
    if not args.serve and not args.manifest.is_file():
        raise SystemExit(
            f"{args.manifest}: missing. It is written by the content sync workflow "
            f"and is what lets repository links be resolved without a checkout of "
            f"the source repository."
        )

    public = QUARTZ / "public"
    if public.exists():
        shutil.rmtree(public)
    public.mkdir(parents=True)

    run(["python3", "-m", "unittest", "discover", "-s", str(SCRIPTS / "tests")], cwd=SITE)
    for locale in LOCALES:
        run(
            ["python3", str(SCRIPTS / "validate_wikilinks.py"), str(REPOSITORY / "content" / locale)],
            cwd=SITE,
        )

    if not args.skip_plugins:
        run(
            [
                "python3",
                str(SCRIPTS / "render_config.py"),
                str(BASE_CONFIG),
                DEFAULT_LOCALE,
                f"{args.host}{base_path}{DEFAULT_LOCALE}",
                str(CONFIG),
            ],
            cwd=QUARTZ,
        )
        run(
            [
                "python3",
                str(SCRIPTS / "quartz_plugins.py"),
                "prepare",
                "quartz.config.yaml",
                "quartz.lock.json",
                ".quartz/plugins",
            ],
            cwd=QUARTZ,
        )
        run(["npx", "quartz", "plugin", "install"], cwd=QUARTZ)
        run(
            ["python3", str(SCRIPTS / "pin_graph_runtime.py"), ".quartz/plugins/graph/dist"],
            cwd=QUARTZ,
        )
        run(
            [
                "python3",
                str(SCRIPTS / "quartz_plugins.py"),
                "verify",
                "quartz.config.yaml",
                "quartz.lock.json",
                ".quartz/plugins",
            ],
            cwd=QUARTZ,
        )

    if args.serve:
        locale = args.serve
        content = REPOSITORY / "content" / locale
        run(
            [
                "python3",
                str(SCRIPTS / "render_config.py"),
                str(BASE_CONFIG),
                locale,
                f"{args.host}{base_path}{locale}",
                str(CONFIG),
            ],
            cwd=QUARTZ,
        )
        run(
            [
                "npx",
                "quartz",
                "build",
                "-d",
                str(content),
                "-o",
                str(public / locale),
                "--serve",
                "--baseDir",
                f"{base_path}{locale}".strip("/"),
            ],
            cwd=QUARTZ,
        )
        return 0

    for locale in LOCALES:
        build_locale(locale, args.host, base_path, public, args.manifest)

    # Before the switcher, so that a page present in one language only is
    # reported as the structural difference it is rather than quietly given a
    # fallback link.
    run(
        [
            "python3",
            str(SCRIPTS / "check_locale_parity.py"),
            str(public),
            "--locales",
            ",".join(LOCALES),
        ],
        cwd=QUARTZ,
    )

    # After validation, deliberately: the switcher's links point into the other
    # locale's tree, which is precisely what a per-locale link check rejects.
    run(
        [
            "python3",
            str(SCRIPTS / "inject_language_switcher.py"),
            str(public),
            "--locales",
            ",".join(LOCALES),
            "--base-path",
            base_path,
        ],
        cwd=QUARTZ,
    )

    (public / "index.html").write_text(
        REDIRECT.format(lang="zh-CN", base_path=base_path, default=DEFAULT_LOCALE),
        encoding="utf-8",
    )
    print(f"Built {', '.join(LOCALES)} into {public} under {base_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
