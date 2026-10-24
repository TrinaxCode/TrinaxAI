<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🧭 Changelog
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.3.0"><img src="https://img.shields.io/badge/version-1.3.0-006bbd" alt="Stable release: 1.3.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="CHANGELOG.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

All notable changes to TrinaxAI are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

## [1.4.0] — 2026-10-23

### Added

- `trinaxai research --web` grounds the research on web search, as the chat's deep-research mode
  does. Without it, a general question ("what is an inverted index?") was answered only from
  indexed documents and returned unrelated fragments.
- `trinaxai network off` returns TrinaxAI to this computer only after you allowed
  other devices, and `trinaxai network` now says whether that access is on. Before,
  undoing the installer's "allow other devices" answer meant editing `.env` by hand.
- `trinaxai ask` and the RAG chat list the files an answer comes from
  (`Sources: aurora.md, manual.pdf (p. 3)`), as the web app already did. An
  answer that says the information is missing lists none.
- The installer asks whether other devices on your home or local network may open
  TrinaxAI. The default is this computer only; a yes sets
  `TRINAXAI_PWA_HOST=0.0.0.0`, and every device still needs a one-time pairing
  code. Use `--lan-access` / `--no-lan-access` (or `TRINAXAI_LAN_ACCESS`) to
  answer without being asked. Host administration stays on this computer
  whatever you choose.
- Guided, client-first setup. `trinaxai setup` opens with a welcome and a
  language choice (English or Spanish), checks free disk space and the GitHub
  connection, asks every optional question up front, and shows an installation
  plan to confirm before anything changes. On an existing installation it
  offers to repair, update, or uninstall it, and a bare `trinaxai` before
  installing offers to set it up. The Windows installer now asks for a
  language too. The launcher retries failed downloads, falls back to `curl`
  behind proxies, accepts `--yes`, `--interactive`, and `--language`, and
  answers in your language.
- `trinaxai uninstall` accepts `--remove-app`, `--remove-env`,
  `--remove-certs`, and `--dry-run`; `trinaxai update` accepts `--dry-run`.

- `trinaxai agent` now works like other terminal coding agents: a
  `● tool(args)` / `⎿ result` transcript with a live "Working…" status, real
  unified diffs on approval prompts, three-way approvals (yes / don't ask again
  / no), permission modes (`default`, `accept-edits`, `plan`, `yolo`) cycled
  with Shift+Tab, `@file` attachments, a `todo_write` checklist,
  `TRINAXAI.md` / `AGENTS.md` / `CLAUDE.md` project instructions, persistent
  prompt history, Ctrl-C that rolls the turn back, `/compact`, `/status`,
  `/diff`, `/init`, `/resume`, session `--continue`/`--resume`, and
  non-interactive `-p`, stdin and `--output-format json` runs.

- Per-device permissions: the host chooses what each paired device may do when
  it generates the pairing code and can change it later from **Settings →
  Advanced → Paired devices → Permissions** or with `trinaxai pair set`. New
  grantable permissions are `index` (index/watch folders, manage collections
  and sources), `agent` (use TrinaxAI Agent, still confirming every dangerous
  action) and `modify` (edit memory and web-search settings, delete
  attachments). The host confirms before granting any of them.
- `PATCH /v1/pairing/devices/{id}` to replace a device's permissions
  (loopback-only).

- The Linux installer now installs `bubblewrap` (best-effort) so the Agent's
  terminal tool works out of the box, and `trinaxai doctor` reports an
  "Agent shell sandbox" row (informational, never fails `--strict`).
- `tests/fixtures/rag_docs_golden.json`: a harder retrieval benchmark over
  TrinaxAI's own documentation (20 files, English corpus, Spanish and English
  queries, abstention cases), run live in CI next to the smoke corpus.
- `tests/test_route_scope_contract.py` pins the device scope of every HTTP
  route, so adding or re-scoping an endpoint is an explicit, reviewed change.
- Spanish counterparts for `npm-package/README.md` and ADR 0001, plus a
  `public_readiness.py` check that every Markdown document has a `.es.md` twin
  with the same headings and code blocks.

### Changed

