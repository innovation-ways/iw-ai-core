# Best Local LLMs for AI-Powered Codebase Understanding on RTX 5090

**Research ID**: R-00045  
**Date**: 2026-04-15  
**Mode**: deep  
**Depth**: deep  
**Editorial Category**: technical

---

## Primary Question

What are the best local LLM models available today for AI-powered codebase understanding (RAG-based Q&A + code map generation), specifically evaluated against RTX 5090 hardware with 32GB VRAM — and how should the provider be architected to support local, Claude Code, and OpenCode as configurable backends?

---

## Executive Summary

The RTX 5090 with 32GB GDDR7 VRAM and 1.79 TB/s memory bandwidth is the first consumer GPU capable of running 32B-parameter models at Q8 quantization — and at Q4, it delivers genuinely interactive response times for 24–27B-class models. For codebase understanding, the recommended LLM is **Gemma 4 26B MoE** for best speed/quality balance (~120–150 tok/s generation, 77% LiveCodeBench v6) or **Devstral Small 2 24B** for deep agentic code comprehension (68% SWE-bench Verified). For embeddings, **nomic-embed-code** (7B, 32K context) is the clear winner on code-specific retrieval, outperforming both Voyage Code 3 and OpenAI Embed 3 Large on CodeSearchNet benchmarks. Gemma 4 31B Dense achieves the highest raw benchmark scores (80% LiveCodeBench v6) but its ~40 tok/s generation speed makes interactive Q&A sluggish on RTX 5090; the 26B MoE variant provides dramatically better latency while losing only 3 benchmark points. The provider should be designed as a clean abstraction with three interchangeable backends: local (Ollama), Claude Code (Anthropic API), and OpenCode — configured per project with sensible defaults.

---

## 1. Gemma 4: Deep Dive [HIGH]

### Release and Licensing

Google released Gemma 4 in April 2026 under the [Apache 2.0 license](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/), making it fully commercially permissive. It is the fourth-generation Gemma family and the first to be fully multimodal (text, image, audio inputs).

### Model Sizes and Context Windows

