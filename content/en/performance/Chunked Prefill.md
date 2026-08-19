---
title: Chunked Prefill
aliases:
  - 分块 Prefill
  - Chunked Prefill and Query Padding
  - Prefill 查询轴补齐
tags:
  - performance
  - prefill
  - attention
  - kv-cache
  - kernel-cache
status: maintained
lang: en
created: 2026-08-19
updated: 2026-08-19
translated_from: 880263ab30e3e39a60d3dcf7e08f66a89779b499
translated_at: 2026-08-19
---

# Chunked Prefill

> [!summary] Question answered
> Why can prefill be fed into the model in chunks, without requiring that "all
> of the KV participate"? What does chunking buy, and what hole does it leave
> that needs one more pass to close?

> [!important] This note describes behavior already implemented on `main`
> The numbers in the tables were all measured on `muse-glimmer-30b-int4` (ONNX
> INT4, native CUDA backend). Where this disagrees with the code, the code wins.

Prefill is the forward pass that "consumes the prompt"; decode is the forward
pass that "emits one token". Both run **the same graph**, differing in only one
number: how many rows the query axis has. Prefill hands the model the entire
prompt at once (M tokens is M rows); decode hands it one row at a time.

That single number decides both a request's peak VRAM and how many kernels the
runtime has to compile.

## 1. Why a prompt can be fed in pieces

To read a 4000-token prompt, the most direct approach is to run a single
`M = 4000` forward pass. Chunked prefill instead runs eight `M = 512` passes,
feeding it one slice at a time. **The output is byte-for-byte identical.**

This holds because of three properties, none of which can be missing.

### 1. The KV cache is append-only

The attention at position `i` reads the key and value of every position `≤ i`.
Those key/values depend only on **the token at that position and this layer's
weights**, and not at all on what comes later. So the cache is written strictly
left to right, and once a position is written it never changes again.

When chunk k runs, `[0, k·W)` has already been written into the cache by the
earlier chunks. Chunk k computes the key/value for its own W positions and
appends them at `[k·W, (k+1)·W)`. Not one byte of what came before is re-read,
not one byte is re-written. The cache after chunk k finishes is **byte-for-byte
identical** to the equal-length prefix of the cache produced by "running the
whole block at once".

This is the answer to "why a chunk does not need all of the KV to participate" —
it **does** attend over all of the KV so far. What it does not need is to
**recompute** that KV. The earlier KV sits in the cache and is read; the chunk's
only new work is its own W rows of query.

> [!tip] The one-line version
> What chunking saves is not "reading", it is "computing".

### 2. The causal mask makes the split invisible

A decoder-only model masks out position `i`'s attention to any position `> i`.
Put the whole-block run and the chunked run side by side: for a query at
position `p` in chunk k,

- the whole-block run lets it see `[0, p]`
- the chunked run lets it see `[0, k·W) ∪ [k·W, p]`

**They are the same set.** The positions the chunked run has not computed yet
are exactly the positions the causal mask would erase anyway.

So chunking is **not an approximation**; it does not trade quality for speed.
The arithmetic is exactly the same; only the order of instruction issue changes.

### 3. The KV tensor's shape does not change

If the KV tensor were resized to the current real sequence length after every
chunk, then the shape each chunk presents to each attention node would be
different, and the runtime would treat every one of them as a new kernel.

`GroupQueryAttention` avoids this by **separating capacity from length**:
`past_key` / `past_value` are bound by **physical capacity** for the entire
generation, and the real effective position count is carried by a separate
input, `seqlens_k`. This fact is hard-coded in `onnx-runtime-session` —
`kernel_input_uses_physical_capacity` in
`crates/onnx-runtime-session/src/executor/geometry.rs` returns `true` for GQA's
input 3 and 4.

The practical consequence of this is worth stating plainly:

> [!important] A growing KV cache does not change any kernel's input shape
> A generation that runs to 4000 tokens and one that stops at 400 tokens
> compile the same number of kernels.

For how the KV cache itself grows without moving data or swapping pointers, see
[[memory/Virtual Memory for KV Cache]].

## 2. What chunking is for

Prefill's attention needs `O(M × total)` work, and more dangerously needs
`O(M × total)` scratch to hold the attention scores. At `M = 4000` this scratch
is frighteningly large, and it is **transient** — allocated for one forward pass
and returned when it finishes. A 30B-class model whose weights and KV cache both
fit can be blown up **by this prefill spike alone**.

Squeeze M down to the chunk width W and the spike drops to `O(W × total)`. The
cost is a few more kernel launches and a few more passes over the weights. The
chunk width is declared by the model in its inference metadata:

```yaml
runtime_configurable:
  chunked_prefill:
    chunk_size: 512
```

In this repository, `NativeDecodeSession::set_prefill_chunk_size` reads it, and
`decode_argmax` (`crates/onnx-genai-engine/src/native_decode/backend.rs`) splits
with `token_ids.chunks(chunk)` when the prompt is longer than one chunk.

## 3. The hole chunking leaves

Chunking fixes M at W — **except for the final chunk**, which gets the remainder.

- a 1137-token prompt, W = 512, runs `512, 512, 113`
- a 1200-token prompt runs `512, 512, 176`

The remainder is "prompt length modulo chunk width", which means **essentially a
new number for every request**.

This is dangerous because the kernel cache keys on **node + input shape**
(`KernelKey` in `crates/onnx-runtime-session/src/executor/kernel_cache.rs`). A
query width no one has run before misses on **every node** in the graph; for a
30B decoder that means recompiling about 890 kernels for every request, forever.
Worse, each compiled kernel holds its own device scratch, so this cache is also
**VRAM that the resource governor cannot see at all** — this is the unbounded
growth tracked by issue #1362.