- The agent no longer asks you to approve a plain `git commit -m ...` when nothing is staged
  (the usual first attempt of small local models, which always fails): it is refused up front
  with the fix (`add <file>` or `commit -a`). Commits with `-a`, `--amend`, `--allow-empty`,
  paths, and anything during a merge, cherry-pick, revert or rebase are left to git.
- When the agent's `git commit` fails because nothing is staged (or the tree is clean), the
  result now says so and how to fix it (`add <file>`, or `commit -a`) instead of only git's raw
  text. Small local models often commit before staging; with the real model this did not stop the
  first attempt from failing, but the failure is now explained.
- `trinaxai ask` and `trinaxai chat` use the model the installer chose for your
  computer (`TRINAXAI_MODEL_GENERAL`) instead of a fixed `qwen3.5:2b`, which left
  them on the smallest model even on machines with room for a better one. Set
  `model` under `[defaults]` in the CLI config to pin one.
- The interactive `trinaxai agent` loads the model and its fixed prompt in the
  background while you type your first task. On a 4-core CPU with `qwen3.5:4b`
  the first task went from 82.6 s to 35.2 s after the warm-up. Nothing changes
  for one-shot runs (`-p`), where the task is sent right away.
- English/Spanish documentation parity: `CONFIGURATION`, `API_REFERENCE`,
  `CLI_REFERENCE`, `ENVIRONMENT_VARIABLES`, `SECURITY` and the PWA README now
  carry the same sections in both languages, and the Spanish CLI localizes the
  remaining help text (`pair`, `agent --permission-mode`), table headers and
  status lines.
- The `8gb` profile now defaults to a 4096-token window. With 2048, three
  retrieved chunks filled it and the model could stop after one token.
- The README and security guide now state that the Agent's terminal tool is
  sandboxed only on Linux and stays disabled on macOS and Windows unless
  `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1`; file tools work everywhere.
- Edge-case test modules are named after the domain they exercise instead of
  `*_coverage*`; the unused `trinaxai-ui-preview` prototype was removed.
- The flat root Python modules (`config`, `trinaxai_core`, `trinaxai_errors`,
  `trinaxai_index_{documents,state,storage}`, the indexer, `service_manager` and
  `recovery_server`) now live in the `trinaxai` package
  ([ADR 0001](adr/0001-python-package-layout.md)). Every old path is kept:
  library names are aliases of the same module object, and `index.py`,
  `service_manager.py`, `recovery_server.py` and `rag_api.py` stay at the root as
  launchers, so installers, units, scheduled tasks and the CLI that run them by
  path keep working across an upgrade, even before `pip install -e .` refreshes
  the editable install. Installer and updater scripts are unchanged; the new
  layout has only been run on Linux, not on macOS or Windows.

### Fixed

- After "rename X to Y" the agent searches the project for the old name and, if any whole-word use is left
  (a call no test covers), sends itself back to update it instead of reporting "renamed everywhere".
- The agent no longer lists an earlier failed test run under an answer once a later run passed (it said
  the command failed after it had been fixed).
- When a command the agent ran fails (for example a test its change broke) and it is about to report
  success, it is now asked, up to twice, to read the error, fix the cause and run it again. In a real
  rename across three files it had left one call unrenamed and still reported "functional".
- The agent's "create one file" shortcut (which ends the turn right after the first write) now applies
  only when exactly one file is requested and nothing is to be run, so "create the module and its
  tests, then run them" is no longer cut short with "Created primos.py".
