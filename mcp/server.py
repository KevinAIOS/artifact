#!/usr/bin/env python3
"""Stdlib-only MCP stdio server for Artifact tools.

Supports:
  - Content-Length framed JSON-RPC (MCP standard)
  - Newline-delimited JSON (handy for smoke / curl-style tests)

Store resolution matches CLI:
  ARTIFACT_STORE → existing ./.artifact/store.json → ~/.artifact/store.json
  ARTIFACT_PROJECT=1 forces project store under cwd.

Tools: upsert_artifact, resolve_artifact, attach_ontology, query_artifacts, list_classes
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from artifact_cli import (  # noqa: E402
    collect_class_names,
    find_by_name,
    find_by_reference,
    load_store,
    resolve_store_path,
    save_store,
)

SERVER_NAME = "artifact"
SERVER_VERSION = "0.2.0"
PROTOCOL_VERSION = "2024-11-05"


def store_path() -> Path:
    return resolve_store_path(
        project=os.environ.get("ARTIFACT_PROJECT", "").strip() in ("1", "true", "yes"),
    )


TOOLS = [
    {
        "name": "upsert_artifact",
        "description": "Create or update an Artifact (Name+Reference together). Omit reference to generate art://<uuid>.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "reference": {"type": "string"},
                "kind": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "resolve_artifact",
        "description": "Resolve an Artifact by reference, name, or id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string"},
                "name": {"type": "string"},
                "id": {"type": "string"},
            },
        },
    },
    {
        "name": "attach_ontology",
        "description": "Attach or update an ontology key (e.g. class, signal) on an Artifact.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string"},
                "name": {"type": "string"},
                "id": {"type": "string"},
                "key": {"type": "string"},
                "value": {},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "query_artifacts",
        "description": "Query artifacts by name, reference, class, or ontology key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "reference": {"type": "string"},
                "class": {"type": "string"},
                "key": {"type": "string"},
                "value": {},
            },
        },
    },
    {
        "name": "list_classes",
        "description": "Return short class-name list from the store (for harness inject).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def ok_result(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def err_result(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def tool_upsert(args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    if not name:
        raise ValueError("name required")
    reference = args.get("reference") or f"art://{uuid.uuid4()}"
    path = store_path()
    store = load_store(path)
    arts = store["artifacts"]
    existing = find_by_reference(arts, reference)
    if existing is not None:
        existing["name"] = name
        existing["reference"] = reference
        if args.get("kind"):
            existing["kind"] = args["kind"]
        art = existing
        action = "updated"
    else:
        art = {
            "id": str(uuid.uuid4()),
            "name": name,
            "reference": reference,
            "ontology": {},
        }
        if args.get("kind"):
            art["kind"] = args["kind"]
        arts.append(art)
        action = "created"
    save_store(path, store)
    return {"ok": True, "action": action, "artifact": art, "store": str(path)}


def tool_resolve(args: dict[str, Any]) -> dict[str, Any]:
    path = store_path()
    store = load_store(path)
    arts = store["artifacts"]
    hits: list[dict[str, Any]] = []
    if args.get("reference"):
        found = find_by_reference(arts, args["reference"])
        if found:
            hits.append(found)
    elif args.get("name"):
        hits = find_by_name(arts, args["name"])
    elif args.get("id"):
        hits = [a for a in arts if a.get("id") == args["id"]]
    else:
        raise ValueError("provide reference, name, or id")
    return {"ok": True, "count": len(hits), "artifacts": hits, "store": str(path)}


def tool_attach(args: dict[str, Any]) -> dict[str, Any]:
    path = store_path()
    store = load_store(path)
    arts = store["artifacts"]
    art = None
    if args.get("reference"):
        art = find_by_reference(arts, args["reference"])
    elif args.get("id"):
        for a in arts:
            if a.get("id") == args["id"]:
                art = a
                break
    elif args.get("name"):
        matches = find_by_name(arts, args["name"])
        if len(matches) == 1:
            art = matches[0]
        elif len(matches) > 1:
            raise ValueError("multiple name matches; pass reference or id")
    if art is None:
        raise ValueError("artifact not found")
    key = args.get("key")
    if not key:
        raise ValueError("key required")
    value = args.get("value")
    ontology = art.setdefault("ontology", {})
    if not isinstance(ontology, dict):
        ontology = {}
        art["ontology"] = ontology
    if key in ("class", "classes") and isinstance(value, str):
        existing = ontology.get("class")
        if existing is None:
            ontology["class"] = [value]
        elif isinstance(existing, list):
            if value not in existing:
                existing.append(value)
        else:
            ontology["class"] = [existing] if existing == value else [existing, value]
    else:
        ontology[key] = value
    save_store(path, store)
    return {"ok": True, "action": "attached", "artifact": art, "store": str(path)}


def tool_query(args: dict[str, Any]) -> dict[str, Any]:
    path = store_path()
    store = load_store(path)
    hits = list(store["artifacts"])
    if args.get("name"):
        needle = str(args["name"]).lower()
        hits = [a for a in hits if needle in str(a.get("name", "")).lower()]
    if args.get("reference"):
        needle = str(args["reference"])
        hits = [a for a in hits if needle in str(a.get("reference", ""))]
    if args.get("class"):
        cn = args["class"]
        filtered = []
        for a in hits:
            ont = a.get("ontology") or {}
            classes = ont.get("class") or ont.get("classes")
            if isinstance(classes, list) and cn in classes:
                filtered.append(a)
            elif classes == cn:
                filtered.append(a)
        hits = filtered
    if args.get("key"):
        key = args["key"]
        filtered = []
        for a in hits:
            ont = a.get("ontology") or {}
            if key not in ont:
                continue
            if "value" in args and ont.get(key) != args.get("value"):
                continue
            filtered.append(a)
        hits = filtered
    return {"ok": True, "count": len(hits), "artifacts": hits, "store": str(path)}


def tool_list_classes(_: dict[str, Any]) -> dict[str, Any]:
    path = store_path()
    store = load_store(path)
    return {"ok": True, "classes": collect_class_names(store), "store": str(path)}


DISPATCH = {
    "upsert_artifact": tool_upsert,
    "resolve_artifact": tool_resolve,
    "attach_ontology": tool_attach,
    "query_artifacts": tool_query,
    "list_classes": tool_list_classes,
}


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Return response dict, or None for notifications (no reply)."""
    id_ = msg.get("id", None)
    method = msg.get("method") or ""
    params = msg.get("params") or {}
    is_notification = "id" not in msg

    if method in ("initialize",):
        return ok_result(
            id_,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method in ("notifications/initialized", "initialized"):
        return None if is_notification else ok_result(id_, {})
    if method in ("ping",):
        return ok_result(id_, {})
    if method in ("tools/list", "list_tools"):
        return ok_result(id_, {"tools": TOOLS})
    if method in ("tools/call", "call_tool"):
        name = params.get("name")
        arguments = params.get("arguments") or params.get("args") or {}
        if name not in DISPATCH:
            return err_result(id_, -32601, f"unknown tool: {name}")
        try:
            result = DISPATCH[name](arguments)
            return ok_result(
                id_,
                {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "structuredContent": result,
                },
            )
        except Exception as e:  # noqa: BLE001 — surface tool errors
            return err_result(id_, -32000, str(e))
    if method in DISPATCH:
        try:
            return ok_result(id_, DISPATCH[method](params if isinstance(params, dict) else {}))
        except Exception as e:  # noqa: BLE001
            return err_result(id_, -32000, str(e))
    if is_notification:
        return None
    return err_result(id_, -32601, f"method not found: {method}")


def write_message(msg: dict[str, Any], *, framed: bool) -> None:
    body = json.dumps(msg, ensure_ascii=False)
    if framed:
        data = body.encode("utf-8")
        sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n")
        sys.stdout.flush()
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    else:
        sys.stdout.write(body + "\n")
        sys.stdout.flush()


def iter_messages() -> Iterator[tuple[dict[str, Any], bool]]:
    """Yield (message, used_content_length_framing)."""
    # Peek first bytes to decide framing mode for the session.
    # Support mixing: if a line starts with Content-Length, use framed;
    # otherwise treat each non-empty line as a JSON message.
    buf = b""
    while True:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            if buf.strip():
                # leftover line
                try:
                    yield json.loads(buf.decode("utf-8")), False
                except json.JSONDecodeError:
                    pass
            return
        buf += chunk
        if buf.startswith(b"Content-Length:") or buf.lower().startswith(b"content-length:"):
            # Read headers until blank line
            while b"\r\n\r\n" not in buf and b"\n\n" not in buf:
                more = sys.stdin.buffer.read(1)
                if not more:
                    return
                buf += more
            if b"\r\n\r\n" in buf:
                header, rest = buf.split(b"\r\n\r\n", 1)
            else:
                header, rest = buf.split(b"\n\n", 1)
            length = None
            for line in header.split(b"\n"):
                line = line.strip(b"\r")
                if line.lower().startswith(b"content-length:"):
                    try:
                        length = int(line.split(b":", 1)[1].strip())
                    except ValueError:
                        length = None
            if length is None:
                buf = rest
                continue
            body = rest
            while len(body) < length:
                more = sys.stdin.buffer.read(length - len(body))
                if not more:
                    return
                body += more
            payload = body[:length]
            buf = body[length:]
            try:
                yield json.loads(payload.decode("utf-8")), True
            except json.JSONDecodeError as e:
                write_message(err_result(None, -32700, f"parse error: {e}"), framed=True)
            continue

        if chunk == b"\n":
            line = buf.decode("utf-8", errors="replace").strip()
            buf = b""
            if not line:
                continue
            try:
                yield json.loads(line), False
            except json.JSONDecodeError as e:
                write_message(err_result(None, -32700, f"parse error: {e}"), framed=False)


def main() -> None:
    for msg, framed in iter_messages():
        if not isinstance(msg, dict):
            write_message(err_result(None, -32600, "invalid request"), framed=framed)
            continue
        out = handle(msg)
        if out is not None:
            write_message(out, framed=framed)


if __name__ == "__main__":
    main()