Per the [official model card](https://ai.google.dev/gemma/docs/core/model_card_4) and [HuggingFace blog](https://huggingface.co/blog/gemma4):

| Variant | Effective Params | Total Params | Context | Architecture |
|---|---|---|---|---|
| E2B | 2.3B active | 5.1B total | 128K | Dense (edge/mobile) |
| E4B | 4.5B active | 8B total | 128K | Dense (edge/mobile) |
| 26B A4B | **3.8B active** | 25.2B total | **256K** | Mixture-of-Experts |
| 31B | 30.7B | 30.7B | **256K** | Dense |

### Architecture Innovations

Per the [HuggingFace detailed writeup](https://huggingface.co/blog/gemma4):

- **Alternating Attention**: Interleaves local sliding-window attention (512–1024 token span) with global full-context attention layers — enables efficient long-context handling without full quadratic cost
- **Dual RoPE Configurations**: Standard RoPE for sliding-window layers; proportional RoPE for global layers to support variable context lengths
- **Per-Layer Embeddings (PLE)**: A second embedding table that conditions each layer on token identity separately from the main residual stream — token-specific conditioning at each depth
- **Shared KV Cache**: The last N layers reuse K/V tensors from earlier non-shared layers, reducing both memory footprint and compute per token
- **Multimodal**: USM-style conformer audio encoder; vision encoder with learned 2D positions and multidimensional RoPE

### Code Benchmark Scores

Per the [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4):

| Benchmark | 31B Dense | 26B A4B (MoE) | E4B | E2B |
|---|---|---|---|---|
| LiveCodeBench v6 | **80.0%** | 77.1% | 52.0% | 44.0% |
| Codeforces ELO | **2150** | 1718 | 940 | 633 |
| AIME 2026 | **89.2%** | 88.3% | 42.5% | 37.5% |
| MMLU Pro | **85.2%** | 82.6% | 69.4% | 60.0% |

[Gemma 3 27B scored only 29.1% on LiveCodeBench v6](https://medium.com/@moksh.9/heres-a-tighter-benchmark-focused-blog-post-501c5ea829f4) — the 31B's 80.0% represents a 175% improvement generation-over-generation. The Codeforces ELO jump from 110 (Gemma 3 27B) to 2150 (Gemma 4 31B) is a ~20x improvement.

### Ollama Availability

[Available on Ollama](https://ollama.com/library/gemma4) with the following official variants:

| Tag | VRAM (Q4_K_M) | Context |
|---|---|---|
| `gemma4:e2b` | 7.2 GB | 128K |
| `gemma4:e4b` / `gemma4:latest` | 9.6 GB | 128K |
| `gemma4:26b` | 18 GB | 256K (MoE) |
| `gemma4:31b` | 20 GB | 256K (Dense) |

29 total model variants including community Q6/Q8 options. [Crossed 1 million downloads](https://www.mindstudio.ai/blog/how-to-run-gemma-4-locally-ollama) since release.

---

## 2. Code LLM Comparison [HIGH for benchmarks; MEDIUM for RAG-specific tasks]

### Gemma 4 31B Dense

Strengths: Highest raw benchmark quality, 256K context, multimodal. LiveCodeBench v6: 80.0%, Codeforces ELO: 2150.  
Weakness: ~40 tok/s at Q4 on RTX 5090 — interactive use is sluggish.  
Best for: Offline batch code map generation where latency is not a concern.

### Gemma 4 26B A4B (MoE)

Strengths: 97% of 31B quality at ~3x the inference speed. MoE activates only 3.8B parameters per token. LiveCodeBench v6: 77.1%, Codeforces ELO: 1718. [LMArena Elo 1441 vs 1452 for 31B](https://huggingface.co/blog/gemma4). Fits in ~15 GB VRAM leaving 17 GB headroom for context and embeddings.

Per [community benchmarks](https://explore.n1n.ai/blog/benchmarking-google-gemma-4-26b-31b-locally-2026-04-06), the 26B MoE achieves ~150 tok/s generation on RTX 4090 vs ~8 tok/s for the 31B Dense on the same GPU. The contrast is due to MoE's lower active parameter count per forward pass.

### Qwen2.5-Coder 32B Instruct

Key benchmark data from the [official Qwen blog](https://qwenlm.github.io/blog/qwen2.5-coder-family/):

- HumanEval: **91.0%** (matches GPT-4o)
- CrossCodeEval: SOTA (cross-file completion — structurally identical to RAG Q&A)
- RepoEval: SOTA (repository-level code completion)
- McEval (40+ languages): 65.9
- MdEval (multi-language code repair): 75.2 (1st among open-source)
- Context window: 128K
- Training: 5.5 trillion tokens of code-related data

**Key differentiator**: CrossCodeEval and CrossCodeLongEval directly test cross-file code completion — this is structurally similar to RAG-augmented code understanding where retrieved chunks from multiple files are injected into context. This is Qwen2.5-Coder's strongest differentiator. Note: 2024 model; likely superseded on raw benchmarks by Gemma 4, but repository-level evaluation data not yet available for newer models.

### Devstral Small 2 (24B)

Architecture from [HuggingFace](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512): 24B dense transformer, 40 layers, GQA, RoPE-scaling. Context: **256K tokens**. License: Apache 2.0.

Key benchmarks per [Mistral](https://mistral.ai/news/devstral-2-vibe-cli):

- **SWE-bench Verified: 68.0%** — places "firmly among models up to five times its size"
- Can run on single RTX 4090 or Mac with 32GB RAM at Q4

SWE-bench Verified measures real GitHub issue resolution — the closest existing benchmark to codebase comprehension Q&A. Devstral's architecture is specifically fine-tuned for [exploring codebases, tracking Git state, updating dependencies, and orchestrating multi-file changes](https://mistral.ai/news/devstral-2-vibe-cli). This is genuine codebase understanding, not just code generation.

### Comparison Summary

| Model | Code Gen Quality | Repo Understanding | Context | RAG Fit | Structured Output |
|---|---|---|---|---|---|
| Gemma 4 31B Dense | Highest (LCB: 80%) | Very Good | 256K | Good | Good |
| Gemma 4 26B MoE | Excellent (LCB: 77%) | Very Good | 256K | Good | Good |
| Qwen2.5-Coder 32B | Excellent (HumanEval: 91%) | **Best cross-file** (SOTA RepoEval) | 128K | **Excellent** | **Excellent** |
| Devstral Small 2 24B | Good | **Best agentic** (SWE-bench: 68%) | 256K | Very Good | Good |

**Key insight for the use case**: For RAG-based Q&A with retrieved chunks, Qwen2.5-Coder 32B's SOTA RepoEval and CrossCodeEval scores indicate it understands cross-file, cross-reference code patterns best. For interactive Q&A sessions where speed matters, Gemma 4 26B MoE is the clear winner. For structured output (Mermaid diagrams, JSON module maps), Qwen2.5-Coder is the most reliable choice.

---

## 3. RTX 5090 Hardware Profile [HIGH for specs; MEDIUM for model-specific tok/s]

### Core Specifications

Per [RunPod's RTX 5090 review](https://www.runpod.io/articles/guides/nvidia-rtx-5090) and [NVIDIA specifications](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/):

| Spec | RTX 5090 | RTX 4090 | A100 80GB |
|---|---|---|---|
| VRAM | **32 GB GDDR7** | 24 GB GDDR6X | 80 GB HBM2e |
| Memory Bandwidth | **1.79 TB/s** | 1.008 TB/s | 2.0 TB/s |
| CUDA Cores | 21,760 | 16,384 | 6,912 |
| FP32 TFLOPS | ~104.8 | ~82.6 | ~19.5 |
| TDP | 575W | 450W | 400W |

The [77% memory bandwidth improvement](https://blog.neevcloud.com/the-impact-of-rtx-5090s-memory-bandwidth-on-llms) over the RTX 4090 is the single most important spec for LLM inference — token generation is memory-bandwidth bound (model weights read from VRAM for every generated token).

### Realistic Tokens Per Second

Synthesized from [hardware-corner.net](https://www.hardware-corner.net/rtx-5090-llm-benchmarks/), [databasemart.com](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090), and [neevcloud blog](https://blog.neevcloud.com/the-impact-of-rtx-5090s-memory-bandwidth-on-llms):

| Model Size | Q4_K_M (tok/s gen) | Q8 (tok/s gen) | Notes |
|---|---|---|---|
| 7B–9B Dense | ~180–213 | ~100–120 | Qwen3 8B: 185.91 t/s at Q4 |
| 12B–14B Dense | ~123–160 | ~70–90 | Qwen3 14B: 123.79 t/s |
| 24B–27B Dense | ~47–70 | ~30–40 | Gemma3 27B: 47 t/s |
| 26B MoE (3.8B active) | **~120–150** | ~80–100 | Extrapolated from RTX 4090 + 30% BW advantage |
| 30B–32B Dense | ~45–65 | ~25–35 | Qwen3 32B: 61.38 t/s |
| 30B MoE (sparse) | ~150–234 | ~90–130 | Qwen3moe 30B: 234 t/s |

Prompt processing (prefill) is dramatically faster: Qwen3 32B achieves [2,931 tok/s prefill at Q4](https://www.hardware-corner.net/rtx-5090-llm-benchmarks/) — RAG Q&A (large prompt, shorter generation) benefits significantly from fast prefill.

### What Fits in 32 GB VRAM

Based on [InsiderLLM VRAM guide](https://insiderllm.com/guides/vram-requirements-local-llms/) and [compute-market.com Gemma 4 guide](https://www.compute-market.com/blog/gemma-4-local-hardware-guide-2026):

| Model | Q4 VRAM | Q8 VRAM | Fits 32GB (Q4) | Fits 32GB (Q8) |
|---|---|---|---|---|
| Gemma 4 E4B | ~2.5 GB | ~4.5 GB | YES | YES |
| Gemma 4 26B MoE | ~15 GB | ~28 GB | YES | YES (tight) |
| Gemma 4 31B Dense | ~18–20 GB | ~33–34 GB | YES | **NO** |
| Devstral Small 2 24B | ~15 GB | ~24 GB | YES | YES |
| Qwen2.5-Coder 32B | ~19–20 GB | ~34 GB | YES | **NO** |
| 70B models | ~40 GB | OOM | **NO** | NO |

**Critical finding**: The RTX 5090 is the [first single consumer GPU that can run 32B-class models at Q8](https://insiderllm.com/guides/vram-requirements-local-llms/). Q8 preserves near-lossless quality (typically <1% benchmark delta vs fp16). However, 256K context KV cache adds 16–32 GB additional VRAM, making Gemma 4 31B at Q4 with full 256K context infeasible on RTX 5090.

### RTX 5090 vs Competitors for LLM Inference

- vs RTX 4090: [28–50% faster tok/s due to bandwidth advantage](https://blog.neevcloud.com/the-impact-of-rtx-5090s-memory-bandwidth-on-llms) plus 8 GB more VRAM
- vs A100 80GB: [RTX 5090 wins 24 out of 26 LLM benchmarks](https://www.runpod.io/gpu-compare/rtx-5090-vs-a100-sxm). A100 has 2.5x more VRAM but slower bandwidth for single-user workloads
- The RTX 5090 [marginally outperforms even the H100 at 32B model generation](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090) (45.51 vs 45.36 tok/s for deepseek-r1:32b at Q4) due to higher per-GPU bandwidth

---

## 4. Local Embedding Models for Code RAG [HIGH for nomic-embed-code; MEDIUM for comparisons]

### nomic-embed-code [PRIMARY RECOMMENDATION]

Released March 2025 by Nomic AI. Purpose-built for code retrieval:

- **Parameters**: 7B
- **Context window**: **32K tokens** (vs 512 for mxbai-embed-large, 8K for nomic-embed-text)
- **Model size on Ollama**: 7.5 GB
- **Training data**: CoRNStack dataset with dual-consistency filtering and progressive hard negative mining

CodeSearchNet benchmark scores ([Hugging Face model card](https://huggingface.co/nomic-ai/nomic-embed-code)):

| Model | Python | Java | Ruby | PHP | JavaScript | Go |
|---|---|---|---|---|---|---|
| **nomic-embed-code** | **81.7** | **80.5** | 81.8 | **72.3** | 77.1 | **93.8** |
| Voyage Code 3 | 80.8 | 80.5 | **84.6** | 71.7 | **79.2** | 93.2 |
| OpenAI Embed 3 Large | 70.8 | 72.9 | 75.3 | 59.6 | 68.1 | 87.6 |
| nomic-embed-text v1.5 | 62.x | 65.x | 70.x | 56.x | 65.x | 83.x |
| mxbai-embed-large | ~55 | ~58 | ~63 | ~50 | ~58 | ~78 |

nomic-embed-code wins 4 of 6 languages, ties Java, loses only Ruby to Voyage Code 3 (a cloud-only model).

**Ollama caveat**: Not yet in the official Ollama library as of April 2026 — available via community model `manutic/nomic-embed-code` or via [GGUF from nomic-ai/nomic-embed-code-GGUF](https://huggingface.co/nomic-ai/nomic-embed-code-GGUF) served through llama.cpp. This may be resolved by implementation time.

### qwen3-embedding 8B [STRONG ALTERNATIVE]

Available in the [official Ollama library](https://ollama.com/library/qwen3-embedding). The 8B variant [ranks #1 on MTEB Multilingual leaderboard at score 70.58](https://github.com/QwenLM/Qwen3-Embedding). Supports code retrieval across 100+ languages. Context: **40K tokens** for 4B/8B variants. Model size: 4.7 GB. Strong general retrieval including code — not benchmarked specifically on CodeSearchNet vs nomic-embed-code. Best choice if official Ollama support is a hard requirement.

### Other Models

| Model | Context | Size | Code-Specific | Ollama Official | Verdict |
|---|---|---|---|---|---|
| nomic-embed-text v1.5 | 8K | 274 MB | No | YES | Good for doc/comment retrieval |
| nomic-embed-text-v2-moe | 8K | ~500 MB | No | YES | Good for NL queries about code |
| mxbai-embed-large | **512 tokens** | 670 MB | No | YES | **Inadequate** — context too short for code |

**mxbai-embed-large is not suitable for code RAG** — its 512-token context window cannot accommodate most function bodies or module descriptions.

---

## 5. Recommended Model Stack

### (a) Best Quality — Maximum Code Understanding

**Use case**: Offline code map generation, batch architecture analysis where latency is acceptable.

| Component | Model | VRAM | Pull Command |
|---|---|---|---|
| LLM | Gemma 4 31B Dense (Q4_K_M) | ~18–20 GB | `ollama pull gemma4:31b` |
| Embedding | nomic-embed-code | ~7.5 GB | `manutic/nomic-embed-code` |
| **Total** | | **~26–28 GB** | Fits in 32 GB |

- LCB v6: 80.0%, Codeforces ELO: 2150
- 256K context — fits entire medium-sized codebases
- ~40 tok/s generation — slow for interactive Q&A, acceptable for batch jobs

### (b) Best Speed — Interactive Q&A

**Use case**: Real-time developer Q&A, quick codebase navigation.

| Component | Model | VRAM | Pull Command |
|---|---|---|---|
| LLM | Gemma 4 E4B (Q4_K_M) | ~2.5 GB | `ollama pull gemma4:e4b` |
| Embedding | qwen3-embedding 8B | ~4.7 GB | `ollama pull qwen3-embedding:8b` |
| **Total** | | **~7–8 GB** | Leaves 24 GB free |

- LCB v6: 52.0%, ~200 tok/s on RTX 5090
- 128K context, genuinely interactive latency
- Leaves enormous headroom for concurrent tasks and large KV cache

### (c) Best Balance — Production Default Recommendation

**Use case**: Daily active development assistance, module-level Q&A, structured output generation.

**Option 1 — Speed + Reasoning (recommended default)**:

| Component | Model | VRAM | Pull Command |
|---|---|---|---|
| LLM | Gemma 4 26B MoE (Q4_K_M) | ~15 GB | `ollama pull gemma4:26b` |
| Embedding | nomic-embed-code | ~7.5 GB | `manutic/nomic-embed-code` |
| **Total** | | **~23 GB** | Fits comfortably |

- LCB v6: 77.1%, ~120–150 tok/s — **interactive response speed**
- 256K context, multimodal (can reason about architecture screenshots)
- Best for architecture diagrams, JSON module maps, general code Q&A

**Option 2 — Agentic Code Understanding**:

| Component | Model | VRAM | Pull Command |
|---|---|---|---|
| LLM | Devstral Small 2 24B (Q4_K_M) | ~15 GB | `ollama pull devstral-small-2:24b` |
| Embedding | nomic-embed-code | ~7.5 GB | `manutic/nomic-embed-code` |
| **Total** | | **~23 GB** | Fits comfortably |

- SWE-bench Verified: 68% — best proxy for codebase comprehension
- 256K context, ~65–70 tok/s
- Best for cross-file dependency tracing, understanding why code exists, architectural reasoning

**Option 3 — Structured Output Focus**:

| Component | Model | VRAM | Pull Command |
|---|---|---|---|
| LLM | Qwen2.5-Coder 32B (Q4_K_M) | ~19–20 GB | `ollama pull qwen2.5-coder:32b` |
| Embedding | nomic-embed-code | ~7.5 GB | `manutic/nomic-embed-code` |
| **Total** | | **~27 GB** | Fits |

- HumanEval: 91%, RepoEval SOTA, ~45–65 tok/s
- Best for generating JSON module maps, Mermaid diagrams, structured code analysis
- SOTA on cross-file code completion (closest to RAG Q&A)

---

## 6. Comparison Matrix

### LLM Models

| Model | Params | Q4 VRAM | Q8 VRAM | Fits 32GB (Q4) | Tok/s RTX 5090 (gen) | Code Benchmark | RAG Suitability |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | 2.3B | ~1.5 GB | ~2.2 GB | YES | ~350+ | LCB v6: 44% | Moderate |
| Gemma 4 E4B | 4.5B | ~2.5 GB | ~4.5 GB | YES | ~200 | LCB v6: 52% | Good |
| **Gemma 4 26B MoE** | 25.2B (3.8B active) | ~15 GB | ~28 GB | YES | **~120–150** | LCB v6: 77% | Very Good |
| Gemma 4 31B Dense | 30.7B | ~18–20 GB | ~33 GB | YES (Q4 only) | ~40 | LCB v6: **80%** | Very Good |
| **Qwen2.5-Coder 32B** | 32B | ~19–20 GB | ~34 GB | YES (Q4 only) | ~45–65 | HumanEval: **91%**, RepoEval: SOTA | **Excellent** |
| **Devstral Small 2 24B** | 24B | ~15 GB | ~24 GB | YES | ~65–70 | SWE-bench: **68%** | Very Good |
| Devstral (original 22B) | 22B | ~13 GB | ~22 GB | YES | ~75 | SWE-bench: 46.8% | Good |

### Embedding Models

| Model | Size | Q4 VRAM | Context | Code CSN Score | Code-Specific | Ollama Official |
|---|---|---|---|---|---|---|
| **nomic-embed-code** | 7B | ~7.5 GB | **32K** | avg ~81+ | **YES** | Community only |
| qwen3-embedding 8B | 8B | ~4.7 GB | 40K | Unknown (MTEB 70.58) | Partial | **YES** |
| nomic-embed-text v1.5 | 137M | ~274 MB | 8K | ~67 avg | No | YES |
| nomic-embed-text-v2-moe | 475M | ~500 MB | 8K | ~65 avg | No | YES |
| mxbai-embed-large | 334M | ~670 MB | **512** | ~60 avg | No | YES |

---

## 7. Provider Architecture Implications

Based on these findings, the configurable provider should support:

```yaml
# Per-project code_understanding config
code_understanding:
  provider: local | claude-code | opencode  # required

  # Local provider settings
  ollama_url: http://localhost:11434         # default
  llm_model: gemma4:26b                     # default for local
  embed_model: manutic/nomic-embed-code     # default for local

  # Cloud provider settings (claude-code / opencode)
  cloud_llm_model: null                     # null = use project default

  # Analysis settings
  index_path: ~/.iw-ai-core/indexes/{project_id}/
  max_context_tokens: 32000                 # safe limit for 256K-context models
  generation_mode: on_demand               # manual only (v1)
```

**Fallback chain**: if `llm_model` not set → use project's configured model → use provider default.

**Local provider model defaults by quality tier**:

| Tier | LLM | Embedding | When to use |
|---|---|---|---|
| `fast` | `gemma4:e4b` | `qwen3-embedding:8b` | Interactive Q&A, low latency |
| `balanced` | `gemma4:26b` | `nomic-embed-code` | Daily use (default) |
| `quality` | `gemma4:31b` or `qwen2.5-coder:32b` | `nomic-embed-code` | Batch generation |

---

## 8. Limitations

1. **Gemma 4 31B tok/s on RTX 5090**: Best available data extrapolated from RTX 4090 ~8 tok/s result. RTX 5090's additional memory room may push this to 45–55 tok/s. HIGH UNCERTAINTY.

2. **Gemma 4 26B MoE on RTX 5090**: Estimated from RTX 4090's 149.56 tok/s result + ~30% RTX 5090 bandwidth advantage. No direct RTX 5090 + Gemma 4 MoE benchmark was found at research time.

3. **RAG-specific benchmarks**: No model has published benchmarks specifically for RAG-based codebase Q&A. SWE-bench Verified (Devstral), RepoEval/CrossCodeEval (Qwen2.5-Coder), and LiveCodeBench (Gemma 4) are used as proxies — they correlate with the target capability but are not identical.

4. **nomic-embed-code Ollama official status**: Not in the official Ollama library as of April 2026. Community model `manutic/nomic-embed-code` exists but may lag upstream updates. This may be resolved by implementation time; qwen3-embedding:8b is the fallback with full official support.

5. **Qwen2.5-Coder 32B recency**: 2024 model. Qwen3-Coder (2025/2026) likely supersedes it on benchmarks but local inference characteristics not yet fully researched.

6. **256K context + large model VRAM**: Running Gemma 4 31B at Q4 (~18–20 GB) with full 256K context KV cache may exceed 32 GB VRAM. A practical context limit of 32K–64K tokens is recommended for safety.

7. **Structured output quality not benchmarked**: No benchmarks specifically test Mermaid diagram or JSON module map generation quality for local models.

---

## 9. Sources

| # | Title | Credibility | URL | Date |
|---|---|---|---|---|
| 1 | Gemma 4: Byte for byte, the most capable open models | HIGH | [blog.google](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) | Apr 2026 |
| 2 | Gemma 4 model card | HIGH | [ai.google.dev](https://ai.google.dev/gemma/docs/core/model_card_4) | Apr 2026 |
| 3 | Welcome Gemma 4: Frontier multimodal intelligence on device | HIGH | [huggingface.co/blog/gemma4](https://huggingface.co/blog/gemma4) | Apr 2026 |
| 4 | gemma4 — Ollama Library | HIGH | [ollama.com/library/gemma4](https://ollama.com/library/gemma4) | Apr 2026 |
| 5 | Qwen2.5-Coder Family Blog | HIGH | [qwenlm.github.io](https://qwenlm.github.io/blog/qwen2.5-coder-family/) | Nov 2024 |
| 6 | Devstral — Mistral AI | HIGH | [mistral.ai/news/devstral](https://mistral.ai/news/devstral) | May 2025 |
| 7 | Introducing Devstral 2 and Mistral Vibe CLI | HIGH | [mistral.ai/news/devstral-2-vibe-cli](https://mistral.ai/news/devstral-2-vibe-cli) | Dec 2025 |
| 8 | devstral-small-2 — Ollama | HIGH | [ollama.com/library/devstral-small-2](https://ollama.com/library/devstral-small-2) | Dec 2025 |
| 9 | devstral-small-2 HuggingFace | HIGH | [huggingface.co/mistralai](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) | Dec 2025 |
| 10 | RTX 5090 LLM Benchmarks: 10K Tokens/sec | MEDIUM | [hardware-corner.net](https://www.hardware-corner.net/rtx-5090-llm-benchmarks/) | 2025/2026 |
| 11 | RTX 5090 Ollama Benchmark — DatabaseMart | MEDIUM | [databasemart.com](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090) | 2025/2026 |
| 12 | Impact of RTX 5090's Memory Bandwidth on LLMs | MEDIUM | [blog.neevcloud.com](https://blog.neevcloud.com/the-impact-of-rtx-5090s-memory-bandwidth-on-llms) | 2025 |
| 13 | Nvidia RTX 5090 Review — RunPod | MEDIUM | [runpod.io](https://www.runpod.io/articles/guides/nvidia-rtx-5090) | 2025 |
| 14 | RTX 5090 vs A100 SXM — RunPod | MEDIUM | [runpod.io/gpu-compare](https://www.runpod.io/gpu-compare/rtx-5090-vs-a100-sxm) | 2025 |
| 15 | nomic-embed-code — Hugging Face | HIGH | [huggingface.co/nomic-ai/nomic-embed-code](https://huggingface.co/nomic-ai/nomic-embed-code) | Mar 2025 |
| 16 | Nomic Embed Code: A State-of-the-Art Code Retriever | HIGH | [nomic.ai/news](https://www.nomic.ai/news/introducing-state-of-the-art-nomic-embed-code) | Mar 2025 |
| 17 | qwen3-embedding — Ollama Library | HIGH | [ollama.com/library/qwen3-embedding](https://ollama.com/library/qwen3-embedding) | Jun 2025 |
| 18 | Qwen3-Embedding GitHub | HIGH | [github.com/QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) | Jun 2025 |
| 19 | Ollama Embedding Models: Benchmarks, VRAM — Morph | MEDIUM | [morphllm.com](https://www.morphllm.com/ollama-embedding-models) | 2025 |
| 20 | mxbai-embed-large — Ollama | HIGH | [ollama.com/library/mxbai-embed-large](https://ollama.com/library/mxbai-embed-large) | 2024/2025 |
| 21 | Best VRAM Cheat Sheet for Local LLMs — InsiderLLM | MEDIUM | [insiderllm.com](https://insiderllm.com/guides/vram-requirements-local-llms/) | 2025 |
| 22 | Gemma 4 Hardware Guide — Compute Market | MEDIUM | [compute-market.com](https://www.compute-market.com/blog/gemma-4-local-hardware-guide-2026) | Apr 2026 |
| 23 | Benchmarking Gemma 4 26B and 31B Locally — n1n.ai | MEDIUM | [explore.n1n.ai](https://explore.n1n.ai/blog/benchmarking-google-gemma-4-26b-31b-locally-2026-04-06) | Apr 2026 |
| 24 | Training Sparse MoE Text Embedding Models (nomic v2) | HIGH | [arxiv.org/abs/2502.07972](https://arxiv.org/abs/2502.07972) | Feb 2025 |
| 25 | Qwen3 vs Nomic embeddings — real numbers | MEDIUM | [imarch.dev](https://imarch.dev/en/blog/qwen3-vs-nomic-embeddings/) | 2025 |
| 26 | Gemma 4 vs competitors comparison | MEDIUM | [ai.rs](https://ai.rs/ai-developer/gemma-4-vs-qwen-3-5-vs-llama-4-compared) | Apr 2026 |
| 27 | Gemma 3 benchmarks (baseline comparison) | MEDIUM | [medium.com/@moksh.9](https://medium.com/@moksh.9/heres-a-tighter-benchmark-focused-blog-post-501c5ea829f4) | 2025 |
