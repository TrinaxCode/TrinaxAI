# Local model benchmark

Measured on the TrinaxAI target host (Ryzen 7 5700U, 16 GB RAM, CPU-only) on
2026-07-18 through Ollama `/api/generate`. Every model received the same Spanish
RAG explanation prompt, `num_ctx=2048`, `num_predict=96`, `temperature=0`,
`think=false`, and `keep_alive=0`.

| Model | Load | Generation | Speed | Total |
|---|---:|---:|---:|---:|
| `qwen3.5:0.8b` | 6.13 s | 5.05 s | 19.00 tok/s | 11.50 s |
| `qwen3.5:2b` | 11.92 s | 10.70 s | 8.97 tok/s | 23.59 s |
| `qwen3.5:4b` | 15.73 s | 14.50 s | 6.62 tok/s | 31.72 s |
| `granite4:3b` | 6.83 s | 8.35 s | 11.50 tok/s | 16.69 s |
| `qwen2.5-coder:1.5b` | 4.46 s | 4.72 s | 20.32 tok/s | 9.75 s |
| `qwen2.5-coder:3b` | 6.88 s | 8.38 s | 11.46 tok/s | 16.67 s |

The faster Granite and legacy coder models mistranslated or misexpanded “RAG”
in this run. `qwen3.5:2b` preserved the concept and handles trivial requests;
`qwen3.5:4b` is the 16 GB general, code, and deep default. The 0.8B model was retired
from routing: it is fast, but brief identity and project questions can make it
blend supplied facts. `qwen3.5:2b` is the smallest supported chat route.
Output review is qualitative and prompt-specific.

## Embedding choice

The Qwen3 model card reports multilingual MTEB means of 64.33, 69.60, and
70.88 for its 0.6B, 4B, and 8B embedding models. TrinaxAI therefore uses those
sizes for its 8/16 GB, max, and ultra profiles with 1024, 2560, and 4096
dimensions respectively. A local Spanish smoke check with 0.6B also separated a relevant
TrinaxAI profile passage (cosine 0.6686) from an unrelated recipe (0.1820), and
matched the equivalent English query at 0.8412. TrinaxAI adds a retrieval
instruction to queries and embeds stored passages without it.

The local latency numbers are host-specific. Repeat the benchmark on materially
different CPU, GPU, RAM, quantization, or Ollama versions before changing profiles.
