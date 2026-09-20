"use strict";

const assert = require("node:assert/strict");
const {
  checksumFor,
  installerAsset,
  releaseBase,
  setupArgs,
} = require("../bin/trinaxai.js");

assert.equal(installerAsset("linux", "1.2.6"), "TrinaxAI-1.2.6-installer.sh");
assert.equal(installerAsset("win32", "1.2.6"), "TrinaxAI-1.2.6-installer.ps1");
assert.equal(
  checksumFor(`${"a".repeat(64)}  TrinaxAI-1.2.6-installer.sh\n`, "TrinaxAI-1.2.6-installer.sh"),
  "a".repeat(64),
);
assert.deepEqual(setupArgs(["--no-models", "--profile", "16gb"], "linux"), ["--no-models", "--profile", "16gb"]);
assert.deepEqual(setupArgs(["--no-models", "--profile", "16gb"], "win32"), ["-NoModels", "-Profile", "16gb"]);
assert.deepEqual(setupArgs(["--profile=16gb"], "linux"), ["--profile", "16gb"]);
assert.equal(releaseBase("1.2.6"), "https://github.com/TrinaxCode/TrinaxAI/releases/download/v1.2.6");

console.log("npm CLI checks passed");
