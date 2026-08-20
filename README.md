# onnx-genai-wiki

Publishes the [onnx-genai](https://github.com/justinchuby/onnx-genai) wiki as a
bilingual site.

## Where content comes from

**The pages are not authored here.** `content/zh/` is a mirror of the `wiki/`
directory of onnx-genai, which is the source of truth. Edit a page there; a
scheduled workflow copies it across. An edit made directly to `content/zh/` in
this repository will be silently overwritten by the next sync, which is why the
mirror is replaced wholesale rather than merged.

`content/en/` is the English edition, derived from `content/zh/` by translation.
It is refreshed periodically rather than in lockstep, so it is expected to lag.
A Chinese page with no translation yet is still published on the English site,
in Chinese and labelled as untranslated, so that lag cannot break the build or
leave the language switcher pointing at a missing page. `content/en/` itself is
never written by that fallback -- a generated page there would be
indistinguishable from a real translation, and `translation_status.py` would
stop reporting the page as missing.
It lives here rather than upstream because it is a product of publishing, not a
part of the source wiki.

```
onnx-genai/wiki/  ──sync──▶  content/zh/  ──translate──▶  content/en/
   (source of truth)          (mirror)                     (derived)
```

## Layout

| Path | What it is |
| --- | --- |
| `content/zh/` | Mirrored Chinese pages. Do not edit. |
| `content/en/` | English edition. Edit here, then re-stamp. |
| `content/source-manifest.txt` | Listing of tracked paths in onnx-genai, written by the sync workflow. Repository links are resolved against it, so links can be checked without cloning the source repository. |
| `site/quartz/` | The Quartz static site generator and its configuration. |
| `site/scripts/` | Build orchestration, link rewriting and checking, translation bookkeeping. |

## Building

```
cd site/quartz
npm ci
npm run wiki:build      # both languages into site/quartz/public
npm run wiki:serve      # preview Chinese locally
npm run wiki:serve:en   # preview English locally
```

The build produces `public/zh/` and `public/en/` with a redirect at the root.
Both locales sit at sibling prefixes so the language switcher is a prefix swap;
that is worth more than a prettier URL for the primary language, because a
switcher that special-cases the root locale fails on exactly the pages where it
is hardest to notice.

`quartz.config.yaml` is **generated** from `quartz.config.base.yaml` per locale
and is not tracked. Edit the base file.

## Keeping the English edition honest

Each English page records the revision of the Chinese page it was made from:

```yaml
translated_from: <git blob sha of the Chinese page>
translated_at: 2026-08-19
```

```
python3 site/scripts/translation_status.py content/zh content/en
python3 site/scripts/stamp_translations.py content/zh content/en
```

`translation_status.py` compares the recorded sha with the source page's current
sha and reports each page as current, stale, missing or orphaned. A weekly
workflow runs it and keeps one tracking issue up to date.

Two things about the stamp are deliberate:

- **It is written by the script, never by hand.** A typed sha is a claim about a
  file the author did not hash, and cannot be checked by reading the diff.
- **It covers the whole file, frontmatter included.** So a source edit that only
  touches `updated:` marks the translation stale. That over-reports, which is the
  harmless direction: retranslating a page that did not need it costs one run,
  whereas failing to notice a changed page publishes a translation that quietly
  says something else.

The value is a git blob sha, so it can be checked by hand:

```
git hash-object "content/zh/index.md"
```

## Workflows

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `sync-content.yml` | daily, or `repository_dispatch` of type `wiki-updated` | Copies `wiki/` from onnx-genai into `content/zh/`, writes the source manifest, commits if anything changed. Refuses an implausibly small mirror rather than publishing a failed checkout. |
| `pages.yml` | push to `main` | Builds both languages and deploys to GitHub Pages. |
| `translate.yml` | weekly, and on changes to `content/zh/` | Reports drift into a single tracking issue, and closes it when the English edition catches up. |

Translation drift does not fail the publish. A stale English page is still a
page, and blocking the Chinese edition from going out because the English one
lags would punish the source of truth for the mirror's delay.

## A hazard worth knowing about

Translation can change a page's *structure* without changing a word of its
content, and no check of the Markdown can see it because the Markdown is right
in both languages.

The case that prompted the check: Obsidian reads `#word` as an inline tag when
it follows whitespace. A Chinese sentence writes `、#864/#874(WDDM 回退)`,
where the ideographic comma before the `#` stops it being a tag. The natural
English rendering is `, #864/#874 (WDDM fallback)` — same meaning, and now a tag
page called `864/874` exists in the English site and nowhere else.

`site/scripts/check_locale_parity.py` runs during the build and requires both
locales to emit exactly the same set of pages. Every page derives from something
identical across the two trees — a filename, an alias, a tag, a directory — so
any difference was introduced by the rendering rather than by an author.
