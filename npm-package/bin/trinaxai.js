#!/usr/bin/env node

"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");
const { spawnSync } = require("node:child_process");
const https = require("node:https");

const PACKAGE_VERSION = require("../package.json").version;
const RELEASE_REPOSITORY = "TrinaxCode/TrinaxAI";
const RELEASE_HOST = "https://github.com";
const MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024;
const DOWNLOAD_ATTEMPTS = 3;

const MESSAGES = {
  en: {
    welcomeTitle: "Welcome to TrinaxAI",
    welcomeBody: "Your private AI assistant that runs on your own computer.",
    welcomeSteps: [
      "Check your system and download the verified installer",
      "Choose your hardware profile and models",
      "Install everything locally (nothing leaves your machine)",
    ],
    welcomeFooter: "You can press Ctrl+C at any time. Setup can be run again safely.",
    languagePrompt: "Select language",
    languageChoose: "Choose [1-2]",
    existingFound: "TrinaxAI is already installed at {root}{version}.",
    existingPrompt: "What would you like to do?",
    existingRepair: "Repair or reinstall (keeps your data and settings)",
    existingUpdate: "Update to the latest version",
    existingUninstall: "Uninstall TrinaxAI",
    existingCancel: "Cancel",
    existingChoose: "Choose [1-4]",
    cancelled: "Cancelled. Nothing was changed.",
    downloading: "Downloading the TrinaxAI {version} installer...",
    verified: "Installer verified (SHA-256).",
    retrying: "Download failed ({reason}); retrying ({attempt}/{total})...",
    curlFallback: "Direct download failed; trying through curl (honors your proxy settings)...",
    downloadFailed: "Could not download TrinaxAI. Check your internet connection or proxy, then run: trinaxai setup",
    checksumFailed: "The installer failed SHA-256 verification and was not run. Try again; if it persists, report it at https://github.com/TrinaxCode/TrinaxAI/issues",
    notInstalled: "TrinaxAI is not installed yet. Run: trinaxai setup",
    installNow: "TrinaxAI is not installed yet. Set it up now? [Y/n]",
    notInstalledUninstall: "Nothing to uninstall: TrinaxAI is not installed.",
    unsupported: "This platform is not supported: {platform}. TrinaxAI supports Linux, macOS and Windows.",
    needShell: "bash is required to run the TrinaxAI installer but was not found.",
    needPowerShell: "PowerShell is required to run the TrinaxAI installer but was not found.",
    setupFailed: "Setup did not finish (exit code {code}). The error is above. It is safe to run \"trinaxai setup\" again.",
    setupDone: "Setup finished. Next: trinaxai doctor",
    uninstallLauncher: "The installed app was removed. To remove this launcher too: npm uninstall -g trinaxai",
    versionLine: "launcher {launcher}, installed app {installed}",
    updateHint: "The installed app is {installed} but this launcher is {launcher}. Run: trinaxai update",
    optionValue: "{option} requires a value",
    unknownOption: "Unknown setup option: {option}",
    invalidLanguage: "Unsupported language: {value} (use en or es)",
    help: `Usage:
  trinaxai setup [options]   Install, repair, update or uninstall TrinaxAI
  trinaxai <command>          Run the installed TrinaxAI CLI

Setup options:
  --language en|es            Skip the language question
  --yes, --non-interactive    Accept the recommended answers; ask nothing
  --interactive               Always ask, even without a detected terminal
  --profile 8gb|16gb|32gb|64gb
  --install-dir PATH          Where to install the application
  --no-models                 Prepare models later
  --no-start, --no-autostart, --no-auto-update
  --dry-run                   Show what would happen; change nothing
`,
  },
  es: {
    welcomeTitle: "Bienvenido a TrinaxAI",
    welcomeBody: "Tu asistente de IA privado que funciona en tu propio equipo.",
    welcomeSteps: [
      "Comprobar tu sistema y descargar el instalador verificado",
      "Elegir tu perfil de hardware y los modelos",
      "Instalar todo localmente (nada sale de tu equipo)",
    ],
    welcomeFooter: "Puedes pulsar Ctrl+C en cualquier momento. Puedes volver a ejecutar la instalación sin riesgo.",
    languagePrompt: "Selecciona el idioma",
    languageChoose: "Elige [1-2]",
    existingFound: "TrinaxAI ya está instalado en {root}{version}.",
    existingPrompt: "¿Qué quieres hacer?",
    existingRepair: "Reparar o reinstalar (conserva tus datos y configuración)",
    existingUpdate: "Actualizar a la última versión",
    existingUninstall: "Desinstalar TrinaxAI",
    existingCancel: "Cancelar",
    existingChoose: "Elige [1-4]",
    cancelled: "Cancelado. No se cambió nada.",
    downloading: "Descargando el instalador de TrinaxAI {version}...",
    verified: "Instalador verificado (SHA-256).",
    retrying: "Falló la descarga ({reason}); reintentando ({attempt}/{total})...",
    curlFallback: "Falló la descarga directa; probando con curl (respeta tu configuración de proxy)...",
    downloadFailed: "No se pudo descargar TrinaxAI. Revisa tu conexión a Internet o tu proxy y ejecuta: trinaxai setup",
    checksumFailed: "El instalador no pasó la verificación SHA-256 y no se ejecutó. Inténtalo de nuevo; si persiste, repórtalo en https://github.com/TrinaxCode/TrinaxAI/issues",
    notInstalled: "TrinaxAI todavía no está instalado. Ejecuta: trinaxai setup",
    installNow: "TrinaxAI todavía no está instalado. ¿Instalarlo ahora? [S/n]",
    notInstalledUninstall: "No hay nada que desinstalar: TrinaxAI no está instalado.",
    unsupported: "Esta plataforma no es compatible: {platform}. TrinaxAI funciona en Linux, macOS y Windows.",
    needShell: "Se necesita bash para ejecutar el instalador de TrinaxAI y no se encontró.",
    needPowerShell: "Se necesita PowerShell para ejecutar el instalador de TrinaxAI y no se encontró.",
    setupFailed: "La instalación no terminó (código de salida {code}). El error aparece arriba. Puedes ejecutar \"trinaxai setup\" de nuevo sin riesgo.",
    setupDone: "Instalación terminada. Siguiente paso: trinaxai doctor",
    uninstallLauncher: "Se eliminó la aplicación instalada. Para quitar también este lanzador: npm uninstall -g trinaxai",
    versionLine: "lanzador {launcher}, aplicación instalada {installed}",
    updateHint: "La aplicación instalada es {installed} pero este lanzador es {launcher}. Ejecuta: trinaxai update",
    optionValue: "{option} requiere un valor",
    unknownOption: "Opción de instalación desconocida: {option}",
    invalidLanguage: "Idioma no compatible: {value} (usa en o es)",
    help: `Uso:
  trinaxai setup [opciones]  Instalar, reparar, actualizar o desinstalar TrinaxAI
  trinaxai <comando>          Ejecutar la CLI de TrinaxAI instalada

Opciones de instalación:
  --language en|es            Omitir la pregunta de idioma
  --yes, --non-interactive    Aceptar las respuestas recomendadas; no preguntar nada
  --interactive               Preguntar siempre, aunque no se detecte una terminal
  --profile 8gb|16gb|32gb|64gb
  --install-dir RUTA          Dónde instalar la aplicación
  --no-models                 Preparar los modelos más tarde
  --no-start, --no-autostart, --no-auto-update
  --dry-run                   Mostrar qué pasaría; no cambia nada
`,
  },
};

