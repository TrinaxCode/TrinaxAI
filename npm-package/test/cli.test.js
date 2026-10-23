"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
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
} = require("../bin/trinaxai.js");

const BIN = path.join(__dirname, "..", "bin", "trinaxai.js");

function scripted(...answers) {
  const written = [];
  return {
    written,
    ask: async () => answers.shift() ?? "",
    write: (text) => written.push(text),
  };
}

async function main() {
  assert.equal(installerAsset("linux", "1.3.0"), "TrinaxAI-1.3.0-installer.sh");
  assert.equal(installerAsset("win32", "1.3.0"), "TrinaxAI-1.3.0-installer.ps1");
  assert.equal(
    checksumFor(`${"a".repeat(64)}  TrinaxAI-1.3.0-installer.sh\n`, "TrinaxAI-1.3.0-installer.sh"),
    "a".repeat(64),
  );
  assert.deepEqual(setupArgs(["--no-models", "--profile", "16gb"], "linux"), ["--no-models", "--profile", "16gb"]);
  assert.deepEqual(setupArgs(["--no-models", "--profile", "16gb"], "win32"), ["-NoModels", "-Profile", "16gb"]);
  assert.deepEqual(setupArgs(["--profile=16gb"], "linux"), ["--profile", "16gb"]);
  assert.equal(releaseBase("1.3.0"), "https://github.com/TrinaxCode/TrinaxAI/releases/download/v1.3.0");

  // The installer accepts the same "yes to everything" spellings on every platform.
  assert.deepEqual(setupArgs(["--yes"], "linux"), ["--non-interactive"]);
  assert.deepEqual(setupArgs(["-y"], "win32"), ["-NonInteractive"]);
  assert.deepEqual(setupArgs(["--interactive"], "win32"), ["-Interactive"]);
  assert.deepEqual(setupArgs(["--language", "es"], "win32"), ["-Language", "es"]);
  assert.deepEqual(setupArgs(["--lang=es"], "linux"), ["--language", "es"]);
  assert.throws(() => setupArgs(["--profile"], "linux", "es"), /--profile requiere un valor/);
  assert.throws(() => setupArgs(["--bogus"], "linux", "en"), /Unknown setup option: --bogus/);
  assert.throws(() => setupArgs(["--bogus"], "linux", "es"), /Opción de instalación desconocida: --bogus/);

  // Language detection and normalization.
  assert.equal(normalizeLanguage("es_PE.UTF-8"), "es");
  assert.equal(normalizeLanguage("es"), "es");
  assert.equal(normalizeLanguage("en-US"), "en");
  assert.equal(normalizeLanguage("english"), null);
  assert.equal(normalizeLanguage("fr_FR"), null);
  assert.equal(detectLanguage({ TRINAXAI_LANG: "es" }), "es");
  assert.equal(detectLanguage({ LANG: "es_ES.UTF-8" }), "es");
  assert.equal(detectLanguage({ LC_ALL: "en_US.UTF-8", LANG: "es_ES.UTF-8" }), "en");
  assert.deepEqual(languageFromArgs(["--no-models", "--language=es"]), { present: true, value: "es" });
  assert.deepEqual(languageFromArgs(["--lang", "en"]), { present: true, value: "en" });
  assert.deepEqual(languageFromArgs(["--no-models"]), { present: false, value: null });

  assert.equal(message("es", "cancelled"), "Cancelado. No se cambió nada.");
  assert.equal(message("en", "retrying", { reason: "x", attempt: 2, total: 3 }), "Download failed (x); retrying (2/3)...");
  assert.equal(message("fr", "cancelled"), message("en", "cancelled"));
  assert.equal(message("es", "welcomeSteps").length, message("en", "welcomeSteps").length);

  // Interactivity: scripts and CI never get prompted, a real terminal does.
  const tty = { isTTY: true };
  const pipe = { isTTY: false };
  assert.equal(isInteractive([], {}, tty, tty), true);
  assert.equal(isInteractive([], {}, pipe, tty), false);
  assert.equal(isInteractive([], { CI: "true" }, tty, tty), false);
  assert.equal(isInteractive(["--yes"], {}, tty, tty), false);
  assert.equal(isInteractive(["--dry-run"], {}, tty, tty), false);
  assert.equal(isInteractive(["--non-interactive"], {}, tty, tty), false);
  assert.equal(isInteractive(["--interactive"], { CI: "true" }, pipe, pipe), true);

  // Language question.
  assert.equal(await chooseLanguage("en", scripted("2")), "es");
  assert.equal(await chooseLanguage("en", scripted("es")), "es");
  assert.equal(await chooseLanguage("es", scripted("1")), "en");
  assert.equal(await chooseLanguage("es", scripted("")), "es");
  assert.equal(await chooseLanguage("en", scripted("")), "en");
  assert.equal(await chooseLanguage("en", scripted("zzz")), "en");

  // Existing installation menu.
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "trinaxai-npm-test-"));
  try {
    fs.writeFileSync(path.join(root, "pyproject.toml"), '[project]\nname = "trinaxai"\nversion = "1.2.9"\n');
    assert.equal(installedVersion(root), "1.2.9");
    assert.equal(installedVersion(path.join(root, "missing")), null);
    assert.equal(await chooseExistingAction("en", root, scripted("1")), "repair");
    assert.equal(await chooseExistingAction("en", root, scripted("2")), "update");
    assert.equal(await chooseExistingAction("en", root, scripted("3")), "uninstall");
    assert.equal(await chooseExistingAction("en", root, scripted("4")), "cancel");
    assert.equal(await chooseExistingAction("en", root, scripted("")), "repair");
    const io = scripted("4");
    await chooseExistingAction("es", root, io);
    assert.match(io.written.join(""), /ya está instalado en .*\(1\.2\.9\)/);

    // The launcher answers in the user's language and never touches the machine
    // when nothing is installed.
    const env = { ...process.env, HOME: root, XDG_DATA_HOME: path.join(root, "data"), LOCALAPPDATA: root, LANG: "es_ES.UTF-8" };
    delete env.TRINAXAI_HOME;
    delete env.TRINAXAI_LANG;
    delete env.LC_ALL;
    delete env.LC_MESSAGES;
    const missing = spawnSync(process.execPath, [BIN, "doctor"], { env, encoding: "utf8" });
    assert.equal(missing.status, 1);
    assert.match(missing.stderr, /TrinaxAI todavía no está instalado\. Ejecuta: trinaxai setup/);
    const uninstall = spawnSync(process.execPath, [BIN, "uninstall"], { env, encoding: "utf8" });
    assert.equal(uninstall.status, 1);
    assert.match(uninstall.stderr, /No hay nada que desinstalar/);
    const english = spawnSync(process.execPath, [BIN, "doctor"], { env: { ...env, LANG: "en_US.UTF-8" }, encoding: "utf8" });
    assert.match(english.stderr, /TrinaxAI is not installed yet\. Run: trinaxai setup/);
    const help = spawnSync(process.execPath, [BIN, "setup", "--help"], { env, encoding: "utf8" });
    assert.equal(help.status, 0);
    assert.match(help.stdout, /Opciones de instalación/);
    const badLanguage = spawnSync(process.execPath, [BIN, "setup", "--language", "fr", "--dry-run"], { env, encoding: "utf8" });
    assert.equal(badLanguage.status, 1);
    assert.match(badLanguage.stderr, /Idioma no compatible: fr/);
    const version = spawnSync(process.execPath, [BIN, "--version"], { env, encoding: "utf8" });
    assert.match(version.stdout.trim(), /^\d+\.\d+\.\d+$/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }

  // Downloads retry transient failures, say so in the user's language, and
  // give up with the original error instead of hanging.
  const logs = [];
  await assert.rejects(
    download("https://127.0.0.1:9/installer", { language: "es", attempts: 2, retryDelay: 1, log: (line) => logs.push(line) }),
    (error) => error instanceof Error,
  );
  assert.ok(logs.some((line) => line.includes("reintentando (2/2)")), logs.join("\n"));
  await assert.rejects(download("http://example.invalid/installer", { attempts: 1, log: () => {} }), /HTTPS/);

  console.log("npm CLI checks passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