- The agent no longer stops after the first file when it was also asked to run something ("create the
  module and its tests, run them"): if nothing has been run it is asked once to run it. Its
  "you claimed a change you did not make" check also stops firing after a real edit.
- `trinaxai research` no longer sends the CLI's default "thinking on" preference: on a CPU the model
  spent its whole budget reasoning and the web synthesis never finished (2.5 minutes, then only
  a list of sources). It now lets the server choose, as the web app does, and `--thinking` /
  `--no-thinking` still force it. A web lookup now answers in under a minute here.
- When `trinaxai research` runs out of its wait limit on a slow computer, the CLI no longer blames
  the network ("The network request timed out"): it says TrinaxAI did not finish in time and
  suggests `--depth 1`. `TRINAXAI_CLI_TIMEOUT` raises the limit.
- `trinaxai research "your question"` takes the topic as plain words, like `ask`; `--query` still
  works. Forgetting it now says how to write the command instead of "--query is required".
- On Debian and Ubuntu the agent's terminal could not find `python3`, `python`, `cc` or `awk`
  ("python3: not found"), because those names are links through `/etc/alternatives`, which the
  sandbox did not include. That one read-only folder of links into `/usr` is now mounted (the
  rest of `/etc` stays hidden), so "run the tests" works on those systems.
- `install.sh`, `update.sh` and `uninstall.sh` print plain text (no color codes) when its output is piped or `NO_COLOR` is
  set, so logs and CI output are readable.
- Indexing says a file with no text is "empty, or a scan that needs OCR" and is checked
  again on the next run, instead of the vaguer "will retry".
- `trinaxai ask --collection x` says "The collection 'x' does not exist" and how to list
  collections, instead of "Start TrinaxAI with: trinaxai start". Typed API errors during a
  RAG answer now show their own message, and the CLI also finds a local API served over
  plain HTTP when it streams an answer.
- Indexing names the files it skips for being too large, with their size and the limit
  (`huge.txt (5.7 MB; limit 3.0 MB)`), instead of only counting them.
- The CLI works when the local API runs without HTTPS (no certificate could be created for
  it): it now follows the port to plain HTTP on this computer instead of reporting that
  the service is stopped. A server that does speak HTTPS is never downgraded.
- `trinaxai network` no longer lists LAN addresses to open while access is limited to
  this computer, where nothing listens on them. It shows `https://localhost:3334` and
  how to allow other devices.
- "Show me the git diff" and "muéstrame el git log" now go to the agent, which can run
  them, instead of being answered as a chat question.
- `trinaxai` no longer treats a URL such as `https://example.com/page.html` as a
  file in your workspace, and questions about git or files ("why does git push
  fail?", "how do I read data.csv in pandas?") stay a conversation instead of
  starting the coding agent.
- `trinaxai network` and `network off` read `.env` the way the service does
  (indented lines, `KEY = value`, quotes), so they no longer miss a setting the
  service honours.
- A short answer that states the information is missing after a sentence of
  context ("The documents cover X, but Y is not mentioned") no longer lists
  sources for the missing information.
- The agent's git errors are recognised whatever language the system speaks, so the
  hint that tells the model what to do next always appears.
- `trinaxai doctor` and every command say "This computer does not trust the local
  TrinaxAI certificate. Run: trinaxai doctor" when the certificate is the problem,
  instead of claiming the service is stopped.
- A config file saved by an older version, which pinned `qwen3.5:2b`, now means
  "automatic" again, so `ask`/`chat` use the model the installer chose. To pin one, set
  `model = "<name>"` under `[defaults]` in the config file or pass `--model`.
- `trinaxai doctor` no longer repeats the start command when TrinaxAI is stopped
  ("Start it with: trinaxai start; run: trinaxai start").
- In the web app's coding agent, a tool that ran but failed (for example a `git commit`
  that exited with an error, or a command with a non-zero exit code) no longer shows a
  green check next to its error text; it shows a warning icon.
- A correct, long answer is no longer mistaken for a refusal (and stripped of its
  sources) just because a phrase like "is not available" appears in the middle of
  the explanation. Refusals are only recognised at the start of an answer.
- `./install.sh --dry-run` no longer announces a LAN link when you chose to keep
  TrinaxAI on this computer only; it says so, as the real installation does.
- `trinaxai models` shows model sizes as `3.1 GB` instead of a raw byte count, and the
  `trinaxai doctor` row about the agent's terminal sandbox is translated to Spanish.
- The terminal assistant now sends file and version-control requests to the coding
  agent instead of answering them as plain chat: "fix the bug in calc.py",
  "read main.py and tell me what it does", "commit these changes". Questions about
  those topics ("what is a git commit?", "what does next.js do?") stay in chat.
- `trinaxai status` shows a service that is not running as `stopped` instead of the
  contradictory `stopped not found`.
- The web app no longer asks you to "prepare this network" when TrinaxAI is kept
  on this computer only. A changed Wi-Fi address or an out-of-date LAN
  certificate only matters when other devices can connect, so the notice now
  appears only if you allowed access from your local network.
- Errors now name the real cause. With TrinaxAI stopped the CLI no longer says
  "the internet connection is unavailable" but "Cannot reach the local TrinaxAI
  service. Start it with: trinaxai start". A model that is not installed is
  reported as such (`The model 'x' is not installed. Install it with: ollama
  pull x`) in the CLI and the API, instead of a generic "start TrinaxAI" or
  "external service unavailable", and "Please retry" is only suggested when a
  retry can help.
- `trinaxai index` no longer prints the internal `TRINAXAI_PROGRESS` lines, and
  `trinaxai collections list` shows a readable date instead of a raw timestamp.
- Answers are no longer slowed down by too many CPU threads. `TRINAXAI_NUM_THREAD`
  defaulted to a fixed 8; on a 4-core computer that made the same answer take
  76-93 s instead of 16 s. The default is now the smaller of 8 and the CPUs you
  have.
- A refusal such as "I don't have access to that information" (including the
  typographic apostrophe and common Spanish wordings) is now recognised, so
  TrinaxAI no longer lists an unrelated file as the source of an answer that
  says the information is missing.
- `trinaxai stop`, `restart` and `status` no longer touch processes that are not
  TrinaxAI's. They used to match words such as `npm run dev`, `vite --host`,
  `node server.mjs` or `ollama` anywhere in a command line, so `status` could
  report the PWA as running because of another project's dev server, and `stop`
  ended that dev server. A process now counts only when it is the expected
  program and runs from this installation's folder (Linux and macOS; Windows
  keeps the previous matching).