function normalizeLanguage(value) {
  const text = String(value || "").trim().toLowerCase();
  if (/^es([^a-z]|$)/.test(text)) return "es";
  if (/^en([^a-z]|$)/.test(text)) return "en";
  return null;
}

function detectLanguage(env = process.env) {
  for (const key of ["TRINAXAI_LANG", "LC_ALL", "LC_MESSAGES", "LANG"]) {
    const language = normalizeLanguage(env[key]);
    if (language) return language;
  }
  try {
    const locale = Intl.DateTimeFormat().resolvedOptions().locale;
    return normalizeLanguage(locale) || "en";
  } catch {
    return "en";
  }
}

function message(language, key, values = {}) {
  const table = MESSAGES[language] || MESSAGES.en;
  const template = table[key] ?? MESSAGES.en[key];
  if (typeof template !== "string") return template;
  return template.replace(/\{(\w+)\}/g, (match, name) => (name in values ? String(values[name]) : match));
}

function releaseBase(version) {
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`Invalid TrinaxAI version: ${version}`);
  }
  return `${RELEASE_HOST}/${RELEASE_REPOSITORY}/releases/download/v${version}`;
}

function installerAsset(platform = process.platform, version = PACKAGE_VERSION) {
  return `TrinaxAI-${version}-installer${platform === "win32" ? ".ps1" : ".sh"}`;
}

