"""Tests for render_config.py.

This script was the only one in site/scripts with a third-party import and the
only one with no test, which is why the first CI run failed on ``import yaml``
rather than on anything the suite could see. Importing the module here means a
missing dependency now fails the test step with a clear traceback instead of
failing mid-build.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from render_config import render

BASE = """\
# a comment
configuration:
  pageTitle: ONNX GenAI Wiki
  locale: zh-CN
  baseUrl: www.example.com/wiki
  theme:
    colors:
      lightMode:
        light: "#faf8f8"
plugins:
  - source: github:quartz-community/explorer
    enabled: true
    layout:
      position: left
"""


class RenderConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name) / "quartz.config.base.yaml"
        self.base.write_text(BASE, encoding="utf-8")

    def render(self, source: str, locale: str = "en", url: str = "example.com/en") -> dict:
        self.base.write_text(source, encoding="utf-8")
        return yaml.safe_load(render(self.base, locale, url))

    def test_locale_overlay_is_applied(self) -> None:
        document = self.render(BASE, locale="en", url="example.com/en")
        self.assertEqual(document["configuration"]["locale"], "en-US")
        self.assertEqual(document["configuration"]["baseUrl"], "example.com/en")

    def test_zh_keeps_its_own_locale(self) -> None:
        document = self.render(BASE, locale="zh", url="example.com/zh")
        self.assertEqual(document["configuration"]["locale"], "zh-CN")

    def test_everything_outside_the_overlay_is_copied_through(self) -> None:
        # The plugin list is what quartz_plugins.py verifies against the
        # lockfile, so a render that dropped or reordered it would produce a
        # site that passes its own checks and is missing features.
        document = self.render(BASE)
        self.assertEqual(document["plugins"], yaml.safe_load(BASE)["plugins"])
        self.assertEqual(
            document["configuration"]["theme"],
            yaml.safe_load(BASE)["configuration"]["theme"],
        )

    def test_output_is_marked_generated(self) -> None:
        # Without this a human edits the rendered file and loses the edit on
        # the next build.
        text = render(self.base, "en", "example.com/en")
        self.assertIn("GENERATED FILE", text.splitlines()[0])

    def test_unknown_locale_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            render(self.base, "fr", "example.com/fr")

    def test_a_base_config_that_lost_a_key_is_refused(self) -> None:
        # Silently adding the key back would let a rename upstream turn the
        # overlay into a no-op, publishing every locale with the same settings.
        for missing in ("locale", "pageTitle", "baseUrl"):
            with self.subTest(missing=missing):
                document = yaml.safe_load(BASE)
                del document["configuration"][missing]
                self.base.write_text(yaml.safe_dump(document), encoding="utf-8")
                with self.assertRaises(SystemExit):
                    render(self.base, "en", "example.com/en")

    def test_a_base_config_without_a_configuration_mapping_is_refused(self) -> None:
        self.base.write_text("plugins: []\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            render(self.base, "en", "example.com/en")


if __name__ == "__main__":
    unittest.main()
