"""Sandboxed tools for the TrinaxAI agentic engine.

Every tool operates relative to a ``workspace_root`` and refuses to touch
anything outside it — the sandbox is enforced by :func:`_resolve_in_workspace`,
which resolves symlinks and rejects paths that escape the root (``..``, absolute
paths pointing elsewhere, symlinks out of the tree).

A tool is described by a :class:`Tool` dataclass:

* ``name`` / ``description`` / ``parameters`` build the JSON schema handed to
  Ollama's ``tools`` field so the model can call it natively.
* ``dangerous`` marks side-effecting tools (write / edit / shell). The engine
  asks for confirmation before running those; read-only tools run freely.
* ``handler`` receives ``(workspace_root, **kwargs)`` and returns a string that
  is fed back to the model as the tool result.

Handlers never raise for expected failures (missing file, bad path, command
error). They return a short, human-readable error string instead so the model
can recover on the next turn.
"""

from __future__ import annotations

import ast
import fnmatch
import importlib
import inspect
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from trinaxai_cli.agent.extract import extract_document_text, is_document

# Cap tool output so a huge file or noisy command cannot blow the model's
# context window. Handlers truncate and append a clear marker when they hit it.
MAX_OUTPUT_CHARS = 8_000
MAX_FILE_BYTES = 2_000_000
RUN_TIMEOUT_SECONDS = 120
_UNSANDBOXED_COMMAND_ENV = "TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS"
MAX_ROOT_ENTRIES = 200
MAX_LIST_ENTRIES = 200
MAX_GLOB_MATCHES = 200
MAX_GREP_MATCHES = 100
MAX_GREP_FILES = 2_000
MAX_RECURSIVE_DEPTH = 8
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}

# Importing arbitrary modules merely to inspect them can itself have side
# effects. Keep automatic API evidence to common, side-effect-free stdlib
# modules. This list can grow deliberately as review coverage expands.
_SAFE_STDLIB_INTROSPECTION = {
    "collections",
    "csv",
    "dataclasses",
    "datetime",
    "functools",
    "itertools",
    "json",
    "math",
    "pathlib",
    "random",
    "re",
    "statistics",
    "string",
    "turtle",
    "typing",
}


class SandboxError(ValueError):
    """Raised when a tool argument points outside the workspace root."""


def _resolve_in_workspace(workspace_root: Path, rel: str) -> Path:
    """Resolve ``rel`` against the workspace and ensure it stays inside it.

    Accepts paths relative to the root or absolute paths that already live under
    it. Rejects everything else (``..`` escapes, symlinks out of the tree,
    absolute paths elsewhere) with :class:`SandboxError`.
    """
    root = workspace_root.resolve()
    raw = (rel or "").strip()
    if not raw:
        raise SandboxError("empty path")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    # ``resolve`` collapses ``..`` and follows symlinks so we compare real paths.
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SandboxError(f"path '{rel}' is outside the workspace root ({root}); access denied")
    return resolved


def _rel(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve())) or "."
    except ValueError:
        return str(path)


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more chars]"


def _workspace_scope_error(workspace_root: Path) -> str | None:
    """Reject an accidentally broad workspace before recursive inspection."""
    try:
        entries = [child for child in workspace_root.iterdir() if child.name not in _SKIP_DIRS]
    except OSError as exc:
        return f"error: cannot inspect workspace root: {exc}"
    if len(entries) > MAX_ROOT_ENTRIES:
        return (
            f"error: workspace root is too broad ({len(entries)} top-level entries). "
            "Pick a project folder instead of a general Documents/home directory."
        )
    return None


def _depth(path: Path, root: Path) -> int:
    return len(path.relative_to(root).parts)


def _compact_doc(obj: Any, limit: int = 700) -> str:
    doc = " ".join((inspect.getdoc(obj) or "").split())
    return doc if len(doc) <= limit else doc[: limit - 1].rstrip() + "…"