function checksumFor(manifest, asset) {
  for (const line of manifest.split(/\r?\n/)) {
    const fields = line.trim().split(/\s+/);
    if (fields.length >= 2 && fields[1].replace(/^\*/, "") === asset) {
      if (!/^[a-f\d]{64}$/i.test(fields[0])) {
        throw new Error(`Invalid SHA-256 entry for ${asset}`);
      }
      return fields[0].toLowerCase();
    }
  }
  throw new Error(`SHA256SUMS does not contain ${asset}`);
}

function downloadOnce(url, redirectCount = 0) {
  if (redirectCount > 5) {
    return Promise.reject(new Error("Too many redirects while downloading TrinaxAI"));
  }

  const target = new URL(url);
  if (target.protocol !== "https:") {
    return Promise.reject(new Error("TrinaxAI downloads must use HTTPS"));
  }

  return new Promise((resolve, reject) => {
    const request = https.get(target, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        response.resume();
        downloadOnce(new URL(response.headers.location, target).toString(), redirectCount + 1)
          .then(resolve, reject);
        return;
      }
      if (response.statusCode !== 200) {
        response.resume();
        const error = new Error(`Download failed with HTTP ${response.statusCode}`);
        error.httpStatus = response.statusCode;
        reject(error);
        return;
      }

      const chunks = [];
      let size = 0;
      response.on("data", (chunk) => {
        size += chunk.length;
        if (size > MAX_DOWNLOAD_BYTES) {
          response.destroy(new Error("TrinaxAI download is unexpectedly large"));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => resolve(Buffer.concat(chunks)));
      response.on("error", reject);
    });
    request.setTimeout(30000, () => request.destroy(new Error("TrinaxAI download timed out")));
    request.on("error", reject);
  });
}

// curl honors HTTP(S)_PROXY and the system trust store, which Node's https does not.
function downloadWithCurl(url) {
  const curl = process.platform === "win32" ? "curl.exe" : "curl";
  const result = spawnSync(curl, [
    "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
    "--max-redirs", "5", "--connect-timeout", "20", "--max-time", "300",
    "--max-filesize", String(MAX_DOWNLOAD_BYTES), url,
  ], { maxBuffer: MAX_DOWNLOAD_BYTES + 1024, encoding: "buffer" });
  if (result.error || result.status !== 0) {
    throw new Error(result.error ? result.error.message : `curl exited with ${result.status}`);
  }
  return result.stdout;
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function download(url, { language = "en", attempts = DOWNLOAD_ATTEMPTS, retryDelay = 1500, log = console.log } = {}) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await downloadOnce(url);
    } catch (error) {
      lastError = error;
      // A definite answer from the server (404, 403...) will not change by retrying.
      if (error.httpStatus && error.httpStatus < 500 && error.httpStatus !== 429) break;
      if (attempt < attempts) {
        log(message(language, "retrying", { reason: error.message, attempt: attempt + 1, total: attempts }));
        await sleep(retryDelay * attempt);
      }
    }
  }
  if (!lastError.httpStatus || lastError.httpStatus >= 500) {
    try {
      log(message(language, "curlFallback"));
      return downloadWithCurl(url);
    } catch {
      // Report the original failure below.
    }
  }
  throw lastError;
}

