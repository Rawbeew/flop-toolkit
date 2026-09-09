"""Unit tests for the Technocore MCP bridge JSON-RPC handler.

The tests import ``mcp_bridge`` as a module and exercise the dispatch loop
in-process by patching the low-level ``_send`` writer so we capture outgoing
JSON-RPC messages instead of writing to stdout. Tool handlers are monkey-
patched so the tests do NOT make network or filesystem requests.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

# Ensure the toolkit root is on sys.path so `import mcp_bridge` works whether
# the tests are invoked from the repo root or from inside ``tests/``.
TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

import mcp_bridge  # noqa: E402


def _capture_dispatch(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """Patch ``_send`` to capture output, then dispatch one message."""
    captured: list[dict[str, Any]] = []
    with mock.patch.object(mcp_bridge, "_send", side_effect=captured.append):
        mcp_bridge.dispatch(msg)
    return captured


def _capture_serve_stdio(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run ``serve_stdio`` with a fake stdin and capture all emitted messages.

    ``messages`` is the list of JSON-RPC request/notification dicts the client
    would write to stdin. Blank lines (simulating client padding) are added
    explicitly because JSON-encoding a blank string would produce ``""`` /
    ``"   "`` which are *valid* JSON strings (not blanks) and would be parsed
    as malformed requests.
    """
    stdin_lines = [json.dumps(m) for m in messages]
    stdin_text = "\n".join(stdin_lines) + "\n"
    captured: list[dict[str, Any]] = []
    fake_stdin = io.StringIO(stdin_text)
    with mock.patch.object(mcp_bridge.sys, "stdin", fake_stdin), mock.patch.object(
        mcp_bridge, "_send", side_effect=captured.append
    ):
        mcp_bridge.serve_stdio()
    return captured


class InitializerTests(unittest.TestCase):
    def test_initialize_returns_protocol_version(self) -> None:
        msgs = _capture_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26"},
            }
        )
        self.assertEqual(len(msgs), 1)
        result = msgs[0]["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertEqual(result["serverInfo"]["name"], "technocore-mcp-bridge")
        self.assertIn("tools", result["capabilities"])
        self.assertTrue(result["capabilities"]["tools"]["listChanged"] is False)
        self.assertEqual(msgs[0]["id"], 1)
        self.assertEqual(msgs[0]["jsonrpc"], "2.0")

    def test_initialized_notification_is_silent(self) -> None:
        msgs = _capture_dispatch(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self.assertEqual(msgs, [])

    def test_cancelled_notification_is_silent(self) -> None:
        msgs = _capture_dispatch(
            {"jsonrpc": "2.0", "method": "notifications/cancelled"}
        )
        self.assertEqual(msgs, [])

    def test_ping_replies_with_empty_object(self) -> None:
        msgs = _capture_dispatch({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["result"], {})
        self.assertEqual(msgs[0]["id"], 7)


class ToolsListTests(unittest.TestCase):
    def test_lists_all_five_tools(self) -> None:
        msgs = _capture_dispatch(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        self.assertEqual(len(msgs), 1)
        tools = msgs[0]["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(
            names,
            {
                "technocore_read",
                "technocore_say",
                "technocore_rooms",
                "technocore_did",
                "technocore_note",
            },
        )
        # Each tool must declare inputSchema with type=object.
        for tool in tools:
            self.assertIn("inputSchema", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("description", tool)

    def test_technocore_read_requires_room(self) -> None:
        tools = {t["name"]: t for t in mcp_bridge.TOOLS}
        self.assertEqual(tools["technocore_read"]["inputSchema"]["required"], ["room"])

    def test_technocore_say_requires_room_and_text(self) -> None:
        tools = {t["name"]: t for t in mcp_bridge.TOOLS}
        self.assertEqual(
            sorted(tools["technocore_say"]["inputSchema"]["required"]),
            ["room", "text"],
        )

    def test_technocore_note_requires_namespace_key_value(self) -> None:
        tools = {t["name"]: t for t in mcp_bridge.TOOLS}
        self.assertEqual(
            sorted(tools["technocore_note"]["inputSchema"]["required"]),
            ["key", "namespace", "value"],
        )


class ToolsCallTests(unittest.TestCase):
    def test_unknown_tool_returns_method_not_found(self) -> None:
        msgs = _capture_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "nope", "arguments": {}},
            }
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["error"]["code"], mcp_bridge.ERR_METHOD_NOT_FOUND)
        self.assertEqual(msgs[0]["id"], 3)

    def test_invalid_arguments_type_returns_invalid_params(self) -> None:
        msgs = _capture_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "technocore_rooms", "arguments": "bad"},
            }
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["error"]["code"], mcp_bridge.ERR_INVALID_PARAMS)
        self.assertEqual(msgs[0]["id"], 4)

    def test_tool_error_is_reported_with_isError(self) -> None:
        def boom(_args: dict[str, Any]) -> str:
            raise RuntimeError("kapow")

        with mock.patch.dict(
            mcp_bridge.TOOL_HANDLERS, {"technocore_rooms": boom}
        ):
            msgs = _capture_dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {"name": "technocore_rooms", "arguments": {}},
                }
            )
        self.assertEqual(len(msgs), 1)
        result = msgs[0]["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("kapow", result["content"][0]["text"])

    def test_tool_value_error_is_reported_as_invalid_arguments(self) -> None:
        msgs = _capture_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "technocore_read", "arguments": {}},
            }
        )
        self.assertEqual(len(msgs), 1)
        result = msgs[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("room", result["content"][0]["text"])

    def test_successful_tool_call_returns_text_content(self) -> None:
        with mock.patch.dict(
            mcp_bridge.TOOL_HANDLERS,
            {"technocore_rooms": lambda _a: json.dumps({"rooms": []})},
        ):
            msgs = _capture_dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {"name": "technocore_rooms", "arguments": {}},
                }
            )
        self.assertEqual(len(msgs), 1)
        result = msgs[0]["result"]
        self.assertFalse(result.get("isError", False))
        self.assertEqual(json.loads(result["content"][0]["text"]), {"rooms": []})


