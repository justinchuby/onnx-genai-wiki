---
title: Using this Wiki
aliases:
  - Wiki Conventions
  - Obsidian Setup
tags:
  - wiki
  - obsidian
  - contributing
status: maintained
lang: en
created: 2026-08-17
updated: 2026-08-19
translated_from: 72b027b82c8e377e6ddcdf1e0e29651579d98a31
translated_at: 2026-08-19
---

# Using this Wiki

> [!summary] Question answered
> How should contributors open, link, date and maintain this repository wiki in Obsidian?

## Open the vault

Open the repository's `wiki/` directory as an Obsidian vault. The notes use
standard Markdown, YAML properties, wikilinks, callouts and Mermaid diagrams.
No community plugin is required to read them.

## Naming

- Use English filenames and `title` properties for stable cross-language links.
- Bodies are written in Simplified Chinese; filenames, the frontmatter `title`,
  and the page's top-level heading (H1) stay in English.
- Use descriptive noun phrases, not issue numbers or temporary project phases.
- Organize by durable domain: `start/`, `architecture/`, `execution/`, `memory/`,
  `meta/`, and future peer domains.

## Required properties

```yaml
---
title: Stable English Title
aliases:
  - Optional alternate title
tags:
  - domain
status: maintained
lang: zh-CN
created: 2026-08-17
updated: 2026-08-17
---
```

`lang` is a required field. Quartz uses its value directly as the published
page's `<html lang>` attribute (see the use of `frontmatter?.lang` in
`site/quartz/quartz/components/renderPage.tsx`), so it affects real accessibility
and search-engine behavior. Chinese notes use `lang: zh-CN`.

Suggested statuses:

| Status | Meaning |
|---|---|
| `maintained` | Intended to track current understanding |
| `proposed` | Explains a target design that is not fully implemented |
| `historical` | Preserved context, not current guidance |
| `draft` | Incomplete and not ready to rely on |

## Can Obsidian show creation and modification times?

Yes, with two different meanings:

### Version-controlled properties

`created` and `updated` appear in Obsidian's Properties view and are stored in
Git. These are the wiki's durable dates.

- Set `created` when adding a note.
- Change `updated` when materially changing its meaning.
- Do not change `updated` for whitespace-only or link-only maintenance unless the
  repository adopts a different convention.

Obsidian Core does not reliably auto-update a custom `updated` property whenever
the note changes. A Linter/Templater-style plugin or repository automation can do
that, but contributors should not need a plugin to produce valid notes.

### Filesystem timestamps

Obsidian and plugins can inspect local file creation/modification timestamps.
These are useful locally but unreliable as repository history:

- cloning creates new local files;
- checkout/rebase can change mtimes;
- different filesystems preserve metadata differently;
- Git does not version filesystem creation time.

Use Git history for exact change provenance:

```bash
git log --follow -- "wiki/path/Note.md"
```

> [!important]
> Frontmatter dates describe note-level editorial history. Git commits remain the
> authoritative record of who changed which lines and when.

## Linking

Prefer wikilinks for wiki concepts:

```markdown
[[architecture/Crate Architecture]]
[[execution/Execution Backends|backend overview]]
```

Use normal relative Markdown links for source files under `docs/` or `crates/`,
because GitHub renders them correctly and they represent formal sources:

```markdown
[Memory Architecture](../../docs/memory/MEMORY_ARCHITECTURE.md)
```

## Preview and publish the static site

The published site reads directly from `wiki/`; there is no second copy of the
notes to maintain. From the repository root:

```bash
cd site/quartz
npm ci
npm run wiki:serve
```

Open <http://localhost:8080/onnx-genai/>. Before opening a pull request, run
`npm run wiki:build` from the same directory. That command validates wikilinks,
builds the production site, and checks that generated links and assets stay
under the `/onnx-genai/` project path.

Site settings live in `site/quartz/quartz.config.yaml`; dependency versions are
recorded in the adjacent npm and Quartz lockfiles. The `Wiki Pages` workflow
builds relevant pull requests and pushes, but only a push to `main` can deploy
to GitHub Pages. Repository maintainers must select **GitHub Actions** as the
Pages source.

## Human reading budget

Each note should answer one primary question and usually take roughly 5–10
minutes to read. This is a navigation aid, not a hard size limit. Keep a longer
tutorial when a beginner needs its definitions and reasoning in one continuous
reading path.

Prefer a small map of linked notes over one chapter that tries to preserve every
implementation detail, but do not make readers chase links just to understand
the article. A wiki note should stand on its own for its intended audience.
Formal specifications and source code support verification and deeper
implementation work; they are not prerequisites for understanding the note.

## Avoid duplicated truth

Do not copy large changing status tables or exhaustive normative contracts into
the wiki. Do include enough definitions, examples and constraints for a human to
understand the topic without opening another file. Link authoritative sources
so claims remain verifiable and maintainers can find implementation details.

## Note template

```markdown
---
title: Note Title
aliases: []
tags:
  - domain
status: draft
lang: zh-CN
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# Note Title

> [!summary] 本文回答的问题
> 一句话说明读者能从这篇笔记里得到什么。

## 说明

...

## 权威来源

- [来源](../../docs/path.md)

## 相关笔记

- [[start/Repository Map]]
```