function setupArgs(args, platform = process.platform, language = "en") {
  const windows = platform === "win32";
  const result = [];
  const flags = new Map([
    ["--non-interactive", windows ? "-NonInteractive" : "--non-interactive"],
    ["--yes", windows ? "-NonInteractive" : "--non-interactive"],
    ["-y", windows ? "-NonInteractive" : "--non-interactive"],
    ["--interactive", windows ? "-Interactive" : "--interactive"],
    ["--no-models", windows ? "-NoModels" : "--no-models"],
    ["--no-vision", windows ? "-NoVision" : "--no-vision"],
    ["--no-autostart", windows ? "-NoAutostart" : "--no-autostart"],
    ["--no-auto-update", windows ? "-NoAutoUpdate" : "--no-auto-update"],
    ["--no-start", windows ? "-NoStart" : "--no-start"],
    ["--dry-run", windows ? "-DryRun" : "--dry-run"],
    ["--lan-system", windows ? "-LanSystem" : "--lan-system"],
  ]);
  const values = new Map([
    ["--profile", windows ? "-Profile" : "--profile"],
    ["--install-dir", windows ? "-InstallDir" : "--install-dir"],
    ["--language", windows ? "-Language" : "--language"],
    ["--lang", windows ? "-Language" : "--language"],
  ]);

  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (flags.has(argument)) {
      result.push(flags.get(argument));
      continue;
    }
    if (values.has(argument)) {
      const value = args[index + 1];
      if (!value || value.startsWith("-")) {
        throw new Error(message(language, "optionValue", { option: argument }));
      }
      result.push(values.get(argument), value);
      index += 1;
      continue;
    }
    const equalsIndex = argument.indexOf("=");
    if (equalsIndex > 0 && values.has(argument.slice(0, equalsIndex))) {
      const option = argument.slice(0, equalsIndex);
      const value = argument.slice(equalsIndex + 1);
      if (!value) throw new Error(message(language, "optionValue", { option }));
      result.push(values.get(option), value);
      continue;
    }
    if (["--help", "-h"].includes(argument)) {
      result.push(windows ? "-?" : argument);
      continue;
    }
    throw new Error(message(language, "unknownOption", { option: argument }));
  }
  return result;
}

function installationCandidates() {
  const candidates = [];
  if (process.env.TRINAXAI_HOME) candidates.push(process.env.TRINAXAI_HOME);
  if (process.platform === "win32") {
    if (process.env.LOCALAPPDATA) candidates.push(path.join(process.env.LOCALAPPDATA, "TrinaxAI"));
    candidates.push(path.join(os.homedir(), "trinaxai"));
  } else if (process.platform === "darwin") {
    candidates.push(path.join(os.homedir(), "Library", "Application Support", "TrinaxAI"));
    candidates.push(path.join(os.homedir(), "trinaxai"));
  } else {
    candidates.push(path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share"), "trinaxai"));
    candidates.push(path.join(os.homedir(), "trinaxai"));
  }
  return [...new Set(candidates.map((candidate) => path.resolve(candidate)))];
}

function isInstallation(root) {
  return [
    "service_manager.py",
    "rag_api.py",
    path.join("chat-pwa", "server.mjs"),
    process.platform === "win32" ? path.join(".venv", "Scripts", "trinaxai.exe") : path.join(".venv", "bin", "trinaxai"),
  ].every((relative) => fs.existsSync(path.join(root, relative)));
}

function findInstallation() {
  return installationCandidates().find(isInstallation) || null;
}

function installedVersion(root) {
  try {
    const text = fs.readFileSync(path.join(root, "pyproject.toml"), "utf8");
    const match = text.match(/^version\s*=\s*"(\d+\.\d+\.\d+[^"]*)"/m);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function runInstalled(args, root) {
  const command = process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "trinaxai.exe")
    : path.join(root, ".venv", "bin", "trinaxai");
  const result = spawnSync(command, args, {
    cwd: root,
    env: { ...process.env, TRINAXAI_HOME: root },
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  return result.status ?? 1;
}

function style(code, text, stream = process.stdout) {
  if (!stream.isTTY || process.env.NO_COLOR) return text;
  return `\u001b[${code}m${text}\u001b[0m`;
}

function isInteractive(args, env = process.env, stdin = process.stdin, stdout = process.stdout) {
  if (args.some((argument) => ["--non-interactive", "--yes", "-y", "--dry-run"].includes(argument))) return false;
  if (args.includes("--interactive")) return true;
  if (env.TRINAXAI_NONINTERACTIVE === "1" || env.CI) return false;
  return Boolean(stdin.isTTY && stdout.isTTY);
}

function ask(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    let answered = false;
    rl.question(question, (answer) => {
      answered = true;
      rl.close();
      resolve(answer.trim());
    });
    rl.on("close", () => {
      if (!answered) resolve("");
    });
  });
}

