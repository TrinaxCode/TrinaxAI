# Local model benchmark

Measured on the TrinaxAI target host on 2026-07-16 through Ollama `/api/generate`.
Every model received the same English web-page planning prompt, `num_ctx=4096`,
`num_predict=96`, `temperature=0`, `think=false`, and `keep_alive=0`.

| Model | Load | Generation | Speed | Total |
|---|---:|---:|---:|---:|
| `granite4:3b` | 7.91 s | 8.83 s | 10.87 tok/s | 18.16 s |
| `qwen3.5:4b` | 19.81 s | 15.92 s | 6.03 tok/s | 37.01 s |

`granite4:3b` is the balanced chat default and advertises Ollama `completion`
and `tools` capabilities with a 131072-token native context. The benchmark
compares these two measured candidates; the current deep-model default is
`qwen3.5:2b` and is not represented in this result set.

These numbers are host-specific. Repeat the command on materially different CPU,
GPU, RAM, quantization, or Ollama versions before changing higher-end profiles.
