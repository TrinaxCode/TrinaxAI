<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🩺 Troubleshooting
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="TROUBLESHOOTING.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

TrinaxAI surfaces a recovery message when a request cannot finish. Start with
the action shown in the PWA or CLI; this page is the fallback when the action
is unavailable, unclear, or the problem returns. Do not delete `storage/` as a
first step: it contains indexes, collections, memory, state, and recovery data.
Back it up before any destructive maintenance.

## Fast path

| Symptom | First action |
|---|---|
| **The selected collection contains no indexed documents.** | Select **Open indexing** in the message, choose a folder and collection in **Settings → Indexing**, then wait for the job to finish. Selecting or attaching a file does not index it automatically. |
| The selected collection was not found. | Open **Settings → Indexing → Collections**, choose an existing collection or create one, select it in chat, then retry. The CLI equivalent is `trinaxai collections list`. |
| An indexing job failed or stopped. | Open **Settings → Indexing**, inspect the failed phase, and select **Retry**. Reindex only after checking the source, model, and available memory. |
| The PWA says the local service is offline. | On the host, select **Start AI** in the local PWA or run `trinaxai status` and `trinaxai doctor`. |
| A model is missing. | Run `ollama list`, then `ollama pull MODEL`, or use the model action in **Settings → General**. Confirm that the selected model matches the active profile. |
| A model will not load, or memory is exhausted. | Stop competing workloads, choose a smaller model/profile, lower concurrency or context, and retry. Do not remove the index unless the error says the embedding configuration changed. |
| A phone cannot open the PWA. | Run `trinaxai network refresh` on the host, open the printed HTTPS URL, trust the public CA on the phone, and allow only gateway port `3334`. Keep `3333` and `11434` closed to the LAN. |
| Search mode cannot find the web. | Check the configured provider and Internet connection. Local RAG does not require Internet; use RAG when the answer should come from indexed files. |
| The UI is stale after an update or network change. | Accept the PWA update, reload once, and if necessary unregister the old service worker/site data for the old origin. Run `trinaxai network refresh` after a LAN address change. |

## What the recovery action means

The PWA combines a safe explanation with the next useful action when the error
is recognized:

- **Open indexing** appears for an empty or missing RAG collection. It opens
  the host-only indexing area; the device still needs the permission to make
  that change.
- **Retry** is appropriate for a transient network, provider, timeout, or
  failed index-job error. It does not change the source or collection.
- **Start AI** starts the local services from the host. A paired phone cannot
  administer the host lifecycle.
- **Open settings** is used for model, profile, and provider configuration.

An attachment used as chat context is not the same as an indexed source. To
make a folder available to future RAG turns, index it into a collection and
wait for a successful job. Then select that collection in the chat and retry
the question.

## Diagnose in order

Run the smallest check that answers the current question. Commands run from
the repository root unless stated otherwise.

```bash
# 1. Service state and basic checks
trinaxai status
trinaxai doctor

# 2. Machine-readable gate for scripts or support
trinaxai doctor --strict --json

# 3. Provider and installed models
ollama list
```

For a direct local health check, prefer a trusted CA bundle printed by
`trinaxai network`:

```bash
curl --cacert PATH_TO_PUBLIC_CA.pem https://localhost:3333/health
```

`curl -k https://localhost:3333/health` is acceptable only as a loopback
diagnostic when the local certificate is not yet trusted. Never use `-k` as a
way to make an untrusted LAN connection safe, and never expose the API or
Ollama ports directly to the network.

Useful log locations are `logs/rag_api.log`, `logs/frontend.log`,
`logs/supervisor.log`, and `logs/recovery.log`. Logs contain request IDs and
diagnostic state, but support bundles must still be redacted before sharing.

## Decision tables

### RAG and indexing

| Check | Meaning | Next step |
|---|---|---|
| Collection is empty | No published source belongs to the selected collection. | Open indexing, select the correct collection, index a supported folder/file, and wait for `completed`. |
| Job is still running | The new index generation is not published yet. | Keep the page open or reconnect to the job; do not start another full job for the same root. |
| Job failed | The current generation remains protected; the failed generation was not published. | Read the phase and recent activity, correct the source/model/resource issue, then use **Retry**. |
| Sources exist but answers have no evidence | The chat may use another collection, a stale in-memory index, or no relevant chunks matched. | Confirm active collections, inspect **Sources**, then reload the backend with `POST /system/reload` from the host if configuration changed. |
| Embedding model, dimensions, or chunk strategy changed | Existing vectors are no longer compatible with the new configuration. | Back up `storage/`, run a complete reindex, and wait for publication before querying. |
| Only one file is missing | The source may be unsupported, unreadable, excluded, or outside the selected root. | Check the job result and file extension; use `trinaxai browse list-files` and inspect the source path. |