- `uninstall.sh --remove-ollama` and `update.sh --remove-ollama` ended themselves:
  they stopped Ollama with `pkill -f ollama`, which also matches their own
  `--remove-ollama` argument, so the removal stopped half-way. They (and the
  Windows scripts) now stop Ollama by exact process name.
- The research preflight no longer blocks the API while it probes Ollama.
- The Agent's prompt now tells the model to use the `git` tool for git, and a
  `git` call that can never succeed (a refused option, an unknown subcommand) is
  reported to the model at once instead of asking you to approve it first.
- The agent's code-review grounding checks recognize the Python 3.13 wording of the `turtle` docstrings, so verified evidence still catches false claims about `goto` on every supported interpreter.
- The changelog release badge now points to 1.3.0 in both languages.

### Security

- Updated `nltk` to 3.10.4 (GHSA-8mgp-746c-j5xp, path traversal in its model
  APIs) and removed the audit exception: `pip-audit` now fails on any known
  vulnerability.
- Updated `pypdf` to 6.21.2 (CVE-2026-115572, CVE-2026-115580,
  CVE-2026-115585) and `setuptools` to 84.1.0 (GHSA-xmj3-9gf7-h52w) in the
  dependency lock, and the development-only `zod` to 4.6.7 (GHSA-mrhx-c7xc-m3w5)
  in the PWA lockfile, plus the development-only `undici` (7.30.1),
  `fast-uri` (3.1.9) and `serialize-javascript` (7.1.4) after new advisories.
- The Agent's terminal sandbox now mounts the workspace's `.git/config` and
  `.git/hooks` read-only. The file tools already refused to write git metadata,
  but a shell command could plant aliases or hooks that git later runs for you
  outside the sandbox. `git add` and `git commit` keep working in the sandbox,
  using your git name and email (it cannot see your global git configuration
  otherwise).
- The Agent has a `git` tool that runs git on your computer with your own git
  setup, so it can commit, push and pull when you ask. Reading commands (status,
  diff, log) run freely, changing commands ask first, and anything that contacts
  a remote asks every time (no "don't ask again"; only `--yolo` skips it). It
  accepts a fixed list of subcommands, refuses options that run programs or read
  outside the repository, keeps hooks off unless `TRINAXAI_AGENT_GIT_HOOKS=1`,
  needs the workspace to be the repository root, and refuses remote commands
  from paired devices.
- The API and the PWA gateway now reject requests whose `Host` header names a
  foreign domain (`421`). This blocks DNS-rebinding pages from reading private
  data when TrinaxAI runs over plain HTTP (no local certificate, or Docker).
  Add custom host names to `TRINAXAI_ALLOWED_HOSTS`.
