# Local model benchmark

Measured on the TrinaxAI target host on 2026-07-16 through Ollama `/api/generate`.
Every model received the same English web-page planning prompt, `num_ctx=4096`,
`num_predict=96`, `temperature=0`, `think=false`, and `keep_alive=0`.

| Model | Load | Generation | Speed | Total |
|---|---:|---:|---:|---:|
| `granite4:3b` | 7.91 s | 8.83 s | 10.87 tok/s | 18.16 s |
| `qwen3.5:4b` | 19.81 s | 15.92 s | 6.03 tok/s | 37.01 s |
| `qwen3.5:9b` | 29.85 s | 24.22 s | 3.96 tok/s | 56.25 s |

`granite4:3b` is the balanced chat default: it was 3.1× faster end-to-end than
Qwen 9B on this host and advertises Ollama `completion` and `tools` capabilities
with a 131072-token native context. `qwen3.5:4b` remains the default deeper model.
Qwen 9B remains supported as a manual quality option and is not removed or
automatically uninstalled.

These numbers are host-specific. Repeat the command on materially different CPU,
GPU, RAM, quantization, or Ollama versions before changing higher-end profiles.
