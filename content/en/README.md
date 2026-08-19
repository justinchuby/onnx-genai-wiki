---
title: Wiki
aliases:
  - Knowledge Base
tags:
  - wiki
  - index
status: maintained
lang: en
created: 2026-08-17
updated: 2026-08-19
---

# onnx-genai Wiki

This directory is an Obsidian-compatible knowledge base for explanatory notes,
learning paths, and links between implementation concepts. It **does not replace**
the specifications, measured evidence, or accepted designs in `docs/`.

Published readers start at [[index|onnx-genai Knowledge Base]].

> [!important] Source precedence
> When a wiki note disagrees with formal documentation or code, use this order:
> 1. Current code and reproducible measurements
> 2. Authoritative documents under `docs/`
> 3. Accepted design decisions
> 4. Explanatory wiki notes

## Maps of content

- **Start here:** [[start/Repository Map]]
- **Architecture:** [[architecture/Crate Architecture]]
- **Runtime flow:** [[architecture/Inference Request Lifecycle]]
- **Execution:** [[execution/Execution Backends]]
- **EP contract:** [[execution/Execution Provider Contract]]
- **CPU EP:** [[execution/CPU Execution Provider]]
- **CUDA EP:** [[execution/CUDA Execution Provider]]
- **Plugin EPs:** [[execution/Plugin Execution Providers]]
- **Memory:** [[memory/Memory Management for Beginners]]
- **KV cache virtual memory:** [[memory/Virtual Memory for KV Cache]]
- **MoE router skew:** [[memory/MoE Router Skew and Always-On Experts]]
- **Chat templates:** [[prompting/Chat Templates]]
- **Tracing:** [[observability/Tracing and Profiling]]
- **Performance engineering:** [[performance/Performance Engineering Playbook]]
- **Chunked prefill:** [[performance/Chunked Prefill]]
- **API design:** [[api/API Design Principles]]
- **Contracts:** [[contracts/Runtime Contracts]]
- **Formal verification:** [[contracts/Formal Verification with TLA+]]
- **Testing and verification:** [[development/Testing and Verification]]
- **Metadata:** [[metadata/Metadata Driven Runtime]]
- **Model packages:** [[metadata/Model Packages and Variants]]
- **Documentation:** [[start/Documentation Guide]]
- **Wiki maintenance:** [[meta/Using this Wiki]]

## Note conventions

Every note should:

1. Use an English filename and `title` so links remain stable across languages.
2. Include YAML frontmatter with `title`, `aliases`, `tags`, `status`, `lang`,
   `created`, and `updated`.
3. Begin with a short statement of the question the note answers.
4. Answer one primary question and usually remain readable in roughly 5–10 minutes.
5. Keep a longer tutorial when shortening it would force a beginner to chase
   prerequisite explanations across other files.
6. Use `[[wikilinks]]` instead of duplicating explanations across notes.
7. Use Obsidian callouts for invariants, warnings, examples, and context.
8. Make the note self-contained for its intended reader. Links to `docs/` and code
   are evidence and implementation detail, not required homework.
9. Clearly label proposed behavior; never present a target design as implemented.

## Language

> [!important] Wiki bodies are written in Chinese; titles stay English
> This wiki's **body text is written in Simplified Chinese**. The following stay
> **in English**:
>
> - **Filenames and directory paths** — for example `execution/CUDA Execution Provider.md`
> - **The frontmatter `title` field**
> - **The page's top-level heading (H1)** — kept consistent with `title`
> - **`tags`** — tags are always English
> - **`[[wikilinks]]` link targets** — when Chinese display text is needed, use
>   `[[目标|显示文本]]`; never change the target itself on the left of the pipe
> - **Code, identifiers, crate names, file paths, environment variables, function
>   names, command lines**
> - **Obsidian callout type keywords** — such as `> [!important]`; this is syntax
>
> Section headings (H2 and below), body text, table contents, and callout title
> text should all be translated into Chinese.
>
> `aliases` may contain both Chinese and English entries — their purpose is to let
> the note be found in either language, so Chinese aliases are encouraged, but do
> **not** remove existing English aliases, as that would break existing links.
>
> Keep the original English on first use of a technical term and give the Chinese
> in parentheses, for example "execution provider(执行提供者,EP)"; afterwards the
> English abbreviation alone is fine. When the English term is itself the common
> industry name (such as kernel, arena, allocator), use the English directly and
> do not force a translation.

The `lang` field is used directly by Quartz as the published page's `<html lang>`
attribute (`renderPage.tsx`), so it affects real accessibility and search-engine
behavior, not just metadata. Chinese notes use `lang: zh-CN`.

> [!note] Creation and modification dates
> Obsidian can display the version-controlled `created` and `updated` properties
> in the Properties view. Obsidian also knows local filesystem creation and
> modification times, but those are not durable across clones, checkouts, and
> rebases. Core Obsidian does not automatically maintain custom `updated`
> frontmatter on every edit; update it with the note, or use a configured
> automation/plugin. See [[meta/Using this Wiki]].