The cache does constrain itself: each node keeps only the most recent few
variants and evicts the rest. But **a cap only helps when the working set fits
inside it**, and a working set of "a new remainder width per request" never fits
inside any cap. Measured (five prompts of different lengths, each run twice):

| Forward pass | Query rows | Kernels compiled | Cumulative evictions |
| --- | --- | --- | --- |
| First pass | 104 | 1105 | 0 |
| First pass | 146 | 888 | 0 |
| First pass | 311 | 890 | 52 |
| **Second pass** | **146** | **888** | **5688** |
| **Second pass** | **311** | **888** | **7045** |
| **Second pass** | **37** | **888** | **9759** |

The second pass runs **exactly the same prompt lengths**, recompiles just as
much as the first pass, and the eviction count is still climbing linearly. This
cache is **thrashing**, not caching.

## 4. Query-axis padding

The fix is to take the trick GQA already uses on the KV axis and move it to the
query axis. GQA does not resize the cache to the exact sequence length; it runs
at a fixed capacity and carries the real length alongside. Prefill can do exactly
the same: **run at the rounded-up width and carry the real row count alongside.**

`prefill_query_width` (in `crates/onnx-genai-engine/src/native_decode/cuda.rs`)
rounds a forward pass's row count up to one of three evenly spaced steps at or
below the chunk width — for a chunk width of 512 that is `{171, 342, 512}`. The
extra rows are filled by repeating the last real token, and any per-token port
that arrives with the request (`inputs_embeds`, and other tensors shaped
`[1, rows, …]`) is widened the same way.

The padded rows are pure waste arithmetically, but they **cannot go wrong**:

- **Cannot be read.** The causal mask does not let the real row at absolute
  position `p` see anything after `p`, and every padded row is ordered after all
  the real rows.
- **logits are discarded.** The result is truncated back to the real row count
  before it is handed to the caller.
- **KV is erased.** After the forward pass the session rewinds to `past_len`
  plus the real row count, which zeroes the tail of the attention mask and rolls
  back the cache's logical length. The next forward pass simply overwrites those
  padded entries.

> [!warning] Two cases decline padding rather than gamble
> **Decoders with recurrent / convolutional state are excluded outright.** That
> state is neither protected by the mask nor addressed by "logical length", so
> advancing it by one extra step can never be taken back.
>
> **An input port whose shape is not `[1, rows, …]`** cannot be assumed to be
> per-token, so the entire padding plan is voided rather than fabricating rows
> for it out of nothing.

There is also a run-time self-check: if a padded forward pass returns **fewer**
logit rows than the query rows handed to it, the decoder has contracted the
query axis internally and its rows cannot be mapped back to input positions — in
that case padding is permanently disabled for that session and the pass is re-run
as-is.

Set `ONNX_GENAI_PREFILL_QUERY_PADDING=0` to turn it off entirely.

## 5. Why the ladder has only three steps

Making the set of widths bounded only helps when the kernel cache's per-node cap
is **at least as large as that set**. That cap is 4.

The obvious move is to raise it. **That is a trap.** Every variant kept holds
device scratch, and this cap is the only thing that caps that scratch. Raising
the cap to 10 to fit an eight-step ladder makes the 30B decoder climb to 72.8 GB
and crash on a 5.5k-token prompt just short of the 76.2 GB mapped ceiling —
while the same decoder at a cap of 4 served the same prompt easily, with VRAM
oscillating between 39–53 GB.

So the ladder is **sized to the cap that already exists**, not the other way
around: three prefill widths, leaving exactly one slot for the single-token
decode shape.

| Configuration | Distinct prefill widths | Second-pass recompiles | 5.5k-token prompt |
| --- | --- | --- | --- |
| No padding, cap 4 | unbounded | ~888 per forward pass | ok, 39–53 GB |
| Padding (eight steps), cap 4 | 5 | ~888 per forward pass | — |
| Padding (eight steps), cap 10 | 5 | 0 | **fails, 72.8 GB** |
| Padding (three steps), cap 4 | 3 | **0** | **ok, flat ~50 GB** |

End-to-end latency does not change beyond noise across prompts from 40 to 900
tokens, and greedy output is byte-for-byte identical whether padding is on or
off.

> [!note] The payoff of this change is not speed
> The payoff is: a long-running server stops continuously compiling kernels, and
> stops continuously piling up kernel scratch it never accounted for.

## 6. How the number of steps was chosen

Three steps is the largest ladder that fits under the premise of "a four-variant
cap that must also leave one slot for the decode shape", and the waste it brings
is the price of that constraint: at most 170 extra rows per forward pass.

Fewer steps would cache better but waste more — switching to a power-of-2 ladder
would send 311 rows up to 512, and that extra 65% of duplicated arithmetic is
measurable on medium-length prompts (a 200-word prompt goes from 4.9 seconds to
7.0 seconds).

The step size **rounds up**, so the top step lands exactly on the chunk width
instead of falling a little short and leaving a stray fourth width above it. The
repository has a test dedicated to guarding this invariant, covering various
declared chunk widths.

## Related reading

- [[memory/Virtual Memory for KV Cache]] — how the KV cache grows without moving data or swapping pointers
- [[memory/Memory Management for Beginners]] — the basics of allocation, residency and governors
- [[performance/Performance Engineering Playbook]] — how to tell whether a performance number is about the runtime or about the experiment itself
- [[execution/CUDA Execution Provider]] — the execution path where all of this note's measurements were taken
- [[metadata/Metadata Driven Runtime]] — how declarations like `chunked_prefill.chunk_size` reach the runtime
