---
title: Chat Template Survey
aliases:
  - 对话模板横向调研
  - Chat Template Comparison
  - Tool Calling Formats
tags:
  - models
  - tokenizer
  - prompt
  - tools
  - survey
status: maintained
lang: en
created: 2026-08-19
updated: 2026-08-19
translated_from: 182248e253324dc32d268045083bdc84bd523258
translated_at: 2026-08-19
---

# Chat Template Survey

> [!summary] Question answered
> Just how different are the chat templates across vendors? How does tool calling actually land at
> the template layer? What differences must an adapter layer be ready to handle to be compatible
> with them — and which differences **don't raise an error, they just quietly drop data**?

This note is a cross-sectional companion to [[prompting/Chat Templates]]. That one is about the
mechanism; this one is about the **distribution**: 54 real templates, 53 that parse, 49 that render
a full turn of tool-calling conversation.

## 1. Method: render, don't read

Method first, because the credibility of every conclusion here depends on it.

**Reading a template will lead you astray.** Jinja branches run deep; a condition like
`{%- if builtin_tools is defined -%}` decides that one and the same template renders something
completely different. None of the assertions here are "read off" the template source; every one
comes from **actually rendering the template** and then reading the output.

The input is held constant — the same conversation throughout: one system message, one user
question, one assistant message carrying `tool_calls` (with both `reasoning_content` and `thinking`
attached), one tool result, one assistant reply, then another user question, with
`add_generation_prompt=True`.

To make "did it actually render or not" decidable, every field in the input is filled with a
**unique sentinel string** (`ZCITYZ`, `ZRESULTZ`, `ZREASONZ`, …), and then the output is searched
for whether those strings are present.

> [!warning] I got this step wrong once
> The first version of the probe used `reasoning_content="R"` and then judged whether the reasoning
> segment was preserved by "does the output contain a capital R". As a result unrelated text like
> `Reasoning: medium` and `RES` all counted as hits, and the whole column of conclusions was wrong.
> **A sentinel must be unique enough that it cannot occur by accident**, otherwise what you are
> measuring is coincidence.

