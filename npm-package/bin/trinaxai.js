#!/usr/bin/env node

"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const https = require("node:https");

const PACKAGE_VERSION = require("../package.json").version;
const RELEASE_REPOSITORY = "TrinaxCode/TrinaxAI";
const RELEASE_HOST = "https://github.com";
const MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024;

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

function download(url, redirectCount = 0) {
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
        download(new URL(response.headers.location, target).toString(), redirectCount + 1)
          .then(resolve, reject);
        return;
      }
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`Download failed with HTTP ${response.statusCode}`));
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

function setupArgs(args, platform = process.platform) {
  const windows = platform === "win32";
  const result = [];
  const flags = new Map([
    ["--non-interactive", windows ? "-NonInteractive" : "--non-interactive"],
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
        throw new Error(`${argument} requires a value`);
      }
      result.push(values.get(argument), value);
      index += 1;
      continue;
    }
    const equalsIndex = argument.indexOf("=");
    if (equalsIndex > 0 && values.has(argument.slice(0, equalsIndex))) {
      const option = argument.slice(0, equalsIndex);
      const value = argument.slice(equalsIndex + 1);
      if (!value) throw new Error(`${option} requires a value`);
      result.push(values.get(option), value);
      continue;
    }
    if (["--help", "-h"].includes(argument)) {
      result.push(windows ? "-?" : argument);
      continue;
    }
    throw new Error(`Unknown setup option: ${argument}`);
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

async function install(version, args) {
  const asset = installerAsset(process.platform, version);
  const base = releaseBase(version);
  const normalizedArgs = setupArgs(args, process.platform);
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "trinaxai-installer-"));
  const installerPath = path.join(tempDir, asset);
  try {
    process.stdout.write(`Downloading TrinaxAI ${version} installer...\n`);
    const [installer, manifest] = await Promise.all([
      download(`${base}/${asset}`),
      download(`${base}/SHA256SUMS`),
    ]);
    const expected = checksumFor(manifest.toString("utf8"), asset);
    const actual = crypto.createHash("sha256").update(installer).digest("hex");
    if (actual !== expected) throw new Error("Installer SHA-256 verification failed");
    fs.writeFileSync(installerPath, installer, { mode: 0o700 });

    const environment = { ...process.env, TRINAXAI_RELEASE_VERSION: version };
    const command = process.platform === "win32" ? "powershell.exe" : "bash";
    const commandArgs = process.platform === "win32"
      ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", installerPath, ...normalizedArgs]
      : [installerPath, ...normalizedArgs];
    const result = spawnSync(command, commandArgs, { env: environment, stdio: "inherit" });
    if (result.error) throw result.error;
    return result.status ?? 1;
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function printHelp() {
  console.log(`TrinaxAI ${PACKAGE_VERSION}

Usage:
  trinaxai setup [options]   Install this release
  trinaxai <command>          Run the installed TrinaxAI CLI

Setup options:
  --no-models, --no-start, --no-autostart, --no-auto-update
  --non-interactive, --dry-run, --profile PROFILE, --install-dir PATH
`);
}

async function main(args = process.argv.slice(2)) {
  if (args[0] === "--help" || args[0] === "-h") {
    printHelp();
    return 0;
  }
  if (args[0] === "--version") {
    console.log(PACKAGE_VERSION);
    return 0;
  }
  if (args[0] === "setup" && ["--help", "-h"].includes(args[1])) {
    printHelp();
    return 0;
  }
  if (args[0] === "setup") {
    return install(PACKAGE_VERSION, args.slice(1));
  }

  const root = findInstallation();
  if (!root) {
    console.error("TrinaxAI is not installed. Run: trinaxai setup");
    return 1;
  }
  return runInstalled(args, root);
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
  installerAsset,
  releaseBase,
  setupArgs,
};