`reload` refreshes a published index in memory; it does not create embeddings
and it is not a substitute for reindexing.

### AI models and resources

| Symptom | Check | Action |
|---|---|---|
| `model not found` | `ollama list` | Pull the exact configured model or choose an installed model in Settings. |
| Model loading failed | RAM/VRAM and the active profile | Select a smaller model, reduce context/concurrency, close other workloads, and retry. |
| Embedding requests are slow | `TRINAXAI_EMBED_KEEP_ALIVE`, workers, and batch size | Keep the embedder warm for a batch; lower workers/batch when memory is tight. |
| GPU unavailable | Hardware status and the selected profile | Use the CPU-compatible profile/model or make the GPU available. |
| Requests time out | `trinaxai doctor`, model size, file size, and recent logs | Narrow the request, use a smaller file/model, and retry before increasing limits. |

The canonical profiles are `8gb`, `16gb`, `32gb`, and `64gb`. Legacy `max` and
`ultra` values are compatibility aliases, not additional current profiles.

### PWA, LAN, and HTTPS

| Symptom | Check | Action |
|---|---|---|
| Host PWA does not load | `trinaxai status`; local port `3334` | Start the PWA/service manager and open `https://localhost:3334`. If **Stop ALL** was used, open the loopback recovery page and select **Start AI**. |
| Phone cannot connect | Host URL, firewall, and port `3334` | Run `trinaxai network refresh`, use the new HTTPS URL, allow only `3334`, and trust the public CA on the device. |
| Certificate warning persists | CA installation and the URL hostname | Install the public CA/profile on that device and use the printed IP or `.local` hostname. Do not transfer the private key or bypass verification. |
| Actions are disabled remotely | Effective device scope and origin | Perform indexing, model, lifecycle, Agent, and device administration from `https://localhost:3334` on the host. Pairing is not host administration. |
| Old address or blank UI remains | Origin-specific cache/service worker | Remove the old PWA origin's site data, reopen the current URL, and accept the update. |

### Web search, Agent, and voice

- Web search requires a configured provider and Internet access. Run the
  Research preflight or inspect **Settings → Web search**; a disabled provider
  is not an indexing failure.
- Agent file actions require a registered workspace and may pause for approval.
  A remote paired device cannot use host-only Agent or shell administration.
- Voice availability depends on browser permissions, local audio hardware, and
  optional Python extras. Check `GET /v1/voice/capabilities` before debugging
  STT/TTS; a `501` means the local engine is not installed or available.

### Storage and recovery

- Before upgrades, model changes, or full reindexing, run `./backup.sh` and keep
  `.env` backed up separately without publishing it.
- Retry or cancel a failed job before removing any data. Failed and cancelled
  generations are not published over a working generation.
- If **Stop ALL** was intentional, the host-only recovery page at
  `https://localhost:3334/` is expected. Start the services there; do not delete
  `storage/`.
- If recovery itself does not open, inspect `storage/recovery.pid` and
  `logs/recovery.log`, then use `trinaxai status` from the host. Escalate before
  manually removing state files.

## Error contract for integrations

API clients should use the structured fields instead of matching the English
message:

```json
{
  "detail": {"category": "...", "code": "...", "message": "...", "recovery": "...", "retryable": true},
  "error": {"category": "...", "code": "...", "message": "...", "recovery": "...", "retryable": true},
  "request_id": "..."
}
```

The frontend also recognizes legacy RAG codes such as `collection_empty` and
`collection_not_found` and maps them to **Open indexing**. Canonical server
categories include `ai_model_unavailable`, `model_loading_failed`,
`permission_denied`, `authentication_failed`, `resource_exhausted`,
`memory_limit_reached`, `file_not_found`, `document_unreadable`,
`invalid_input`, `unsupported_format`, `network_timeout`, and
`internal_server_error`. Respect `retryable` and `Retry-After`; preserve
`request_id` for support, but do not display or log tokens and private content.

See the complete [API error contract](API_REFERENCE.md#error-contract),
[configuration reference](CONFIGURATION.md), and [CLI reference](CLI_REFERENCE.md).

## Support bundle

When the first action does not solve the problem, include:

1. TrinaxAI version, OS, Python, Node.js, Ollama version, RAM/GPU, and active
   profile.
2. The exact action or command, approximate time, and whether the request came
   from localhost or a paired device.
3. Redacted output from `trinaxai doctor --strict --json`, relevant status, and
   the API `request_id`.
4. The affected collection, file type, model/profile, and index-job ID—but not
   the file contents.
5. The relevant log excerpt with tokens, API keys, private paths, prompts, and
   personal documents removed.

Open a community issue only after checking [Support](SUPPORT.md). Send suspected
security vulnerabilities through [Security](SECURITY.md), not a public issue.