The render environment is Jinja2's `ImmutableSandboxedEnvironment`, with the `raise_exception`,
`strftime_now`, and `tojson` that HF injects filled in, plus an implementation of transformers'
`{% generation %}` tag (it marks the assistant mask used at training time; standard Jinja2 doesn't
have it, and without it templates like SmolLM3 don't even parse).

The minimal skeleton to reproduce it:

```python
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2.exceptions import TemplateError
import json, datetime

env = ImmutableSandboxedEnvironment(
    trim_blocks=True, lstrip_blocks=True,
    extensions=["jinja2.ext.loopcontrols"])
env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(TemplateError(m))
env.globals["strftime_now"]    = lambda f: datetime.datetime.now().strftime(f)
env.filters["tojson"]          = lambda o, **k: json.dumps(o, ensure_ascii=False)

out = env.from_string(src).render(
    messages=msgs, tools=tools, add_generation_prompt=True,
    bos_token="<BOS>", eos_token="<EOS>")
```

### Sample and sources

Templates are taken from the `chat_template.jinja` in each Hugging Face repository, falling back to
the `chat_template` field of `tokenizer_config.json` when that file is absent; fetch date
2026-08-19.

> [!note] Gated models went through mirrors
> The official repositories for Llama, Gemma, and Command-R require authorization (HTTP 401). The
> Llama and Gemma templates are taken from `unsloth/*` re-upload mirrors; both Command-R mirrors
> were also 401 and are **not included in this note**. Whether the mirrors are byte-for-byte
> identical to the official repos has not been verified here, so discount the related conclusions as
> "from a mirror". All other models are official repositories.

## 2. Axis one: how a single turn is framed

Across the 54 templates, the ways of delimiting a turn largely fall into a few families. Every
marker in the rows below is lifted from the **rendered output**, not from the template source.

| Family | Representative | Frame of the assistant turn |
|---|---|---|
| ChatML | Qwen (all), Hermes, Olmo 3, Yi | `<\|im_start\|>assistant\n` … `<\|im_end\|>` |
| Llama 3.x | Llama 3.1 / 3.3 | `<\|start_header_id\|>assistant<\|end_header_id\|>\n\n` … `<\|eot_id\|>` |
| Llama 4 | Llama 4 Scout | `<\|header_start\|>assistant<\|header_end\|>\n\n` … `<\|eot\|>` |
| Harmony family | gpt-oss, Muse Glimmer | `<\|start\|>assistant` … `<\|message\|>` … `<\|end\|>` / `<\|eot\|>` |
| Square brackets | Mistral (all) | `[INST]` … `[/INST]` |
| Gemma | Gemma 2 / 3 | `<start_of_turn>model\n` … `<end_of_turn>` |
| Pipe-delimited role | GLM-4.5, EXAONE, Granite | `<\|assistant\|>`, `[\|assistant\|]`, `<\|start_of_role\|>assistant<\|end_of_role\|>` |
| Other | Kimi K2, MiniMax-M2, Nemotron | `<\|im_assistant\|>assistant<\|im_middle\|>`, `[e~[\n]~b]ai`, `<SPECIAL_11>Assistant` |

MiniMax-M2's `[e~[\n]~b]` is worth a separate look — the delimiter carries a literal newline escape,
which is a reminder of one thing: **don't assume a delimiter is a string that "looks like a
marker"**; it is merely a run of tokens that was used during training.

## 3. Axis two: reasoning segments — two camps, channel vs paired tags

### Camp one: channel (Harmony family)

gpt-oss and Muse Glimmer use the **same family of format**. Not "similar" — they share one and the
same skeleton:

```text
<|start|>{sender} to={recipient} [<|channel|>{channel}] <|message|>{content}{stop}
```

A verbatim comparison of the tool call each renders:

```text
gpt-oss      <|start|>assistant to=functions.get_weather<|channel|>commentary json<|message|>{"city": "Paris"}<|call|>
Muse Glimmer <|start|>assistant to=get_weather<|message|><atem:function_calls>…</atem:function_calls><|eot|>
```

The trio of `<|start|>`, `to=`, and `<|message|>` is exactly the same. There are only two
differences:

1. **gpt-oss has one extra, orthogonal `<|channel|>` dimension.** It has both a "recipient" (`to=`)
   and a "channel" (`analysis` / `commentary` / `final`), the two independent; Muse Glimmer merges
   them into a single `to=`, using `to=self` to express gpt-oss's `analysis` and `to=user` to
   express `final`.
2. **The terminators differ.** gpt-oss uses three — `<|end|>` / `<|call|>` / `<|return|>`; Muse
   Glimmer uses two — `<|eot|>` / `<|eom|>`.

gpt-oss even writes the channel list into the system block — the same move as Muse Glimmer writing
`# Valid recipients:`:

```text
# Valid channels: analysis, commentary, final. Channel must be included for every message.
Calls to these tools must go to the commentary channel: 'functions'.
```

So it is accurate to view them as two variants of the same design.

### The other camp: paired tags

Almost all the other reasoning-capable models use **paired tags** rather than a channel:

| Tag | Models |
|---|---|
| `<think>` / `</think>` | Qwen3, QwQ, DeepSeek-R1, DeepSeek-V3.1, GLM-4.5, EXAONE 4.0, MiniMax-M2, Nemotron family, Baichuan-M2, Ling, Skywork, MiniCPM 4.1 |
| `<seed:think>` | Seed-OSS |
| `[THINK]` / `[/THINK]` | Magistral |

### The difference between the camps: the marker is in the header, or in the content

The difference between the camps is not aesthetic. **A channel is structural; a paired tag is inside
the text.** With tags, the runtime has to do string matching in the generated text stream to know
where the reasoning segment ends; with a channel, the recipient is written in the message header, so
the parser knows as soon as it reads the header, without waiting for the content.

### A more consequential difference: who is responsible for dropping historical reasoning segments

Reasoning segments should not be back-filled into later turns (see [[prompting/Chat Templates]]).
But **who does this differs from vendor to vendor**, and that directly decides whether the adapter
layer has to do it itself.

Measured directly: for the same history carrying `reasoning_content` and `thinking`, whether the
sentinel string is still present after rendering — of the 49 renderable templates, only **2**
preserved it: `ByteDance-Seed/Seed-OSS-36B-Instruct` and `meta-models/Muse-Glimmer-30B`.

In other words:

- **The vast majority of templates drop historical reasoning segments on their own.** gpt-oss's
  template even carries the comment *"CoT is dropped during all previous turns, so we never render it
  for inference"*. Passing it in is wasted effort but has no side effect.
- **Seed-OSS and Muse Glimmer faithfully render the reasoning segments they are passed.** For these
  two models, "not back-filling historical reasoning" is **the caller's responsibility**; code
  written on the assumption that "the template will drop it anyway" will, on these two models, stuff
  all the historical thinking back into the context.

> [!important] Conclusion
> The rule "don't back-fill reasoning segments" cannot be relied on the template to honor. Either the
> caller itself constructs `messages` without historical `reasoning_content`, or it has to be
> confirmed per model. The former is always correct; the latter means maintaining a table.

## 4. Axis three: tool calling

This is the axis with the most variation. It is really **three mutually independent mechanisms**, and
a model can implement only part of them — which is exactly the source of the silent failures in the
next section.

### Part 1: where the tool definitions are injected

| Location | Models |
|---|---|
| Inside the system block | Qwen (all), GLM-4.5, Kimi K2, Granite, Muse Glimmer, Seed-OSS |
| A separate developer turn | gpt-oss |
| **The user turn** | Llama 3.1 / 3.3 |
| A separate `available_tools` turn | Granite 3.3 |
| A dedicated `[AVAILABLE_TOOLS]` section | Mistral (all) |
| A self-built system block (placed before the caller's system) | Hermes 3 |
| **Not injected at all** | DeepSeek-R1, DeepSeek-V3.1 |

Two counterintuitive ones:

**Llama 3.1 writes the tool definitions into the user turn**, not the system:

```text
<|start_header_id|>user<|end_header_id|>

Given the following functions, please respond with a JSON for a function call ...
{"type": "function", "function": {"name": "get_weather", ...}}

Weather in Paris?<|eot_id|>
```

**DeepSeek-R1 / V3.1 simply ignore the `tools` argument.** Measured: the sentinel strings of the tool
descriptions do not appear in the output at all, yet they **can** render `tool_calls` and tool
results. That is, for these two models the tool definitions **must be written into the system prompt
by the caller**; passing `tools=[...]` does nothing, and raises no error.

The description format is not uniform either. gpt-oss converts the JSON Schema into a **TypeScript
declaration**:

```text
namespace functions {
// Get weather.
type get_weather = (_: {
// City
city: string,
}) => any;
} // namespace functions
```

Muse Glimmer, by contrast, writes a large block of natural language + XML usage examples + a schema
list. Hermes 3 stuffs the schema in together with a stretch of pydantic-model explanation, and
**starts a separate system turn** to hold the caller's system — so the rendered result contains **two
consecutive system blocks**.

### Part 2: the syntax the assistant uses to issue a call

All lifted from the rendered output, verbatim:

| Model | What the assistant's call looks like |
|---|---|
| Qwen3 / Hermes / Granite 4 / EXAONE / Ling | `<tool_call>\n{"name": "get_weather", "arguments": {"city": "Paris"}}\n</tool_call>` |
| Llama 3.1 / 3.3 | `{"name": "get_weather", "parameters": {"city": "Paris"}}` (bare JSON — note the key is `parameters`) |
| **Llama 4** | `[get_weather(city="Paris")]` (Python call syntax) |
| **Olmo 3** | `<function_calls>get_weather(city="Paris")</function_calls>` |
| Mistral v0.3 | `[TOOL_CALLS] [{"name": …, "arguments": {…}, "id": "abcdefghi"}]` |
| Mistral Small 3.2 | `[TOOL_CALLS]get_weather[CALL_ID]call_abc12[ARGS]{"city": "Paris"}` |
| Magistral | `[TOOL_CALLS]get_weather[ARGS]{"city": "Paris"}` |
| gpt-oss | `<\|start\|>assistant to=functions.get_weather<\|channel\|>commentary json<\|message\|>{"city": "Paris"}<\|call\|>` |
| Muse Glimmer | `<atem:invoke name="get_weather"><atem:parameter name="city">Paris</atem:parameter></atem:invoke>` |
| MiniMax-M2 | `<minimax:tool_call><invoke name="get_weather"><parameter name="city">Paris</parameter></invoke></minimax:tool_call>` |
| step3 | `<steptml:invoke name="get_weather"><steptml:parameter name="city">Paris</steptml:parameter></steptml:invoke>` |
| Seed-OSS | `<seed:tool_call><function=get_weather><parameter=city>Paris</parameter></function></seed:tool_call>` |
| GLM-4.5 | `<tool_call>get_weather\n<arg_key>city</arg_key>\n<arg_value>Paris</arg_value>\n</tool_call>` |
| Kimi K2 | `<\|tool_calls_section_begin\|><\|tool_call_begin\|>call_abc12<\|tool_call_argument_begin\|>{"city": "Paris"}<\|tool_call_end\|>` |
| DeepSeek-V3.1 | `<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>get_weather<｜tool▁sep｜>{"city": "Paris"}<｜tool▁call▁end｜>` |
| Nemotron Nano | `<TOOLCALL>[{"name": "get_weather", "arguments": {"city": "Paris"}}]</TOOLCALL>` |
| Falcon3 | `<tool_call>\n[{"id": …, "type": "function", "function": {…}}]\n</tool_call>` |

A few points that will directly save you debugging time:

- **`<tool_call>` + JSON is the de facto majority**, with Qwen's form widely reused. If you only want
  to support one parser, support it first.
- **Llama 3.1 uses the key `parameters`, not `arguments`.** Different from the OpenAI wire format.
- **XML-style calls are becoming more common.** Muse Glimmer (`atem:`), MiniMax (`minimax:`), step3
  (`steptml:`), and Seed-OSS all follow the same idea, only swapping the namespace prefix. Their
  shared motive is to avoid making the model output strictly valid JSON — Muse Glimmer's template
  states outright *"The output is not expected to be valid XML and is parsed with regular
  expressions."*
- **Llama 4 and Olmo 3 make the model write function-call code**, not JSON. Parsing these two means
  writing an expression parser; you can't use `json.loads`.

> [!warning] `<|python_tag|>` is a common misconception
> It is often said online (and in earlier versions of this wiki) that Llama 3.1 issues a tool call
> with `<|python_tag|>{...}<|eom_id|>`. **The default path is not like that.** Reading the template
> shows that `<|python_tag|>` appears only when `builtin_tools is defined` **and** the called
> function is in `builtin_tools` (built-in tools like `brave_search`, `wolfram_alpha`); `<|eom_id|>`
> is likewise only used when `builtin_tools is defined`. Passing plain `tools=[...]` renders as
> **bare JSON + `<|eot_id|>`**, which is exactly what the table above measured.

### Part 3: how tool results are fed back

The role names are even more of a mess than the call syntax:

| Role used for the result | Models |
|---|---|
| `tool` | Hermes 3, Muse Glimmer (`<\|start\|>tool get_weather`) |
| **`user`** | Qwen (all), Granite 4, Nemotron |
| `ipython` | Llama 3.1 / 3.3 / 4 |
| `observation` | GLM-4.5 (`<\|observation\|>`) |
| `OBSERVATION` | Ling |
| `environment` | Olmo 3 |
| `[\|tool\|]` | EXAONE 4.0 |
| `<\|im_system\|>{function name}` | Kimi K2 |
| `functions.{function name} to=assistant` | gpt-oss |
| Dedicated section, no role | Mistral (`[TOOL_RESULTS]`), DeepSeek (`<｜tool▁output▁begin｜>`) |
| **`assistant`** | Falcon3 |

**Qwen rendering the tool result as a `user` turn** is the easiest one to trip on — in the template
it is `<|im_start|>user\n<tool_response>\n…\n</tool_response>`. Two attendant details:

1. Multiple consecutive tool results are **merged into the same user turn** (the template checks
   whether the previous message was also a `tool`).
2. To find "the last genuine user message", Qwen3 relies on **detecting whether a user message is
   wrapped in `<tool_response>`** to exclude tool results:
   ```jinja
   {%- if ns.multi_step_tool and message.role == "user" and message.content is string
        and not(message.content.startswith('<tool_response>')
        and message.content.endswith('</tool_response>')) %}
   ```
   That is, **if the user themselves sends a message that starts and ends with `<tool_response>`,
   Qwen3 will misjudge it as a tool result.** This is a genuine ambiguity that exists at the template
   layer.

Falcon3 hangs the tool result under the `<|assistant|>` header (line 24 of the template), effectively
making the assistant "say" the tool's output itself. This one I am inclined to consider a template
defect rather than a design.

## 5. Input conventions: the same OpenAI shape is not universal

The `messages` / `tools` structures the caller provides look like a uniform OpenAI shape, but
templates do not expect the same thing from it. Every cell below was **rendered and verified
separately** (after the baseline configuration renders, flip a single axis on its own and run again),
not reverse-engineered from "the first combination that rendered" — that would only prove one form
works, not that another fails.

| Convention | Conclusion |
|---|---|
| `arguments` passed as a **dict** | 47/49 accept. **DeepSeek-R1, DeepSeek-V3.1 raise an error** (they want a JSON string) |
| `arguments` passed as a **JSON string** | **GLM-4.5, MiniMax-M2, Seed-OSS, Olmo 3, step3, Muse Glimmer raise an error** |
| `tool_call_id` not 9 characters | **Mistral v0.3, Mistral-Nemo raise an error**: *"Tool call IDs should be alphanumeric strings with length 9!"* |
| `tools` using a flat structure (not wrapped in `function`) | gpt-oss, MiniMax-M2, Mistral v0.3 raise an error; **Apertus, conversely, accepts only a flat structure** |

The most useful thing in this table is the first two rows read together: **no single way of writing
`arguments` works for everything.** A dict is rejected by DeepSeek; a string is rejected by the other
six. The adapter layer has to convert per model.

Qwen3 is the only one that explicitly handles both forms in its template:

```jinja
{%- if tool_call.arguments is string %}
    {{- tool_call.arguments }}
{%- else %}
    {{- tool_call.arguments | tojson }}
{%- endif %}
```

Both inputs render byte-for-byte identically in testing. This is a good example of defensive writing:
**it absorbs a burden of the adapter layer into the template**.

Mistral's 9-character ID is the most famous pitfall of all. An ID in OpenAI's `call_abc123...` form
triggers the exception outright. Note this one is **only in the older templates**: Mistral-Small-3.2,
Devstral, and Magistral have already removed this check.

## 6. Silent failure: far more dangerous than an error

The ones above at least throw an exception. The truly dangerous case is **rendering succeeds, but the
content is gone**.

### 6.1 Renders the tool definitions, but drops the tool call

These three templates render `tools` into the prompt, but **nowhere in the entire template is
`message.tool_calls` referenced** (grep hit count: 0):

- `ibm-granite/granite-3.3-8b-instruct`
- `HuggingFaceTB/SmolLM3-3B`
- `zai-org/GLM-4-9B-0414`

The consequence: a history of "assistant called a tool → tool returned → assistant answered" renders
as

```text
<|start_of_role|>assistant<|end_of_role|><|end_of_text|>
```

**The assistant turn becomes empty**, and the tool call vanishes into thin air. The history the model
sees is "it said nothing, and then the tool result appeared". No error, no warning.

Their design intent is for the model to write the call **into `content`** (Granite 3.3's system
prompt says *"respond only with `<|tool_call|>` followed by a JSON list of tools used"*), so the
caller must put the tool call into `content` as text, not into the structured `tool_calls` field.

### 6.2 Ignores the `tools` argument

`deepseek-ai/DeepSeek-R1` and `deepseek-ai/DeepSeek-V3.1`: pass `tools=[...]`, and the sentinel
strings of the tool descriptions are **entirely absent** from the rendered output. The tool
definitions must be written into the system prompt yourself.

### 6.3 No tool support at all

12 templates render neither definitions nor calls: Yi-1.5, ChatGLM3, OLMo-2, ERNIE-4.5,
DeepSeek-V2-Lite, InternLM3, Phi-3.5-mini, Phi-4, Phi-4-mini, MiniCPM-4.1, dots.llm1, Hunyuan-A13B.

**Gemma 2 / 3 are stricter**: the template has no `tool` role at all, and it forces user/assistant
alternation — the moment a `tool` appears in the history it throws *"Conversation roles must
alternate user/assistant/user/assistant/..."* outright. Gemma 2 doesn't even support the system role
(*"System role not supported"*). To do tool calling with Gemma, the entire protocol has to be built
inside the user turn yourself.

> [!important] One item to add to the checklist
> When onboarding a new model, **render a history with a tool call, then confirm the call actually
> appears in the output**. This step takes three lines of code and catches every case in this
> section. Testing only that "rendering didn't error" is not enough.

## 7. Bugs that ship inside the template

A template is a data file shipped with the model; like code it can have defects, and hardly anyone
tests it.

**`stepfun-ai/step3`'s delimiter is inconsistent between where it's taught and where it's used.** The
form the template teaches the model is `<｜tool_call_begin｜>` (appearing twice, both in the
instructional text shown to the model), but **when it actually renders history** it uses
`<｜tool_call_begin>｜>` — the `>` and `｜` are transposed. That is, the model is taught one form while
its own history records another.

**`tiiuae/Falcon3` puts the tool result under the assistant header**, see the previous section.

Neither of these is my conjecture; both were found by comparing the rendered output against the
template source word for word. Their significance is not the two models themselves but this: **a
template cannot be assumed correct.** When onboarding, printing the rendered result and taking a look
is more reliable than reading the documentation.

## 8. Implications for this repository

Cross-referencing `crates/onnx-genai-ort/src/chat_template.rs` and
`crates/onnx-genai/src/reasoning.rs`:

1. **`pycompat` is required, not an optimization.** Among the 49 successful renders here, a great many
   templates call Python's string methods. This confirms the existing implementation's decision to
   hook up `minijinja_contrib::pycompat`.
2. **`raise_exception` must be implemented.** In the sample Mistral-Small-3.2 has 8 occurrences,
   Apertus 11, gpt-oss and Mistral v0.3 4 each. Not implementing it = silently ignoring the hard
   constraints the model declares.
3. **`{% generation %}` needs to be tolerated.** SmolLM3 uses this transformers extension tag. A
   pure-Jinja implementation fails at the **parse stage**, without even a chance to degrade
   gracefully.
4. **`arguments` needs bidirectional conversion per model.** As it stands, some models require a dict
   and others a string, with no universal answer. This is more complex than the claim in
   [[prompting/Chat Templates]] that "HF wants a dict, OpenAI wants a string": the HF camp is not
   uniform internally.
5. **The `ChatRole::Other(String)` design is proven necessary.** The result roles observed in testing
   include at least four nonstandard values — `ipython`, `observation`, `OBSERVATION`, `environment`
   — plus forms that bypass the role enum entirely, like Qwen stuffing the result into `user` and
   Kimi into `im_system`.
6. **Dropping reasoning segments cannot rely on the template.** See section 3: only 2/49 replay it,
   but precisely because these 2 exist, the drop logic on the caller's side cannot be skipped.
7. **`reasoning.rs` currently recognizes only paired delimiters.** The Harmony family (gpt-oss, Muse
   Glimmer) uses the recipient/channel in the message header, which requires recognizing the segment
   after `<|start|>` and before `<|message|>` at the parsing layer. This remains an unimplemented gap.

## 9. Minimal conclusions for the adapter layer

1. **There is no universal `arguments` shape.** Convert to dict / JSON string per model.
2. **There is no universal role for tool results.** At minimum you must be able to express custom
   roles beyond `tool`.
3. **Do not assume the template will use the `tools` argument you pass.** The DeepSeek family won't.
4. **Do not assume the template will render the `tool_calls` you pass.** Granite 3.3, SmolLM3, and
   GLM-4-9B won't, and raise no error.
5. **Onboarding acceptance = render once and check whether the sentinel string is present**, not "no
   exception was thrown".
6. **Prefer a 9-character alphanumeric `tool_call_id`**; it sidesteps old Mistral's check and is
   harmless to others.
7. **Drop reasoning segments at the caller**, don't count on the template.

## References and sources

- All templates are taken from the `chat_template.jinja` or `tokenizer_config.json` of the
  corresponding Hugging Face repository, fetch date 2026-08-19. Llama / Gemma are taken from
  `unsloth/*` mirrors (the official repos are gated).
- Every syntax fragment in this note is a verbatim excerpt of the **rendered output**; for the render
  skeleton see section 1.
- Related implementation: `crates/onnx-genai-ort/src/chat_template.rs`,
  `crates/onnx-genai/src/reasoning.rs`

## Related notes

- [[prompting/Chat Templates]] — the mechanism: how templates work, and the principles of
  multimodality and tool calling
- [[architecture/Inference Request Lifecycle]] — the full path of a request after rendering
- [[memory/Virtual Memory for KV Cache]] — how the rendered tokens are placed in VRAM
