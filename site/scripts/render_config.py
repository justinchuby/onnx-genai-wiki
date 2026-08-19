#!/usr/bin/env python3
"""Render a locale-specific quartz.config.yaml from the shared base config.

Quartz reads its configuration from ``quartz.config.yaml`` in the working
directory and offers no flag to point somewhere else, so a bilingual build has
to put a different file there for each locale. Generating that file rather than
editing it in place means an interrupted build cannot leave a half-patched
config checked out, and it keeps ``quartz.config.base.yaml`` the only file a
human edits.

Only the keys that genuinely differ between locales are overridden. Everything
else -- and in particular the plugin list that ``quartz_plugins.py verify``
checks against the lockfile -- is copied through untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

LOCALES = {
    "zh": {
        "locale": "zh-CN",
        "pageTitle": "ONNX GenAI Wiki",
    },
    "en": {
        "locale": "en-US",
        "pageTitle": "ONNX GenAI Wiki",
    },
}


def render(base: Path, locale: str, base_url: str) -> str:
    if locale not in LOCALES:
        raise SystemExit(f"unknown locale {locale!r}; expected one of {sorted(LOCALES)}")

    document = yaml.safe_load(base.read_text(encoding="utf-8"))
    configuration = document.get("configuration")
    if not isinstance(configuration, dict):
        raise SystemExit(f"{base}: missing a 'configuration' mapping")

    for key, value in LOCALES[locale].items():
        if key not in configuration:
            raise SystemExit(
                f"{base}: expected key {key!r} in 'configuration' so the locale "
                f"overlay has something to override; the base config has changed "
                f"shape and this script needs updating"
            )
        configuration[key] = value

    if "baseUrl" not in configuration:
        raise SystemExit(f"{base}: expected key 'baseUrl' in 'configuration'")
    configuration["baseUrl"] = base_url

    header = (
        "# GENERATED FILE -- DO NOT EDIT.\n"
        f"# Rendered from quartz.config.base.yaml for locale {locale!r} by\n"
        "# site/scripts/render_config.py. Edit the base file instead.\n"
    )
    return header + yaml.safe_dump(document, allow_unicode=True, sort_keys=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path, help="path to quartz.config.base.yaml")
    parser.add_argument("locale", choices=sorted(LOCALES))
    parser.add_argument("base_url", help="site base URL including the locale prefix")
    parser.add_argument("output", type=Path, help="path to write quartz.config.yaml")
    args = parser.parse_args()

    args.output.write_text(render(args.base, args.locale, args.base_url), encoding="utf-8")
    print(f"Rendered {args.output} for locale {args.locale} at {args.base_url}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