def _python_stdlib_facts(source: str) -> list[str]:
    """Return verified call signatures/docs without executing user code.

    The AST is used to infer simple bindings such as ``t = turtle.Turtle()``.
    We then inspect only allowlisted standard-library objects. This gives the
    model concrete API semantics for claims that source text alone cannot prove
    (for example whether ``goto`` accepts a tuple or draws while moving).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    modules: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".", 1)[0]
                if top_level in _SAFE_STDLIB_INTROSPECTION:
                    modules[alias.asname or top_level] = top_level

    loaded: dict[str, Any] = {}

    def load(module_name: str) -> Any | None:
        if module_name not in loaded:
            try:
                loaded[module_name] = importlib.import_module(module_name)
            except Exception:  # noqa: BLE001 - metadata is best-effort
                loaded[module_name] = None
        return loaded[module_name]

    instances: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
        ):
            continue
        module_name = modules.get(value.func.value.id)
        module = load(module_name) if module_name else None
        class_name = value.func.attr
        if module is None or not inspect.isclass(getattr(module, class_name, None)):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                instances[target.id] = (module_name, class_name)

    facts: list[str] = []
    seen: set[str] = set()
    constructed_modules = {module_name for module_name, _ in instances.values()}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        module_name: str | None = None
        label: str | None = None
        obj: Any = None
        if isinstance(owner, ast.Name) and owner.id in instances:
            module_name, class_name = instances[owner.id]
            module = load(module_name)
            cls = getattr(module, class_name, None) if module else None
            obj = getattr(cls, node.func.attr, None) if cls else None
            label = f"{module_name}.{class_name}.{node.func.attr}"
        elif isinstance(owner, ast.Name) and owner.id in modules:
            module_name = modules[owner.id]
            # Module-level evidence is most valuable when it belongs to the
            # same API as an inferred instance; skip noisy math/json helpers.
            if module_name not in constructed_modules:
                continue
            module = load(module_name)
            obj = getattr(module, node.func.attr, None) if module else None
            label = f"{module_name}.{node.func.attr}"
        if obj is None or label is None or label in seen:
            continue
        seen.add(label)
        try:
            signature = str(inspect.signature(obj))
        except (TypeError, ValueError):
            signature = "(signature unavailable)"
        call_text = ast.get_source_segment(source, node) or label
        call_text = " ".join(call_text.split())
        doc = _compact_doc(obj)
        fact = f"- line {node.lineno}: {call_text} -> verified {label}{signature}; {doc or 'no local documentation'}"
        facts.append(fact)
        if len(facts) >= 12:
            break
    return facts


# --------------------------------------------------------------------- handlers


def _read_file(workspace_root: Path, path: str, offset: int = 0, limit: int = 0, **_: Any) -> str:
    target = _resolve_in_workspace(workspace_root, path)
    if not target.is_file():
        return f"error: file not found: {path}"
    # Rich documents (PDF, Word, Excel, …) are extracted to text rather than read
    # as raw bytes, so the agent can read the same file types TrinaxAI indexes.
    if is_document(target):
        try:
            text = extract_document_text(target)
        except ImportError as exc:
            return f"error: cannot read {path}: missing parser dependency ({exc})"
        except Exception as exc:  # noqa: BLE001 - report any parse failure to the model
            return f"error: cannot extract text from {path}: {exc}"
        return _truncate(text) or "(no extractable text)"
    try:
        if target.stat().st_size > MAX_FILE_BYTES:
            return f"error: file too large to read ({target.stat().st_size} bytes): {path}"
        source = target.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
    except OSError as exc:
        return f"error: cannot read {path}: {exc}"
    if not offset and not limit and len(source) > 8_000:
        return (
            f"[read_file path={_rel(workspace_root, target)}; partial; lines=0-0/{len(lines)}]\n"
            "File is too long for one reliable tool result. Use grep for exact identifiers "
            "or call read_file again with offset and limit. Do not answer from unread lines."
        )
    start = max(0, int(offset or 0))
    end = start + int(limit) if limit else len(lines)
    selected = lines[start:end]
    numbered = "\n".join(f"{start + i + 1}\t{line}" for i, line in enumerate(selected))
    first_line = start + 1 if selected else 0
    last_line = start + len(selected)
    complete = start == 0 and end >= len(lines)
    scope = "complete" if complete else "partial"
    details = [
        f"read_file path={_rel(workspace_root, target)}",
        scope,
        f"lines={first_line}-{last_line}/{len(lines)}",
    ]
    api_facts: list[str] = []
    # Parsing is safe (the source is never executed) and gives small models a
    # hard fact they cannot replace with a guessed syntax diagnosis. This is
    # especially useful in reviews where valid continuations or constructors
    # are otherwise frequently misreported as errors.
    if target.suffix.lower() == ".py":
        try:
            ast.parse(source, filename=str(target))
        except SyntaxError as exc:
            details.append(f"syntax=invalid at line {exc.lineno}: {exc.msg}")
        else:
            details.append("syntax=valid")
            api_facts = _python_stdlib_facts(source)
    header = "[" + "; ".join(details) + "]"
    footer = f"[end read_file: {scope}]"
    body = numbered or "(empty file)"
    facts_block = ""
    if api_facts:
        facts_block = "\n[verified local stdlib API evidence]\n" + "\n".join(api_facts)
    return _truncate(f"{header}\n{body}{facts_block}\n{footer}")


def _write_file(workspace_root: Path, path: str, content: str = "", **_: Any) -> str:
    target = _resolve_in_workspace(workspace_root, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"error: cannot write {path}: {exc}"
    verb = "overwrote" if existed else "created"
    return f"{verb} {_rel(workspace_root, target)} ({len(content)} chars)"


def _edit_file(workspace_root: Path, path: str, old: str = "", new: str = "", **_: Any) -> str:
    target = _resolve_in_workspace(workspace_root, path)
    if not target.is_file():
        return f"error: file not found: {path}"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"error: cannot read {path}: {exc}"
    if old == "":
        return "error: 'old' must not be empty; use write_file to create a file"
    count = text.count(old)
    if count == 0:
        return f"error: 'old' string not found in {path}; read the file first"
    if count > 1:
        return f"error: 'old' matches {count} times in {path}; add more context to make it unique"
    try:
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
    except OSError as exc:
        return f"error: cannot write {path}: {exc}"
    return f"edited {_rel(workspace_root, target)} (1 replacement)"


def _list_dir(workspace_root: Path, path: str = ".", **_: Any) -> str:
    target = _resolve_in_workspace(workspace_root, path or ".")
    if not target.is_dir():
        return f"error: not a directory: {path}"
    if target == workspace_root:
        scope_error = _workspace_scope_error(workspace_root)
        if scope_error:
            return scope_error
    try:
        children = [child for child in target.iterdir() if child.name not in _SKIP_DIRS]
    except OSError as exc:
        return f"error: cannot list directory: {exc}"
    children.sort(key=lambda p: (p.is_file(), p.name.lower()))
    truncated = len(children) > MAX_LIST_ENTRIES
    entries = [f"{child.name}/" if child.is_dir() else child.name for child in children[:MAX_LIST_ENTRIES]]
    if truncated:
        entries.append(f"... [truncated: {len(children) - MAX_LIST_ENTRIES} more entries]")
    listing = "\n".join(entries) if entries else "(empty directory)"
    return _truncate(listing)


def _glob(workspace_root: Path, pattern: str, **_: Any) -> str:
    root = workspace_root.resolve()
    normalized = (pattern or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
        raise SandboxError(f"glob pattern '{pattern}' is outside the workspace root ({root}); access denied")
    scope_error = _workspace_scope_error(root)
    if scope_error:
        return scope_error
    matches: list[str] = []
    if "**" not in normalized:
        try:
            candidates = root.glob(normalized)
            for full in candidates:
                if full.is_file() and not any(part in _SKIP_DIRS for part in full.relative_to(root).parts):
                    matches.append(str(full.relative_to(root)))
                    if len(matches) > MAX_GLOB_MATCHES:
                        break
        except OSError as exc:
            return f"error: glob failed: {exc}"
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            if _depth(current, root) >= MAX_RECURSIVE_DEPTH:
                dirnames[:] = []
            for name in filenames:
                full = current / name
                rel = str(full.relative_to(root))
                if fnmatch.fnmatch(rel, normalized):
                    matches.append(rel)
                    if len(matches) > MAX_GLOB_MATCHES:
                        break
            if len(matches) > MAX_GLOB_MATCHES:
                break
    if not matches:
        return f"no files match: {pattern}"
    matches.sort()
    truncated = len(matches) > MAX_GLOB_MATCHES
    output = matches[:MAX_GLOB_MATCHES]
    if truncated:
        output.append(f"... [truncated: more than {MAX_GLOB_MATCHES} matches]")
    return _truncate("\n".join(output))


def _grep(workspace_root: Path, pattern: str, path: str = ".", **_: Any) -> str:
    base = _resolve_in_workspace(workspace_root, path or ".")
    skip = {".git", "node_modules", "__pycache__", ".venv"}
    if base == workspace_root:
        scope_error = _workspace_scope_error(workspace_root)
        if scope_error:
            return scope_error
    results: list[str] = []
    files: list[Path] = [base] if base.is_file() else []
    if base.is_dir():
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in skip]
            files.extend(Path(dirpath) / n for n in filenames)
            if len(files) > MAX_GREP_FILES:
                return (
                    f"error: search scope is too broad (more than {MAX_GREP_FILES} files). "
                    "Narrow the path before using grep."
                )
    for file in files:
        try:
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            for lineno, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if pattern in line:
                    results.append(f"{_rel(workspace_root, file)}:{lineno}:{line.strip()[:200]}")
                    if len(results) >= MAX_GREP_MATCHES:
                        break
        except OSError:
            continue
        if len(results) >= MAX_GREP_MATCHES:
            break
    if not results:
        return f"no matches for: {pattern}"
    output = results
    if len(results) >= MAX_GREP_MATCHES:
        output.append(f"... [truncated: reached {MAX_GREP_MATCHES} matches]")
    return _truncate("\n".join(output))


def _is_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _bubblewrap_argv(workspace_root: Path, command: str) -> list[str] | None:
    """Build a networkless Linux sandbox for a shell command.

    The namespace contains only the workspace, a private ``/tmp``/``$HOME`` and
    read-only operating-system runtime directories.  In particular, the host's
    home directories and ``/etc`` are not mounted.  Returning ``None`` means the
    host cannot provide the isolation TrinaxAI promises, so callers must fail
    closed unless the user explicitly opts into the legacy unsafe behaviour.
    """
    if os.name != "posix" or not Path("/proc/self/ns/user").exists():
        return None
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return None

    root = workspace_root.resolve()
    argv = [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
    ]
    # Most modern distributions merge these directories into /usr. Preserve
    # that layout without exposing any additional host path.
    for raw in ("/bin", "/sbin", "/lib", "/lib64"):
        path = Path(raw)
        if path.is_symlink():
            argv.extend(("--symlink", os.readlink(path), raw))
        elif path.exists():
            argv.extend(("--ro-bind", raw, raw))

    path_value = ":".join(
        (
            str(root / ".venv" / "bin"),
            str(root / "node_modules" / ".bin"),
            str(root / "chat-pwa" / "node_modules" / ".bin"),
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
        )
    )
    argv.extend(
        (
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home",
            "--dir",
            "/tmp/trinaxai-home",
            "--bind",
            str(root),
            str(root),
            "--chdir",
            str(root),
            "--setenv",
            "HOME",
            "/tmp/trinaxai-home",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "PATH",
            path_value,
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PIP_NO_INDEX",
            "1",
            "--setenv",
            "npm_config_offline",
            "true",
            "/bin/sh",
            "-lc",
            command,
        )
    )
    return argv


def _run_process(argv: list[str], *, cwd: Path) -> tuple[int, str, str]:
    """Run a command and reliably terminate its complete process group."""
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "text": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(argv, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(argv, RUN_TIMEOUT_SECONDS, output=stdout, stderr=stderr)
    return proc.returncode, stdout or "", stderr or ""


def _run_command(workspace_root: Path, command: str, **_: Any) -> str:
    cmd = (command or "").strip()
    if not cmd:
        return "error: empty command"

    root = workspace_root.resolve()
    argv = _bubblewrap_argv(root, cmd)
    sandboxed = argv is not None
    if argv is None:
        if not _is_enabled(_UNSANDBOXED_COMMAND_ENV):
            return (
                "error: terminal execution is disabled because this host has no supported "
                "sandbox. Install bubblewrap on Linux, or explicitly set "
                f"{_UNSANDBOXED_COMMAND_ENV}=1 to accept full user-level host access."
            )
        # Compatibility escape hatch. It is intentionally explicit and never
        # enabled by the PWA/API. Avoid ``shell=True`` even here so process-tree
        # cleanup remains reliable.
        shell = os.environ.get("SHELL") or ("cmd.exe" if os.name == "nt" else "/bin/sh")
        flag = "/c" if os.name == "nt" else "-lc"
        argv = [shell, flag, cmd]
    try:
        returncode, stdout, stderr = _run_process(argv, cwd=root)
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {RUN_TIMEOUT_SECONDS}s: {cmd}"
    except OSError as exc:
        return f"error: cannot run command: {exc}"
    out = stdout + (("\n[stderr]\n" + stderr) if stderr else "")
    status = f"[exit {returncode}; {'sandboxed, network=off' if sandboxed else 'UNSANDBOXED opt-in'}]"
    return _truncate(f"{status}\n{out}".strip()) or status


# ------------------------------------------------------------------ tool table


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]
    dangerous: bool

    def schema(self) -> dict[str, Any]:
        """Return the Ollama/OpenAI-style function schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _string_param(desc: str) -> dict[str, Any]:
    return {"type": "string", "description": desc}