- Agent hardening: "don't ask again" no longer widens to test runners or type
  checkers, rules for commands that run workspace code expire individually
  after the Agent edits a file, the Agent's file tools refuse every spelling of
  `.git`, and `/diff` runs git inside the sandbox (or with config overrides).
- `system` and the Agent's auto-approve (YOLO) mode remain impossible to grant
  to a device. Elevated permissions are granted only by the localhost operator,
  are ignored on records created before this change until granted again, and an
  admin token sent over the network does not unlock them.
- A device with `index` can only watch folders inside the host's configured
  indexing roots.
- A device with `agent` can never use or browse a workspace that holds
  TrinaxAI's own files (install directory, `.env`, storage, credential
  secrets), even when the host's workspace roots include them.
- Deleting an imported source resolves symlinks before checking that the path
  stays inside the imports folder.

### Fixed

- Passing `--language es` (two words) to the installer, updater, or uninstaller
  no longer asks for the language a second time.
- Answering "sí" or "s" to a default-No question no longer counts as No, and
  Spanish prompts now read `[S/n]`.
- Installer messages that appeared in English in Spanish mode are translated,
  and a failed install says it is safe to run again.

## [1.3.0] — 2026-10-18

### Changed

- Reworked the public documentation around one npm installation path, clarified
  first-run and platform operations, aligned the English and Spanish guides,
  and removed obsolete direct-installer onboarding.
- Cross-platform release checks, Windows and macOS test paths, and watcher
  status handling were stabilized.

### Fixed

- Shared app state: a transient read error no longer looks like an empty store
  that the next sync would overwrite; corrupt files are quarantined instead.
- Backup restore: rollback can no longer delete the original data when moving
  it aside fails.
- Source updates: the rollback marker is removed before the backup, so a
  half-deleted backup is never restored.
- Indexing: the watcher worker survives out-of-space and other batch failures
  and keeps processing the queue; unreadable manifests and collection lists
  are no longer treated as empty.
- PWA: the network notice closes properly after preparing a new link, and the
  `trinaxai pair` link opens Settings > Advanced instead of the chat.
- Voice: read-aloud text is no longer cut mid-word, calls keep the screen awake
  after returning to the tab, the system TTS picks the matching language voice,
  and temporary audio files are cleaned up on failed writes.
- Piper now uses the real `piper` package API, Coqui picks its model by
  language, and concurrent LibreOffice conversions no longer fail.

## [1.2.6] — 2026-09-20

### Added

- Added the verified npm launcher: `npm install --global trinaxai@latest` followed by `trinaxai setup`.
- Added a fresh-device LAN pairing flow and expanded release/UI regression coverage.

### Changed

- Refreshed the chat and Agent surfaces, document handoff, voice support, indexing feedback, and bilingual documentation.
- Release publication now validates and publishes the npm CLI before making the GitHub release public.

### Fixed

- Hardened device cookies, lifecycle services, research/RAG runtime handling, installer updates, and web-search boundaries.

## [1.2.5] — 2026-09-13

### Fixed

- Preserved `chat-pwa/node_modules` and `chat-pwa/dist` during source updates so
  npm-generated `.bin` symlinks are not mistaken for unsafe source links.

## [1.2.4] — 2026-09-11

### Fixed

- Allowed installations and updates to defer model downloads with `--no-models`.
- Made macOS npm caches independent from root-owned `~/.npm` entries.
- Made uninstall path checks work through macOS `/tmp` symlink canonicalization and
  prevented the uninstaller from leaving the loopback recovery server running.

## [1.2.3] — 2026-09-11

### Fixed

- Kept the Agent's approval-mode control inside the mobile tools menu so the
  responsive interface exposes the same controls at narrow and zoomed
  viewports.

## [1.2.2] — 2026-09-11

### Changed

- Split the frontend API into domain modules behind a stable `api.ts` facade.
- Split Agent rendering, execution, voice and shared contracts into focused
  modules while preserving the existing public behavior and tests.
- Kept RAG generation, streaming, runtime, indexing and chat responsibilities
  behind small compatibility facades instead of growing release entry points.

### Documentation