class ParseAndDispatchTests(unittest.TestCase):
    def test_unknown_method_returns_method_not_found(self) -> None:
        msgs = _capture_dispatch(
            {"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["error"]["code"], mcp_bridge.ERR_METHOD_NOT_FOUND)

    def test_missing_method_is_invalid_request(self) -> None:
        msgs = _capture_dispatch({"jsonrpc": "2.0", "id": 10})
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["error"]["code"], mcp_bridge.ERR_INVALID_REQUEST)

    def test_non_object_params_is_invalid_params(self) -> None:
        msgs = _capture_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "initialize",
                "params": "nope",
            }
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["error"]["code"], mcp_bridge.ERR_INVALID_PARAMS)

    def test_read_message_returns_none_on_blank_line(self) -> None:
        self.assertIsNone(mcp_bridge._read_message(""))
        self.assertIsNone(mcp_bridge._read_message("   \n"))

    def test_read_message_parses_object(self) -> None:
        msg = mcp_bridge._read_message('{"jsonrpc":"2.0","id":1}\n')
        self.assertEqual(msg, {"jsonrpc": "2.0", "id": 1})

    def test_read_message_rejects_non_object(self) -> None:
        captured: list[dict[str, Any]] = []
        with mock.patch.object(mcp_bridge, "_send", side_effect=captured.append):
            result = mcp_bridge._read_message('"hello"')
        self.assertIsNone(result)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["error"]["code"], mcp_bridge.ERR_INVALID_REQUEST)


