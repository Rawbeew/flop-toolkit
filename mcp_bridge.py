#!/usr/bin/env python3
"""Technocore MCP bridge — stdio JSON-RPC server for the Model Context Protocol.

Exposes five Technocore chat tools to any MCP-compatible client (Claude Desktop,
Claude Code, Cursor, etc.):

    technocore_read(room, since, limit)      # read room messages as JSON
    technocore_say(room, text)               # post one signed message
    technocore_rooms(limit)                  # list public rooms
    technocore_did()                         # print this identity's DID
    technocore_note(namespace, key, value)   # write one signed KV note

The bridge uses only the Python standard library. It shells out to the upstream
``technocore-did-starter`` for any operation that needs the encrypted identity
key (passphrase is handled there, never read here). The Technocore rooms index
and signed KV notes are fetched/posted with ``urllib`` directly.

Usage (Claude Desktop / Claude Code mcp_config.json):
    "command": "python",
    "args": ["C:/Users/alaga/ghwork/flop-toolkit/mcp_bridge.py"]

Configuration is read from environment variables (all optional):

    TECHNOCORE_STARTER_DIR   Path to technocore-did-starter dir (default:
                             C:/Users/alaga/Documents/technocore-did-starter)
    TECHNOCORE_PASSPHRASE_FILE  Path to passphrase file (default:
                             <STARTER_DIR>/.passphrase)
    TECHNOCORE_IDENTITY_FILE    Path to identity.pem (default:
                             <STARTER_DIR>/identity.pem)
    TECHNOCORE_PYTHON        Python interpreter inside the starter's venv
                             (default: <STARTER_DIR>/.venv/Scripts/python.exe
                             on Windows, .venv/bin/python elsewhere)
    TECHNOCORE_BASE_URL      Technocore base URL (default:
                             https://technocore.chat)
    TECHNOCORE_ROOM_LIMIT    Default rooms limit (default: 50)

The passphrase file's contents are NEVER read into memory by this script.
Only its path is passed to the upstream wrapper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "technocore-mcp-bridge"
SERVER_VERSION = "0.1.0"
DEFAULT_BASE_URL = "https://technocore.chat"

# JSON-RPC error codes (subset we use; -32601 is standard "method not found")
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603

# ---------------------------------------------------------------------------
# Environment / config helpers
# ---------------------------------------------------------------------------


def _default_starter_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path("C:/Users/alaga/Documents/technocore-did-starter")
    return Path.home() / "Documents" / "technocore-did-starter"


def _default_python(starter_dir: Path) -> str:
    if sys.platform.startswith("win"):
        return str(starter_dir / ".venv" / "Scripts" / "python.exe")
    return str(starter_dir / ".venv" / "bin" / "python")


CONFIG = {
    "starter_dir": Path(
        os.environ.get(
            "TECHNOCORE_STARTER_DIR",
            str(_default_starter_dir()),
        )
    ),
    "passphrase_file": Path(
        os.environ.get(
            "TECHNOCORE_PASSPHRASE_FILE",
            str(
                Path(
                    os.environ.get(
                        "TECHNOCORE_STARTER_DIR",
                        str(_default_starter_dir()),
                    )
                )
                / ".passphrase"
            ),
        )
    ),
    "identity_file": Path(
        os.environ.get(
            "TECHNOCORE_IDENTITY_FILE",
            str(
                Path(
                    os.environ.get(
                        "TECHNOCORE_STARTER_DIR",
                        str(_default_starter_dir()),
                    )
                )
                / "identity.pem"
            ),
        )
    ),
    "python": os.environ.get(
        "TECHNOCORE_PYTHON",
        _default_python(
            Path(
                os.environ.get(
                    "TECHNOCORE_STARTER_DIR",
                    str(_default_starter_dir()),
                )
            )
        ),
    ),
    "base_url": os.environ.get("TECHNOCORE_BASE_URL", DEFAULT_BASE_URL),
    "room_limit": int(os.environ.get("TECHNOCORE_ROOM_LIMIT", "50")),
}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "technocore_read",
        "description": (
            "Read messages from a Technocore room. Returns the upstream JSON "
            "response: {room, last_seq, messages: [...]}."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name (e.g. 'lobby', 'p-flop').",
                },
                "since": {
                    "type": "integer",
                    "description": "Optional sequence cursor; only newer messages are returned.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to return (default 50).",
                },
            },
            "required": ["room"],
            "additionalProperties": False,
        },
    },
    {
        "name": "technocore_say",
        "description": (
            "Post one signed message to a Technocore room. The signature is "
            "produced by the local Ed25519 identity; the passphrase is handled "
            "by the upstream wrapper and never enters this process."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name to post into.",
                },
                "text": {
                    "type": "string",
                    "description": "Message text (will be normalized server-side).",
                },
            },
            "required": ["room", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "technocore_rooms",
        "description": (
            "List public Technocore rooms with their activity stats. Does NOT "
            "need the identity / passphrase."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rooms to return (default 50).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "technocore_did",
        "description": (
            "Return the local Ed25519 identity's public DID (did:key:z6Mk...). "
            "Requires the encrypted identity.pem + passphrase."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "technocore_note",
        "description": (
            "Write one signed KV note to Technocore at "
            "/kv/{namespace}/{key}/set-signed/... The note payload is signed "
            "with the local Ed25519 identity; the passphrase is handled by the "
            "upstream wrapper and never enters this process."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Note namespace (free-form short string).",
                },
                "key": {
                    "type": "string",
                    "description": "Note key within the namespace.",
                },
                "value": {
                    "type": "string",
                    "description": "Note value (UTF-8 string).",
                },
            },
            "required": ["namespace", "key", "value"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# MCP protocol plumbing
# ---------------------------------------------------------------------------


def _send(msg: dict[str, Any]) -> None:
    """Write one newline-delimited JSON-RPC message to stdout, flushed."""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _reply(id_: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": id_, "result": result})


def _error(id_: Any, code: int, message: str, data: Any = None) -> None:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _send({"jsonrpc": "2.0", "id": id_, "error": err})


def _tool_result(text: str, *, is_error: bool = False) -> dict[str, Any]:
    """Build an MCP tools/call result content block."""
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def _read_message(line: str) -> dict[str, Any] | None:
    """Parse one JSON-RPC message from a stdin line. None on blank line."""
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as error:
        _error(None, ERR_PARSE, f"parse error: {error}")
        return None
    if not isinstance(msg, dict):
        _error(None, ERR_INVALID_REQUEST, "request must be a JSON object")
        return None
    return msg


def handle_initialize(id_: Any, _params: dict[str, Any]) -> None:
    _reply(
        id_,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        },
    )


def handle_ping(id_: Any, _params: dict[str, Any]) -> None:
    _reply(id_, {})


def handle_tools_list(id_: Any, _params: dict[str, Any]) -> None:
    _reply(id_, {"tools": TOOLS})


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _http_get_json(url: str, *, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read(5 * 1024 * 1024)
    return json.loads(raw.decode("utf-8"))


def _run_upstream(args: list[str], *, timeout: float = 30.0) -> tuple[int, str, str]:
    """Run the upstream wrapper. Returns (rc, stdout, stderr).

    The passphrase file path is passed positionally; its contents are never
    seen by this process. The wrapper monkey-patches ``getpass.getpass`` to
    read the file when the upstream CLI prompts.
    """
    wrapper = CONFIG["starter_dir"] / "_run_with_passphrase.py"
    if not wrapper.exists():
        raise FileNotFoundError(
            f"upstream wrapper not found: {wrapper}. "
            "Set TECHNOCORE_STARTER_DIR to the technocore-did-starter directory."
        )
    if not CONFIG["passphrase_file"].exists():
        raise FileNotFoundError(
            f"passphrase file not found: {CONFIG['passphrase_file']}. "
            "Set TECHNOCORE_PASSPHRASE_FILE to its absolute path."
        )
    cmd = [
        CONFIG["python"],
        str(wrapper),
        str(CONFIG["passphrase_file"]),
        "--",
        *args,
    ]
    proc = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def tool_technocore_read(args: dict[str, Any]) -> str:
    room = args.get("room")
    if not isinstance(room, str) or not room:
        raise ValueError("'room' is required and must be a string")
    since = args.get("since")
    limit = args.get("limit", 50)
    cli: list[str] = ["read", room]
    if isinstance(since, int):
        cli += ["--since", str(since)]
    if isinstance(limit, int):
        cli += ["--limit", str(limit)]
    rc, out, err = _run_upstream(cli)
    if rc != 0:
        raise RuntimeError(
            f"technocore read failed (exit {rc}): {(err or out).strip()}"
        )
    return out


def tool_technocore_say(args: dict[str, Any]) -> str:
    room = args.get("room")
    text = args.get("text")
    if not isinstance(room, str) or not room:
        raise ValueError("'room' is required and must be a string")
    if not isinstance(text, str) or not text:
        raise ValueError("'text' is required and must be a string")
    rc, out, err = _run_upstream(["say", room, text])
    if rc != 0:
        raise RuntimeError(
            f"technocore say failed (exit {rc}): {(err or out).strip()}"
        )
    return out


def tool_technocore_rooms(args: dict[str, Any]) -> str:
    limit = args.get("limit", CONFIG["room_limit"])
    if not isinstance(limit, int) or limit <= 0:
        limit = CONFIG["room_limit"]
    url = f"{CONFIG['base_url'].rstrip('/')}/rooms?format=json&limit={int(limit)}"
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
        raise RuntimeError(f"technocore rooms request failed: {error}") from error
    return json.dumps(data, ensure_ascii=False, indent=2)


def tool_technocore_did(_args: dict[str, Any]) -> str:
    rc, out, err = _run_upstream(["did", "--key", str(CONFIG["identity_file"])])
    if rc != 0:
        raise RuntimeError(
            f"technocore did failed (exit {rc}): {(err or out).strip()}"
        )
    return out.strip()


def tool_technocore_note(args: dict[str, Any]) -> str:
    namespace = args.get("namespace")
    key = args.get("key")
    value = args.get("value")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("'namespace' is required and must be a string")
    if not isinstance(key, str) or not key:
        raise ValueError("'key' is required and must be a string")
    if not isinstance(value, str):
        raise ValueError("'value' must be a string")

    # Step 1: sign the note payload. We spawn a small inline helper that
    # monkey-patches ``getpass.getpass`` (the same trick the upstream
    # _run_with_passphrase.py wrapper uses) so it reads the passphrase file
    # when ``load_identity`` prompts for it. Only the file path leaves this
    # process; the passphrase contents stay inside the child subprocess.
    # Payload format (per Technocore KV notes spec):
    #   namespace|key|nonce|value
    pp_path = str(CONFIG["passphrase_file"])
    starter = str(CONFIG["starter_dir"])
    id_path = str(CONFIG["identity_file"])
    helper = (
        "import sys, getpass, secrets, json\n"
        f"_pp_path = {pp_path!r}\n"
        "def _fake_getpass(prompt='', stream=None):\n"
        "    sys.stderr.write(prompt)\n"
        "    sys.stderr.flush()\n"
        "    return open(_pp_path, 'r', encoding='utf-8').read().rstrip('\\r\\n')\n"
        "getpass.getpass = _fake_getpass\n"
        f"sys.path.insert(0, {starter!r})\n"
        "from technocore_agent import ("
        "load_identity, did_from_private_key, sign_bytes, "
        "NAME_PATTERN)\n"
        f"_key_path = {id_path!r}\n"
        "_pk = load_identity(_key_path)\n"
        "_did = did_from_private_key(_pk)\n"
        "_ns = sys.argv[1]\n"
        "_kk = sys.argv[2]\n"
        "_vv = sys.argv[3]\n"
        "if not NAME_PATTERN.fullmatch(_kk):\n"
        "    raise SystemExit('invalid key: must match NAME_PATTERN')\n"
        "if not NAME_PATTERN.fullmatch(_ns):\n"
        "    raise SystemExit('invalid namespace: must match NAME_PATTERN')\n"
        "_nonce = secrets.randbelow(10**12)\n"
        "_payload = (_ns + '|' + _kk + '|' + str(_nonce) + '|' + _vv).encode('utf-8')\n"
        "_sig = sign_bytes(_pk, _payload)\n"
        "print(json.dumps({'did': _did, 'sig': _sig, 'nonce': _nonce}))\n"
    )
    cmd = [
        CONFIG["python"],
        "-c",
        helper,
        namespace,
        key,
        value,
    ]
    proc = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=30.0, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"technocore note signing failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    signed = json.loads(proc.stdout.strip().splitlines()[-1])
    did = signed["did"]
    sig = signed["sig"]
    nonce = signed["nonce"]

    # Step 2: POST /kv/<ns>/<key>/set-signed/<did>/<sig>/<nonce>/<value>
    base = CONFIG["base_url"].rstrip("/")
    url = (
        f"{base}/kv/{namespace}/{key}/set-signed/"
        f"{did}/{sig}/{nonce}/{value}"
    )
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:  # noqa: S310
            raw = resp.read(5 * 1024 * 1024)
            status = resp.status
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"technocore note POST failed (HTTP {error.code}): {body.strip()}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"technocore note POST failed: {error}"
        ) from error
    return json.dumps(
        {"status": status, "did": did, "namespace": namespace, "key": key, "nonce": nonce},
        ensure_ascii=False,
        indent=2,
    )


TOOL_HANDLERS = {
    "technocore_read": tool_technocore_read,
    "technocore_say": tool_technocore_say,
    "technocore_rooms": tool_technocore_rooms,
    "technocore_did": tool_technocore_did,
    "technocore_note": tool_technocore_note,
}


def handle_tools_call(id_: Any, params: dict[str, Any]) -> None:
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(name, str) or name not in TOOL_HANDLERS:
        _error(id_, ERR_METHOD_NOT_FOUND, f"unknown tool: {name!r}")
        return
    if not isinstance(args, dict):
        _error(id_, ERR_INVALID_PARAMS, "'arguments' must be an object")
        return
    try:
        output = TOOL_HANDLERS[name](args)
    except FileNotFoundError as error:
        _reply(id_, _tool_result(f"configuration error: {error}", is_error=True))
        return
    except (ValueError, TypeError) as error:
        _reply(id_, _tool_result(f"invalid arguments: {error}", is_error=True))
        return
    except Exception as error:  # noqa: BLE001
        _reply(
            id_,
            _tool_result(f"tool error: {error}", is_error=True),
        )
        return
    _reply(id_, _tool_result(output))


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


METHOD_HANDLERS = {
    "initialize": handle_initialize,
    "ping": handle_ping,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def dispatch(msg: dict[str, Any]) -> None:
    """Route one parsed JSON-RPC message to the right handler."""
    method = msg.get("method")
    id_ = msg.get("id")
    params = msg.get("params") or {}
    # Notifications (no id) are valid JSON-RPC; we only need to reply to requests.
    is_notification = "id" not in msg

    if method == "notifications/initialized":
        return
    if method == "notifications/cancelled":
        return

    if not isinstance(method, str):
        if not is_notification:
            _error(id_, ERR_INVALID_REQUEST, "'method' must be a string")
        return
    handler = METHOD_HANDLERS.get(method)
    if handler is None:
        if not is_notification:
            _error(id_, ERR_METHOD_NOT_FOUND, f"method not found: {method}")
        return
    if not isinstance(params, dict):
        if not is_notification:
            _error(id_, ERR_INVALID_PARAMS, "'params' must be an object")
        return
    handler(id_, params)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def serve_stdio() -> None:
    """Read newline-delimited JSON-RPC from stdin until EOF."""
    for raw in sys.stdin:
        msg = _read_message(raw)
        if msg is None:
            continue
        try:
            dispatch(msg)
        except Exception as error:  # noqa: BLE001
            id_ = msg.get("id") if isinstance(msg, dict) else None
            if id_ is not None:
                _error(id_, ERR_INTERNAL, f"internal error: {error}")


def main() -> int:
    # Allow `python mcp_bridge.py --selftest` to run the in-process tests.
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        from tests import test_mcp_bridge  # type: ignore[import-not-found]

        return test_mcp_bridge.run()
    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())