"use strict";

const assert = require("node:assert/strict");
const {
  checksumFor,
  detectLanguage,
  installerAsset,
  message,
  releaseBase,
  setupArgs,
} = require("../bin/trinaxai.js");

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

assert.equal(detectLanguage([], { LANG: "es_MX.UTF-8" }), "es");
assert.equal(detectLanguage([], { LANG: "en_US.UTF-8" }), "en");
assert.equal(detectLanguage([], {}), "en");
assert.equal(detectLanguage(["--language", "es"], { LANG: "en_US.UTF-8" }), "es");
assert.equal(detectLanguage(["--lang=en"], { TRINAXAI_LANG: "es" }), "en");
assert.equal(detectLanguage([], { TRINAXAI_LANG: "es", LANG: "en_US.UTF-8" }), "es");
assert.equal(message("notInstalled"), "TrinaxAI is not installed. Run: trinaxai setup");
assert.equal(message("invalidVersion", "x"), "Invalid TrinaxAI version: x");
assert.equal(message("help", "1.3.0").startsWith("TrinaxAI 1.3.0"), true);

console.log("npm CLI checks passed");