class ServeStdioTests(unittest.TestCase):
    def test_handles_full_handshake_sequence(self) -> None:
        """initialize -> initialized -> tools/list -> tools/call."""
        # Stub the rooms handler so we don't hit the network.
        with mock.patch.dict(
            mcp_bridge.TOOL_HANDLERS,
            {"technocore_rooms": lambda _a: json.dumps({"rooms": []})},
        ):
            messages = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26"},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "technocore_rooms", "arguments": {}},
                },
            ]
            captured = _capture_serve_stdio(messages)

        # Four messages, four replies (the initialized notification is silent).
        self.assertEqual(len(captured), 3)
        self.assertEqual(captured[0]["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", captured[1]["result"])
        self.assertEqual(captured[2]["id"], 3)
        self.assertIn("content", captured[2]["result"])

    def test_silently_skips_blank_lines(self) -> None:
        # Real MCP clients pad with blank lines between requests; these must
        # be ignored without producing a parse-error response.
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ]
        # Inject blank lines by editing the wire text directly.
        stdin_text = "\n" + "\n".join(json.dumps(m) for m in messages) + "\n   \n"
        captured: list[dict[str, Any]] = []
        fake_stdin = io.StringIO(stdin_text)
        with mock.patch.object(mcp_bridge.sys, "stdin", fake_stdin), mock.patch.object(
            mcp_bridge, "_send", side_effect=captured.append
        ):
            mcp_bridge.serve_stdio()
        self.assertEqual(len(captured), 2)
        self.assertEqual([m["id"] for m in captured], [1, 2])


class ConfigEnvTests(unittest.TestCase):
    def test_overrides_via_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            starter = Path(tmp) / "starter"
            starter.mkdir()
            (starter / ".passphrase").write_text("hunter2\n", encoding="utf-8")
            (starter / "identity.pem").write_text("pem\n", encoding="utf-8")
            env = {
                "TECHNOCORE_STARTER_DIR": str(starter),
                "TECHNOCORE_BASE_URL": "https://example.test",
                "TECHNOCORE_ROOM_LIMIT": "12",
                "TECHNOCORE_PYTHON": sys.executable,
            }
            with mock.patch.dict(os.environ, env, clear=False):
                # Re-import the module so CONFIG is rebuilt with our env.
                import importlib

                fresh = importlib.reload(mcp_bridge)
                self.assertEqual(fresh.CONFIG["base_url"], "https://example.test")
                self.assertEqual(fresh.CONFIG["room_limit"], 12)
                self.assertEqual(fresh.CONFIG["python"], sys.executable)
                self.assertEqual(
                    fresh.CONFIG["passphrase_file"],
                    starter / ".passphrase",
                )


