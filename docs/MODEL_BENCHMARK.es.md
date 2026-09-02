<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 📊 Benchmark de modelos
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="MODEL_BENCHMARK.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Medido en el host objetivo de TrinaxAI (Ryzen 7 5700U, 16 GB de RAM, solo CPU) el
2026-07-18 mediante Ollama `/api/generate`. Todos los modelos recibieron el mismo
prompt de explicación RAG en español, `num_ctx=2048`, `num_predict=96`,
`temperature=0`, `think=false` y `keep_alive=0`.

| Modelo | Carga | Generación | Velocidad | Total |
|---|---:|---:|---:|---:|
| `qwen3.5:0.8b` | 6.13 s | 5.05 s | 19.00 tok/s | 11.50 s |
| `qwen3.5:2b` | 11.92 s | 10.70 s | 8.97 tok/s | 23.59 s |
| `qwen3.5:4b` | 15.73 s | 14.50 s | 6.62 tok/s | 31.72 s |
| `granite4:3b` | 6.83 s | 8.35 s | 11.50 tok/s | 16.69 s |
| `qwen2.5-coder:1.5b` | 4.46 s | 4.72 s | 20.32 tok/s | 9.75 s |
| `qwen2.5-coder:3b` | 6.88 s | 8.38 s | 11.46 tok/s | 16.67 s |

El modelo Granite y los modelos coder heredados, aunque más rápidos, tradujeron
o expandieron mal “RAG” en esta ejecución. `qwen3.5:2b` conservó el concepto y
responde bien a solicitudes triviales; `qwen3.5:4b` es el valor predeterminado
general, de código y profundo para 16 GB. El modelo 0.8B fue retirado del routing:
es rápido, pero preguntas breves de identidad y proyecto pueden hacer que mezcle
los hechos proporcionados. `qwen3.5:2b` es la ruta de chat compatible más pequeña.
La revisión de la salida es cualitativa y depende del prompt.

## Elección de embeddings

La ficha del modelo Qwen reporta medias MTEB multilingües de 64.33 y 69.60
para sus modelos de embeddings 0.6B y 4B. TrinaxAI usa el preset 0.6B en `8gb`
y `16gb`, y el preset 4B en `32gb` y `64gb`, con dimensiones 1024 y 2560.
No existe un preset actual de embeddings 8B. Una comprobación local en español con 0.6B separó un pasaje
relevante del perfil de TrinaxAI (coseno 0.6686) de una receta no relacionada
(0.1820), y coincidió con la consulta equivalente en inglés en 0.8412. TrinaxAI
añade una instrucción de recuperación a las consultas y embebe los pasajes
almacenados sin ella.

Los números de latencia son específicos de este host. Repite el benchmark en
hardware, cuantización o versiones de Ollama materialmente diferentes antes de
cambiar perfiles.

[English version](MODEL_BENCHMARK.md) · [Documentation index](README.es.md)