- Added a bilingual troubleshooting and recovery guide that maps common errors
  to safe next actions, including the PWA's **Open indexing** flow for empty
  collections.
- Aligned README, API, CLI, configuration, PWA, support, and in-app Docs with
  current profiles, HTTPS trust, recoverable jobs, and the reserved MCP command.

### Fixed

- Made the one-line installer path explicit for Linux, macOS, and Windows while
  keeping the release package pinned and SHA-256 verified.
- Fixed Windows PowerShell 5.1 parsing by publishing installer scripts with a
  UTF-8 BOM and made native dependency failures stop the installation clearly.
- Kept macOS frontend and lifecycle errors visible instead of closing the
  terminal with no actionable context.
- Corrected PowerShell checksum examples so they parse the `SHA256SUMS`
  manifest line by line.

## [1.2.1] — 2026-09-02

### Changed

- Promoted the validated desktop release to Production/Stable and aligned the
  Python package, CLI, PWA, installers, updater, and documentation on one version.
- Simplified the public installation path to one short command per platform while
  keeping release archives checksum-verified and signed.
- Pinned the release public key in the repository and closed the remaining
  dependency alerts.

### Fixed

- Standalone RAG evaluation now imports the repository package from a clean
  checkout, matching the isolated CLI wheel contract.
- PowerShell release URLs parse correctly on Windows and the installer refuses
  unverified or unpinned source packages.

## [1.2.0] — 2026-08-17

### Added

- Added a collapsible thinking trace with elapsed time, explicit completion
  metadata, and bounded automatic continuation for length-limited answers.
- Added autonomous chat-mode routing across web search, deep research, local
  knowledge and Agent tools, while preserving explicit user overrides.
- Added retained chat attachments with mobile PDF fallbacks, Office downloads,
  and localhost-only native application opening.
- Added a loopback recovery page for a stopped installation, a desktop service
  manager, hardware-aware model profiles, and lifecycle installer dry-runs.

### Changed

- Host administration is now fail-closed and localhost-only. Paired LAN devices
  are limited to chat, private-read and web scopes, and the PWA renders controls
  from the effective capability reported by the server.
- The Windows installer now writes the same canonical `8gb`, `16gb`, `32gb`, and
  `64gb` profiles as the backend, while migrating legacy `max`/`ultra` values.
- `trinaxai network` now prints the public CA/certificate path needed to trust a
  LAN browser, with a bilingual Android/iOS pairing and HTTPS guide.
- English and Spanish setup, security, API, CLI and testing guides now describe
  the current installers, recovery flow, model selection and LAN boundaries.
- Expanded the documentation hub and configuration/API references, aligned the
  in-app PWA Docs with the repository, and replaced its placeholder architecture
  image with an accessible overview.

### Fixed

- Long chat, RAG, research and Agent responses now terminate with an explicit
  complete, length, cancelled or error state instead of silently appearing
  complete after truncation.
- Improved responsive PWA navigation, keyboard/focus behavior, accessible
  labels, offline handling and attachment actions across desktop, tablet and
  phone viewports.
- Release publication now builds signed source archives, installers, and the
  CLI-only wheel, includes them in `SHA256SUMS`, and verifies every published
  asset after download.

## [1.1.0] — 2026-08-05

### Added

- Added `trinaxai network refresh` and an accessible PWA recovery notice for
  stale cached origins after Wi-Fi, router, or LAN address changes.
- The offline copy can explicitly erase its cache, local data, and service
  worker to remove an installation saved at an old address.
- A new address detects existing server state and opens pairing recovery
  instead of repeating first-time setup.
- The CLI is now translatable through `trinaxai_cli/i18n.py`, covering the
  app, client, doctor, help and interface output.
- The web app ships a manifest per locale, so an installed app keeps its
  language in the launcher.
- Added Spanish guides for the environment-variable inventory and the model
  benchmark.

### Changed

- Community documentation (changelog, contributing, security, support, code of
  conduct, trademark) moved into `docs/`, leaving the root to entry points,
  build and runtime configuration, and lifecycle scripts.
- Translated documents use a single `*.es.md` convention; `docs/es/` is gone.
- `service_manager` returns accurate exit codes on start actions and gained a
  `reload-network` action.
