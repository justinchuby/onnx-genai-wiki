# Vendored from the source repository

Everything in this directory is mirrored from `justinchuby/onnx-genai` by
`.github/workflows/sync-content.yml`, exactly as `content/zh` is. **Do not edit
it here.** A change made here is silently reverted by the next sync, which is
worse than not being able to make it.

- `lint_wiki_voice.py` — from `scripts/lint_wiki_voice.py`. It enforces the
  rule that a note must read for someone who was not in the conversation that
  produced it. The rule and the linter are defined upstream because the
  Chinese pages are; mirroring it means the English edition is held to the
  same definition rather than to a copy of it that has drifted.
