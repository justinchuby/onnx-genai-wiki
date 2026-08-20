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
translated_from: b836e6588dce315dba58ecdc5ffe0783e030bf89
translated_at: 2026-08-19
---

# onnx-genai Wiki

This directory is an Obsidian-compatible knowledge base for explanatory notes,
learning paths, and links between implementation concepts. It **does not replace**
the specifications, measured evidence, or accepted designs in `docs/`.

Published readers start at [[index|onnx-genai Knowledge Base]].

Notes are edited only here. The site is published by
[justinchuby/onnx-genai-wiki](https://github.com/justinchuby/onnx-genai-wiki),
which mirrors this directory on a schedule, derives an English edition from it,
and publishes both as a bilingual site at
<https://www.justinchuby.com/onnx-genai-wiki/>. The Chinese content there is a
mirror: editing it directly is overwritten by the next sync.

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
10. **Write for a reader who was not there.** A note may be born out of a
    conversation, but the reader cannot see that conversation. Never attribute a
    claim or an idea to the reader, and never point back to context that only
    ever existed in a dialogue — such writing leaves the reader lost, and makes
    the note read like a fragment of someone else's chat log. Rewrite the
    question as the note's own statement, so every claim carries its own
    context. The most common forms are below; everything in the left column is
    forbidden:

    <!-- voice-lint: off -->

    | Not this | This |
    |---|---|
    | As you mentioned, this is a typo | The model card writes it as X; the template writes Y |
    | Your observation is right — they are the same family | gpt-oss and Muse Glimmer share one skeleton |
    | What you called "predicting the first character" | This step is often described as "predicting the first character" |

    <!-- voice-lint: on -->

    A generic "you" addressing the implementer ("your adapter layer needs to…")
    is fine in itself, but when it can be replaced by "the caller" or "the
    supplied…" without losing information, prefer the latter.

    This rule is enforced by `scripts/lint_wiki_voice.py`, which runs in CI on
    pull requests that touch `wiki/**`. When counter-examples must be quoted, as
    in the table above, fence them with `<!-- voice-lint: off -->` /
    `<!-- voice-lint: on -->` — the exemption covers only the fenced lines, and
    it shows up in the diff.

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
attribute, so it affects real accessibility and search-engine behavior, not just
metadata. Chinese notes use `lang: zh-CN`.

> [!note] Creation and modification dates
> Obsidian can display the version-controlled `created` and `updated` properties
> in the Properties view. Obsidian also knows local filesystem creation and
> modification times, but those are not durable across clones, checkouts, and
> rebases. Core Obsidian does not automatically maintain custom `updated`
> frontmatter on every edit; update it with the note, or use a configured
> automation/plugin. See [[meta/Using this Wiki]].