- Static translation data is bundled as its own JavaScript chunk, cutting the
  largest chunk from 384.5 KiB to 302.3 KiB with no change to total size.

### Removed

- Dropped `install_ollama_16gb_profile.sh`, a wrapper that only forwarded to
  `install.sh --profile 16gb`. Use that command directly.

### Fixed

- `trinaxai doctor` caps its service probe at 10s, so a slow service manager is
  reported as a failed check instead of hanging the command.
- Voice calls and web-search settings behave correctly, and i18n coverage now
  extends across chat, the knowledge browser, settings and pairing.
- The installer, update, uninstall and backup scripts are more robust on Linux,
  macOS and Windows.
- Identity and creator answers are resolved deterministically, so small local
  models no longer distort them.
- Spanish pages link Spanish targets; every relative link in the repository
  resolves.

### Security

- Cryptographic material, certificates, credentials and environment files are
  excluded from indexing (`.key`, `.pem`, `.p12`, `.pfx`, `.netrc`,
  `credentials.json`, `secrets.json` and similar).
- Updated `aiohttp` to 3.14.3, clearing CVE-2026-59881, CVE-2026-69243 and
  CVE-2026-69244.
- Patched three high-severity frontend advisories: `brace-expansion` 5.0.9,
  `fast-uri` 3.1.5 and `undici` 7.29.0.

## [1.0.2] — 2026-08-01

### Fixed

- Initialized the Buildx container driver so the GHCR image can be published
  with SBOM and provenance attestations.

## [1.0.1] — 2026-07-31

### Added

- Published release assets through one verified release workflow.
- Added production gateway coverage and cross-platform CLI, installer, service,
  cancellation, timeout and failure-path tests.

### Changed

- Hardware profiles now scale official Qwen3 embeddings from 0.6B/1024d on
  memory-constrained systems to 4B/2560d on 32/64 GB systems.
- Docker Compose can start with safe defaults when no `.env` file exists.

### Fixed

- Hardened inference timeouts, TLS verification, proxy identity, API errors,
  cleanup paths and Windows/macOS/Linux release checks.

## [1.0.0] — 2026-07-21

### Added

- Local-first PWA with Ollama chat, cited RAG, optional web research, vision,
  voice and capability-scoped device pairing.
- Hybrid project/document indexing with collections, AST-aware code chunks,
  durable progress, cancellation, retry and safe incremental publication.
- One packaged `trinaxai` CLI for chat, agent, indexing, research, memory,
  collections, watchers, pairing, diagnostics and service lifecycle.
- Tool-using agent constrained to approved workspaces, with confirmation for
  dangerous actions and a network-isolated Linux shell sandbox.
- Cross-platform installers and service supervision for Linux, macOS and
  Windows, plus bilingual product and technical documentation.

### Changed

- Automatic model profiles cover memory-constrained through 64+ GB systems and use
  multilingual `qwen3-embedding:0.6b` embeddings by default.
- The PWA includes refreshed install icons, a clearer Call Mode and accessible
  reduced-motion behavior.
- CLI HTTPS remains verified and accepts private certificate authorities through
  `--ca-file` or `TRINAXAI_CA_FILE`.

### Fixed

- Plain greetings in automatic CLI mode use normal Ollama chat instead of
  forcing an empty RAG lookup.
- Generation, RAG, research, agent, memory, pairing, service and web-search
  failures now terminate predictably and preserve shared state.
- Microphone streams, Web Audio nodes, timers, previews and upload listeners are
  released on cancellation, navigation and errors.
- Large documents and uploads use bounded batches, timeouts and cleanup paths;
  failed indexing never publishes a partial generation.
- Packaging now exposes only the modular CLI and produces a consistent wheel,
  source archive, installers and checksums.

### Security

- Ollama base URLs are centrally restricted to valid HTTP(S) endpoints before
  network access by the backend, CLI, agent and diagnostics.
- Trusted-proxy assertions are signed, short-lived and single-use; protected
  operations require scoped pairing or explicit administration credentials.
- CI checks Python and frontend dependencies, static high-severity findings,
  committed secrets, package builds, browser flows and public-release readiness.

[1.2.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.2
[1.2.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1
[1.2.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0
[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.1.0
[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