async function chooseLanguage(defaultLanguage, io = { ask, write: (text) => process.stdout.write(text) }) {
  io.write(`\n${style("1;34", "TrinaxAI")}\n`);
  io.write(`  1) English${defaultLanguage === "en" ? " (default)" : ""}\n`);
  io.write(`  2) Español${defaultLanguage === "es" ? " (predeterminado)" : ""}\n`);
  const reply = (await io.ask(`${message(defaultLanguage, "languagePrompt")} / Language [${defaultLanguage === "es" ? "2" : "1"}]: `)).toLowerCase();
  if (reply === "1" || reply.startsWith("en")) return "en";
  if (reply === "2" || reply.startsWith("es")) return "es";
  return defaultLanguage;
}

function printWelcome(language, write = (text) => process.stdout.write(text)) {
  write(`\n${style("1;34", `=== ${message(language, "welcomeTitle")} ${PACKAGE_VERSION} ===`)}\n`);
  write(`${message(language, "welcomeBody")}\n\n`);
  message(language, "welcomeSteps").forEach((step, index) => write(`  ${index + 1}. ${step}\n`));
  write(`\n${style("2", message(language, "welcomeFooter"))}\n`);
}

async function chooseExistingAction(language, root, io = { ask, write: (text) => process.stdout.write(text) }) {
  const version = installedVersion(root);
  io.write(`\n${message(language, "existingFound", { root, version: version ? ` (${version})` : "" })}\n`);
  io.write(`${message(language, "existingPrompt")}\n`);
  io.write(`  1) ${message(language, "existingRepair")}\n`);
  io.write(`  2) ${message(language, "existingUpdate")}\n`);
  io.write(`  3) ${message(language, "existingUninstall")}\n`);
  io.write(`  4) ${message(language, "existingCancel")}\n`);
  const reply = (await io.ask(`${message(language, "existingChoose")}: `)).toLowerCase();
  return { 1: "repair", 2: "update", 3: "uninstall", 4: "cancel" }[reply] || "repair";
}

function platformShell(platform = process.platform) {
  if (platform === "win32") return "powershell.exe";
  if (platform === "linux" || platform === "darwin") return "bash";
  return null;
}

function commandExists(command) {
  const lookup = process.platform === "win32" ? "where" : "which";
  const result = spawnSync(lookup, [command], { stdio: "ignore" });
  return !result.error && result.status === 0;
}

function preflight(language) {
  const shell = platformShell();
  if (!shell) throw new Error(message(language, "unsupported", { platform: process.platform }));
  if (!commandExists(shell)) {
    throw new Error(message(language, shell === "bash" ? "needShell" : "needPowerShell"));
  }
}

async function install(version, args, language = "en") {
  preflight(language);
  const asset = installerAsset(process.platform, version);
  const base = releaseBase(version);
  const normalizedArgs = setupArgs(args, process.platform, language);
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "trinaxai-installer-"));
  const installerPath = path.join(tempDir, asset);
  try {
    process.stdout.write(`\n${message(language, "downloading", { version })}\n`);
    let installer;
    let manifest;
    try {
      [installer, manifest] = await Promise.all([
        download(`${base}/${asset}`, { language }),
        download(`${base}/SHA256SUMS`, { language }),
      ]);
    } catch (error) {
      console.error(`TrinaxAI: ${message(language, "downloadFailed")} (${error.message})`);
      return 1;
    }
    const expected = checksumFor(manifest.toString("utf8"), asset);
    const actual = crypto.createHash("sha256").update(installer).digest("hex");
    if (actual !== expected) {
      console.error(`TrinaxAI: ${message(language, "checksumFailed")}`);
      return 1;
    }
    process.stdout.write(`${message(language, "verified")}\n`);
    fs.writeFileSync(installerPath, installer, { mode: 0o700 });

    const environment = { ...process.env, TRINAXAI_RELEASE_VERSION: version, TRINAXAI_LANG: language };
    const command = platformShell();
    const commandArgs = process.platform === "win32"
      ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", installerPath, ...normalizedArgs]
      : [installerPath, ...normalizedArgs];
    const result = spawnSync(command, commandArgs, { env: environment, stdio: "inherit" });
    if (result.error) throw result.error;
    const status = result.status ?? 1;
    if (status !== 0) console.error(`\nTrinaxAI: ${message(language, "setupFailed", { code: status })}`);
    return status;
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function languageFromArgs(args) {
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--language" || argument === "--lang") return { present: true, value: args[index + 1] };
    const match = argument.match(/^--(?:language|lang)=(.*)$/);
    if (match) return { present: true, value: match[1] };
  }
  return { present: false, value: null };
}