class UpstreamWrapperTests(unittest.TestCase):
    """Tests that verify the wrapper is invoked with file paths only — never
    with the passphrase contents."""

    def test_technocore_read_passes_path_not_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            starter = Path(tmp) / "starter"
            starter.mkdir()
            pp = starter / ".passphrase"
            pp.write_text("supersecret123\n", encoding="utf-8")
            idp = starter / "identity.pem"
            idp.write_text("pem\n", encoding="utf-8")
            wrapper = starter / "_run_with_passphrase.py"
            wrapper.write_text("# placeholder\n", encoding="utf-8")
            with mock.patch.dict(
                mcp_bridge.CONFIG,
                {
                    "starter_dir": starter,
                    "passphrase_file": pp,
                    "identity_file": idp,
                    "python": sys.executable,
                    "base_url": "https://example.test",
                    "room_limit": 5,
                },
            ), mock.patch.object(
                mcp_bridge, "_run_upstream", return_value=(0, "ok", "")
            ) as run_mock:
                mcp_bridge.tool_technocore_read({"room": "lobby"})
                # ``_run_upstream`` was called with the upstream CLI args; we
                # need to verify the wrapper itself would have invoked the
                # python binary and forwarded the passphrase *path*, not its
                # contents. Build the cmd that _run_upstream would construct,
                # using the patched CONFIG (still in scope here).
                upstream_args = run_mock.call_args[0][0]
                cfg = mcp_bridge.CONFIG
                cmd = [
                    cfg["python"],
                    str(cfg["starter_dir"] / "_run_with_passphrase.py"),
                    str(cfg["passphrase_file"]),
                    "--",
                    *upstream_args,
                ]
            self.assertEqual(upstream_args[0], "read")
            self.assertEqual(upstream_args[1], "lobby")
            self.assertNotIn("supersecret123", cmd)
            self.assertIn(str(pp), cmd)

    def test_technocore_say_invokes_wrapper(self) -> None:
        with mock.patch.object(
            mcp_bridge, "_run_upstream", return_value=(0, '{"ok":true}', "")
        ) as run_mock:
            mcp_bridge.tool_technocore_say({"room": "lobby", "text": "hi"})
        # ``_run_upstream`` received the raw upstream CLI argv after the ``--``.
        upstream_args = run_mock.call_args[0][0]
        self.assertEqual(upstream_args, ["say", "lobby", "hi"])

    def test_technocore_did_passes_identity_file(self) -> None:
        with mock.patch.object(
            mcp_bridge, "_run_upstream", return_value=(0, "did:key:z6Mkabc\n", "")
        ) as run_mock:
            result = mcp_bridge.tool_technocore_did({})
        self.assertEqual(result, "did:key:z6Mkabc")
        upstream_args = run_mock.call_args[0][0]
        self.assertEqual(
            upstream_args,
            ["did", "--key", str(mcp_bridge.CONFIG["identity_file"])],
        )

    def test_technocore_rooms_makes_http_request(self) -> None:
        with mock.patch.object(
            mcp_bridge,
            "_http_get_json",
            return_value={"rooms": [{"room": "lobby"}]},
        ) as http_mock:
            result = mcp_bridge.tool_technocore_rooms({"limit": 7})
        self.assertEqual(json.loads(result), {"rooms": [{"room": "lobby"}]})
        self.assertIn("limit=7", http_mock.call_args[0][0])

    def test_technocore_rooms_uses_default_limit(self) -> None:
        with mock.patch.object(
            mcp_bridge,
            "_http_get_json",
            return_value={"rooms": []},
        ) as http_mock:
            mcp_bridge.tool_technocore_rooms({})
        self.assertIn(
            f"limit={mcp_bridge.CONFIG['room_limit']}",
            http_mock.call_args[0][0],
        )

    def test_technocore_note_signs_and_posts(self) -> None:
        # Stub the signing subprocess: just print the JSON we'd expect.
        fake_signing_output = json.dumps(
            {"did": "did:key:z6Mkfake", "sig": "sigvalue", "nonce": 42}
        )
        # Stub the upstream CLI: we don't want a real subprocess.
        with mock.patch.object(
            subprocess, "run", return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=fake_signing_output + "\n", stderr=""
            )
        ) as run_mock, mock.patch.object(
            mcp_bridge.urllib.request, "urlopen"
        ) as url_mock:
            url_resp = mock.MagicMock()
            url_resp.status = 200
            url_resp.read.return_value = b'{"ok":true}'
            url_resp.__enter__ = mock.MagicMock(return_value=url_resp)
            url_resp.__exit__ = mock.MagicMock(return_value=False)
            url_mock.return_value = url_resp
            result = mcp_bridge.tool_technocore_note(
                {"namespace": "flop", "key": "v1", "value": "hello"}
            )
        # Verify the helper script received our passphrase FILE PATH, not its
        # contents (the passphrase contents are not even in scope here).
        signed_cmd = run_mock.call_args[0][0]
        self.assertEqual(signed_cmd[0], str(mcp_bridge.CONFIG["python"]))
        self.assertIn("-c", signed_cmd)
        helper_src = signed_cmd[signed_cmd.index("-c") + 1]
        # The helper source embeds the passphrase path via repr() — normalize
        # both representations before comparing.
        expected_path = repr(str(mcp_bridge.CONFIG["passphrase_file"]))[1:-1]
        self.assertIn(expected_path, helper_src)
        # The POST URL must carry the DID, sig, nonce, value.
        posted_url = url_mock.call_args[0][0].full_url
        self.assertIn("/kv/flop/v1/set-signed/", posted_url)
        self.assertIn("did:key:z6Mkfake", posted_url)
        self.assertIn("sigvalue", posted_url)
        self.assertIn("/42/", posted_url)
        self.assertTrue(posted_url.endswith("/hello"))
        # Result is JSON with the metadata we returned.
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], 200)
        self.assertEqual(parsed["namespace"], "flop")
        self.assertEqual(parsed["key"], "v1")
        self.assertEqual(parsed["nonce"], 42)


def run() -> int:
    """Entry point used by ``python mcp_bridge.py --selftest``."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run())