DEFAULT_TOOLS: tuple[Tool, ...] = (
    Tool(
        name="read_file",
        description=(
            "Read a file inside the workspace. Text files return line-numbered content; "
            "documents (PDF, Word .docx/.doc, PowerPoint, Excel, ODF, RTF, EPUB) return extracted text."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": _string_param("File path relative to the workspace root."),
                "offset": {"type": "integer", "description": "0-based first line to read (optional)."},
                "limit": {"type": "integer", "description": "Max number of lines to read (optional, 0 = all)."},
            },
            "required": ["path"],
        },
        handler=_read_file,
        dangerous=False,
    ),
    Tool(
        name="write_file",
        description="Create or overwrite a file with the given content. Overwrites without warning.",
        parameters={
            "type": "object",
            "properties": {
                "path": _string_param("File path relative to the workspace root."),
                "content": _string_param("Full file content to write."),
            },
            "required": ["path", "content"],
        },
        handler=_write_file,
        dangerous=True,
    ),
    Tool(
        name="edit_file",
        description="Replace an exact unique string in a file. 'old' must match once, verbatim.",
        parameters={
            "type": "object",
            "properties": {
                "path": _string_param("File path relative to the workspace root."),
                "old": _string_param("Exact existing text to replace (must be unique in the file)."),
                "new": _string_param("Replacement text."),
            },
            "required": ["path", "old", "new"],
        },
        handler=_edit_file,
        dangerous=True,
    ),
    Tool(
        name="list_dir",
        description="List the entries of a directory inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": _string_param("Directory path relative to the workspace root (default: '.')."),
            },
            "required": [],
        },
        handler=_list_dir,
        dangerous=False,
    ),
    Tool(
        name="glob",
        description="Find files whose path or name matches a glob pattern (e.g. '**/*.py', 'src/*.ts').",
        parameters={
            "type": "object",
            "properties": {
                "pattern": _string_param("Glob pattern to match against relative paths and file names."),
            },
            "required": ["pattern"],
        },
        handler=_glob,
        dangerous=False,
    ),
    Tool(
        name="grep",
        description="Search for a literal substring across files in the workspace. Returns file:line:match.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": _string_param("Literal substring to search for."),
                "path": _string_param("File or directory to search in (default: '.')."),
            },
            "required": ["pattern"],
        },
        handler=_grep,
        dangerous=False,
    ),
    Tool(
        name="run_command",
        description=(
            "Run a command in a networkless OS sandbox containing only the workspace and "
            "read-only runtime binaries. Refuses to run if supported isolation is unavailable."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": _string_param("Shell command to execute."),
            },
            "required": ["command"],
        },
        handler=_run_command,
        dangerous=True,
    ),
)


def build_tool_map(tools: tuple[Tool, ...] = DEFAULT_TOOLS) -> dict[str, Tool]:
    return {tool.name: tool for tool in tools}