async function setup(args, deps = {}) {
  const interactive = deps.interactive ?? isInteractive(args);
  const requested = languageFromArgs(args);
  let language = detectLanguage();
  if (requested.present) {
    const chosen = normalizeLanguage(requested.value);
    if (!chosen) throw new Error(message(language, "invalidLanguage", { value: requested.value || "" }));
    language = chosen;
  } else if (interactive) {
    language = await chooseLanguage(language);
  }
  const forwarded = requested.present || !interactive ? args : [...args, "--language", language];

  if (interactive) printWelcome(language);
  const root = findInstallation();
  if (root && interactive && !args.includes("--dry-run")) {
    const action = await chooseExistingAction(language, root);
    if (action === "cancel") {
      console.log(message(language, "cancelled"));
      return 0;
    }
    if (action === "update" || action === "uninstall") {
      const status = runInstalled([action], root);
      if (action === "uninstall" && status === 0 && !isInstallation(root)) {
        console.log(message(language, "uninstallLauncher"));
      }
      return status;
    }
  }
  const status = await install(PACKAGE_VERSION, forwarded, language);
  if (status === 0 && !args.includes("--dry-run")) console.log(`\n${message(language, "setupDone")}`);
  return status;
}

async function main(args = process.argv.slice(2)) {
  const language = detectLanguage();
  if (args[0] === "--help" || args[0] === "-h" || (args[0] === "setup" && ["--help", "-h"].includes(args[1]))) {
    process.stdout.write(`TrinaxAI ${PACKAGE_VERSION}\n\n${message(language, "help")}`);
    return 0;
  }
  if (args[0] === "--version") {
    const root = findInstallation();
    const installed = root && installedVersion(root);
    if (installed && installed !== PACKAGE_VERSION) {
      console.log(message(language, "versionLine", { launcher: PACKAGE_VERSION, installed }));
      console.log(message(language, "updateHint", { launcher: PACKAGE_VERSION, installed }));
    } else {
      console.log(PACKAGE_VERSION);
    }
    return 0;
  }
  if (args[0] === "setup") {
    return setup(args.slice(1));
  }

  const root = findInstallation();
  if (!root && args.length === 0 && isInteractive(args)) {
    // A bare "trinaxai" right after "npm install -g": offer the setup instead of an error.
    const reply = (await ask(`${message(language, "installNow")} `)).toLowerCase();
    if (reply === "" || /^[ys]/.test(reply)) return setup([]);
    console.log(message(language, "cancelled"));
    return 0;
  }
  if (!root) {
    console.error(message(language, args[0] === "uninstall" ? "notInstalledUninstall" : "notInstalled"));
    return 1;
  }
  const status = runInstalled(args, root);
  if (args[0] === "uninstall" && status === 0 && !isInstallation(root)) {
    console.log(message(language, "uninstallLauncher"));
  }
  return status;
}

if (require.main === module) {
  main().then((status) => {
    process.exitCode = status;
  }).catch((error) => {
    console.error(`TrinaxAI: ${error.message}`);
    process.exitCode = 1;
  });
}

module.exports = {
  checksumFor,
  chooseExistingAction,
  chooseLanguage,
  detectLanguage,
  download,
  installedVersion,
  installerAsset,
  isInteractive,
  languageFromArgs,
  message,
  normalizeLanguage,
  releaseBase,
  setupArgs,
};
