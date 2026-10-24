"""Validation, risk classification and hardened invocation for the Agent's ``git`` tool.

The Agent's terminal runs in a networkless sandbox, so ``git push`` and
``git pull`` cannot work there. The ``git`` tool runs git on the host instead,
with the user's own configuration and credentials, which makes it much more
sensitive than a sandboxed command. This module keeps that safe by construction:

* only known subcommands run, so a git alias (configured outside the Agent's
  reach, but arbitrary code) can never be invoked by name;
* global options (``-c``, ``-C``, ``--git-dir`` ...) are refused, and so are the
  subcommand options that run programs or read/write outside the repository
  (``--exec``, ``--upload-pack``, ``--output``, ``--no-index`` ...);
* every call is classified as ``read`` (no side effects), ``local`` (changes the
  repository) or ``network`` (talks to a remote with the user's credentials) so
  the approval layer can treat them differently;
* hooks are switched off, git never prompts or opens an editor, and only a short
  list of remote protocols is allowed, so approving a command approves exactly
  what its text says.

Nothing here runs git; :mod:`trinaxai_agent.tools` does that.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import Any

READ = "read"
LOCAL = "local"
NETWORK = "network"

#: Hooks live in the repository or can be redirected into the (Agent-writable)
#: workspace with ``core.hooksPath``; they run outside the sandbox with the
#: user's credentials. They stay off unless the user opts in explicitly.
HOOKS_ENV = "TRINAXAI_AGENT_GIT_HOOKS"

_READ_COMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "blame",
        "ls-files",
        "ls-tree",
        "rev-parse",
        "rev-list",
        "describe",
        "shortlog",
        "show-ref",
        "grep",
        "merge-base",
    }
)
_LOCAL_COMMANDS = frozenset(
    {
        "add",
        "rm",
        "mv",
        "restore",
        "reset",
        "commit",
        "switch",
        "checkout",
        "branch",
        "tag",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "stash",
        "remote",
        "clean",
        "init",
    }
)
_NETWORK_COMMANDS = frozenset({"push", "pull", "fetch"})
GIT_COMMANDS = _READ_COMMANDS | _LOCAL_COMMANDS | _NETWORK_COMMANDS

# Options that run another program, point git at another repository, or read or
# write outside the repository. Matched on the part before ``=``.
_DENIED_OPTIONS = frozenset(
    {
        "--config",
        "--config-env",
        "--git-dir",
        "--work-tree",
        "--exec-path",
        "--namespace",
        "--super-prefix",
        "--upload-pack",
        "--receive-pack",
        "--exec",
        "--output",
        "--ext-diff",
        "--textconv",
        "--open-files-in-pager",
        "--paginate",
        "--separate-git-dir",
        "--recurse-submodules",
        "--recursive",
        "--no-index",
        "--contents",
        "--run",
    }
)
# Long options that read a file: its value must stay inside the workspace.
_FILE_LONG_OPTIONS: dict[str, tuple[str, ...]] = {
    "commit": ("--file", "--template"),
    "tag": ("--file",),
    "merge": ("--file",),
}
# Short options per subcommand as (letters that take a value, letters that read a
# file, letters that are refused). A value letter ends a bundle such as ``-am msg``:
# the rest of the token (or the next argument) is its value.
_SHORT_OPTIONS: dict[str, tuple[str, str, str]] = {
    "commit": ("mCcFtu", "Ft", ""),
    "tag": ("mFu", "F", ""),
    "merge": ("mFsXS", "F", ""),
    "grep": ("efABCmO", "f", "O"),
    "rebase": ("sXSCxr", "", "x"),
}

_URL_SCHEMES = frozenset({"https", "ssh", "git", "file"})
_HELPER_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*::")
_ALLOWED_PROTOCOLS = "https:ssh:git:file"
_MAX_ARGS = 200
_MAX_ARG_CHARS = 8_192

_BRANCH_READ_FLAGS = frozenset(
    {"-a", "--all", "-r", "--remotes", "-l", "--list", "-v", "-vv", "--verbose", "--show-current", "--no-color"}
)
_BRANCH_READ_PREFIXES = (
    "--sort=",
    "--format=",
    "--merged",
    "--no-merged",
    "--contains",
    "--no-contains",
    "--points-at",
)
_TAG_READ_FIRST = frozenset(
    {
        "-l",
        "--list",
        "-n",
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
        "--sort",
        "-v",
        "--verify",
    }
)
_TAG_WRITE_FLAGS = frozenset(
    {
        "-d",
        "--delete",
        "-f",
        "--force",
        "-a",
        "--annotate",
        "-s",
        "--sign",
        "-m",
        "--message",
        "-F",
        "--file",
        "-u",
        "--local-user",
        "-e",
        "--edit",
    }
)
_REMOTE_URL_COMMANDS = frozenset({"add", "set-url"})
_REMOTE_LOCAL_COMMANDS = frozenset({"remove", "rm", "rename"})
_REMOTE_NETWORK_COMMANDS = frozenset({"update", "prune", "show"})


class GitUsageError(ValueError):
    """The requested git invocation is not allowed (or not understandable)."""


@dataclass(frozen=True)
class GitCommand:
    """A validated git invocation."""

    args: tuple[str, ...]
    kind: str
    files: tuple[str, ...] = ()

    @property
    def subcommand(self) -> str:
        return self.args[0]


def parse_git_args(raw: Any) -> tuple[str, ...]:
    """Turn the tool argument into an argument vector (no shell is ever involved)."""
    if raw is None:
        raise GitUsageError("no git arguments were given; pass the subcommand and its options")
    if isinstance(raw, str):
        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            raise GitUsageError(f"cannot read the git arguments: {exc}") from exc
    elif isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, (str, int, float)):
                raise GitUsageError("every git argument must be text")
            parts.append(str(item))
    else:
        raise GitUsageError("git arguments must be a list of strings")
    if parts and parts[0] == "git":
        parts = parts[1:]
    if not parts:
        raise GitUsageError("no git arguments were given; pass the subcommand and its options")
    if len(parts) > _MAX_ARGS or any(len(part) > _MAX_ARG_CHARS or "\x00" in part for part in parts):
        raise GitUsageError("git arguments are too long or contain invalid characters")
    return tuple(parts)


def _check_url(value: str) -> None:
    if _HELPER_URL.match(value):
        raise GitUsageError("remote-helper URLs (ext::, fd::, ...) are not allowed")
    if "://" in value and value.split("://", 1)[0].lower() not in _URL_SCHEMES:
        raise GitUsageError("only https, ssh, git and file remotes are allowed")


def _split_option(argument: str) -> str:
    return argument.split("=", 1)[0]


def _file_operands(subcommand: str, options: list[str]) -> list[str]:
    """Files git would read for this call; also refuses short options that run programs."""
    files: list[str] = []
    long_options = _FILE_LONG_OPTIONS.get(subcommand, ())
    value_letters, file_letters, denied_letters = _SHORT_OPTIONS.get(subcommand, ("", "", ""))
    skip_next = False
    for index, token in enumerate(options):
        if skip_next:  # the value of the previous short option, not an option itself
            skip_next = False
            continue
        following = options[index + 1] if index + 1 < len(options) else None
        if token.startswith("--"):
            name = _split_option(token)
            if len(name) > 3 and any(option.startswith(name) for option in long_options):
                value = token.split("=", 1)[1] if "=" in token else following
                if value is not None:
                    files.append(value)
        elif token.startswith("-") and len(token) > 1:
            for position, letter in enumerate(token[1:], start=1):
                if letter in denied_letters:
                    raise GitUsageError(f"the option -{letter} is not allowed")
                if letter in file_letters:
                    value = token[position + 1 :] or following
                    if value is not None:
                        files.append(value)
                    skip_next = position == len(token) - 1
                    break
                if letter in value_letters:
                    skip_next = position == len(token) - 1
                    break
    return files


def _branch_kind(rest: tuple[str, ...]) -> str:
    safe = all(a in _BRANCH_READ_FLAGS or a.startswith(_BRANCH_READ_PREFIXES) for a in rest)
    return READ if safe else LOCAL


def _tag_kind(rest: tuple[str, ...]) -> str:
    if not rest:
        return READ
    if rest[0] in _TAG_READ_FIRST and not any(a in _TAG_WRITE_FLAGS for a in rest):
        return READ
    return LOCAL


def _remote_kind(rest: tuple[str, ...]) -> str:
    if not rest or rest in {("-v",), ("--verbose",)}:
        return READ
    action, operands = rest[0], rest[1:]
    if action == "get-url":
        return READ
    if action in _REMOTE_URL_COMMANDS:
        if len(operands) != 2 or any(a.startswith("-") for a in operands):
            raise GitUsageError(f"use: remote {action} <name> <url>")
        _check_url(operands[1])
        return LOCAL
    if action in _REMOTE_LOCAL_COMMANDS:
        return LOCAL
    if action in _REMOTE_NETWORK_COMMANDS:
        return NETWORK
    raise GitUsageError("this remote command is not supported")


def _stash_kind(rest: tuple[str, ...]) -> str:
    return READ if rest and rest[0] in {"list", "show"} else LOCAL


def classify_git(raw: Any) -> GitCommand:
    """Validate a git invocation and say how risky it is, or raise :class:`GitUsageError`."""
    args = parse_git_args(raw)
    subcommand, rest = args[0], args[1:]
    if subcommand.startswith("-"):
        raise GitUsageError("put the git subcommand first; global options such as -c or -C are not allowed")
    if subcommand not in GIT_COMMANDS:
        allowed = ", ".join(sorted(GIT_COMMANDS))
        raise GitUsageError(f"the git subcommand '{subcommand}' is not available to the Agent (allowed: {allowed})")

    before_separator = list(rest[: rest.index("--")]) if "--" in rest else list(rest)
    if subcommand in _NETWORK_COMMANDS:
        # Only operands that name a remote matter; commit messages may contain any URL.
        for argument in rest:
            if not argument.startswith("-"):
                _check_url(argument)
    denied = _DENIED_OPTIONS if subcommand == "commit" else _DENIED_OPTIONS | {"--template"}
    for argument in before_separator:
        if argument.startswith("--") and len(argument) > 2:
            name = _split_option(argument)
            # git accepts any unambiguous abbreviation of a long option (--ext-dif, --upload-p=...).
            if any(option.startswith(name) for option in denied):
                raise GitUsageError(f"the option {name} is not allowed")
    files = _file_operands(subcommand, before_separator)

    if subcommand in _READ_COMMANDS:
        kind = READ
    elif subcommand in _NETWORK_COMMANDS:
        kind = NETWORK
    elif subcommand == "branch":
        kind = _branch_kind(rest)
    elif subcommand == "tag":
        kind = _tag_kind(rest)
    elif subcommand == "remote":
        kind = _remote_kind(rest)
    elif subcommand == "stash":
        kind = _stash_kind(rest)
    else:
        kind = LOCAL
    return GitCommand(args=args, kind=kind, files=tuple(files))


def git_input(arguments: dict[str, Any]) -> Any:
    """The git argument list from a tool-call argument dict (``args``, or ``command``)."""
    value = arguments.get("args")
    return value if value is not None else arguments.get("command")


def git_display(arguments: dict[str, Any]) -> str:
    """The command a tool call would run, as text for a prompt or a transcript line."""
    try:
        parts = parse_git_args(git_input(arguments))
    except GitUsageError:
        return "git " + str(git_input(arguments))
    return "git " + " ".join(shlex.quote(part) for part in parts)


def git_risk(raw: Any) -> str:
    """Risk of a call for approval policies; an unusable call is treated as ``local``.

    Invalid calls are refused when the tool runs, so a policy only has to avoid
    auto-approving them.
    """
    try:
        return classify_git(raw).kind
    except GitUsageError:
        return LOCAL


def hooks_enabled(environ: dict[str, str] | None = None) -> bool:
    value = (environ if environ is not None else os.environ).get(HOOKS_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def git_argv(executable: str, args: tuple[str, ...], *, hooks_dir: str, hooks: bool = False) -> list[str]:
    """Argument vector for running ``args`` with the safety configuration applied."""
    argv = [executable, "--no-pager"]
    if not hooks:
        argv += ["-c", f"core.hooksPath={hooks_dir}"]
    argv += [
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.editor=true",
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "protocol.fd.allow=never",
    ]
    return [*argv, *args]


# GIT_* variables the user may legitimately set for their own credentials/SSH.
_KEPT_GIT_ENV = frozenset(
    {"GIT_SSH", "GIT_SSH_COMMAND", "GIT_ASKPASS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_SSL_CAINFO"}
)


def git_env(base: dict[str, str]) -> dict[str, str]:
    """Environment for a git run: no stray ``GIT_*`` redirection, never interactive."""
    env = {k: v for k, v in base.items() if not k.upper().startswith("GIT_") or k.upper() in _KEPT_GIT_ENV}
    # Error hints match git's English messages, whatever language the user's system speaks.
    env.pop("LANGUAGE", None)
    env.pop("LC_ALL", None)
    env.update(
        {
            "LC_MESSAGES": "C",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "GIT_EDITOR": "true",
            "GIT_SEQUENCE_EDITOR": "true",
            "GIT_MERGE_AUTOEDIT": "no",
            "GIT_ALLOW_PROTOCOL": _ALLOWED_PROTOCOLS,
        }
    )
    return env


__all__ = [
    "GIT_COMMANDS",
    "HOOKS_ENV",
    "LOCAL",
    "NETWORK",
    "READ",
    "GitCommand",
    "GitUsageError",
    "classify_git",
    "git_argv",
    "git_env",
    "git_display",
    "git_input",
    "git_risk",
    "hooks_enabled",
    "parse_git_args",
]
