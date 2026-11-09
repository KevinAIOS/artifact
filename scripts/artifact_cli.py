#!/usr/bin/env python3
"""Artifact store-backed CLI: upsert|resolve|attach|query|classes|list-classes|paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


def _looks_like_project_root(cwd: Path) -> bool:
    """Heuristic: git repo or common project markers."""
    markers = (
        ".git",
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "Gemfile",
        "composer.json",
        ".artifact",
    )
    for name in markers:
        if (cwd / name).exists():
            return True
    return False


def resolve_store_path(
    *,
    project: bool = False,
    cwd: Path | None = None,
    explicit: str | None = None,
    create_project: bool = False,
) -> Path:
    """Store resolution order:
    1. explicit path (--store) if given
    2. ARTIFACT_STORE env
    3. ./.artifact/store.json when --project (create) or file already exists
    4. else ~/.artifact/store.json
    """
    if explicit:
        return Path(explicit).expanduser().resolve()

    env = os.environ.get("ARTIFACT_STORE")
    if env:
        return Path(env).expanduser().resolve()

    here = (cwd or Path.cwd()).resolve()
    project_store = here / ".artifact" / "store.json"

    want_project = project or create_project or os.environ.get("ARTIFACT_PROJECT", "").strip() in (
        "1",
        "true",
        "yes",
    )
    if want_project:
        return project_store

    if project_store.is_file():
        return project_store

    return (Path.home() / ".artifact" / "store.json").resolve()


def default_store_path() -> Path:
    """Backward-compatible: env → existing project store → home store."""
    return resolve_store_path()


def load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "artifacts": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {"version": 1, "artifacts": []}
    data.setdefault("version", 1)
    data.setdefault("artifacts", [])
    if not isinstance(data["artifacts"], list):
        data["artifacts"] = []
    return data


def save_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def emit(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def find_by_reference(arts: list[dict[str, Any]], reference: str) -> dict[str, Any] | None:
    for a in arts:
        if a.get("reference") == reference:
            return a
    return None


def find_by_name(arts: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [a for a in arts if a.get("name") == name]


def store_from_args(args: argparse.Namespace) -> Path:
    return resolve_store_path(
        project=bool(getattr(args, "project", False)),
        explicit=getattr(args, "store", None),
        create_project=bool(getattr(args, "project", False)),
    )


def cmd_upsert(args: argparse.Namespace) -> int:
    path = store_from_args(args)
    store = load_store(path)
    arts = store["artifacts"]

    name = args.name
    reference = args.reference
    if not name:
        print("error: --name required", file=sys.stderr)
        return 2
    if not reference:
        reference = f"art://{uuid.uuid4()}"

    existing = find_by_reference(arts, reference)
    if existing is None and args.match_name:
        matches = find_by_name(arts, name)
        if len(matches) == 1:
            existing = matches[0]

    if existing is not None:
        existing["name"] = name
        existing["reference"] = reference
        if args.kind:
            existing["kind"] = args.kind
        art = existing
        action = "updated"
    else:
        art = {
            "id": str(uuid.uuid4()),
            "name": name,
            "reference": reference,
            "ontology": {},
        }
        if args.kind:
            art["kind"] = args.kind
        arts.append(art)
        action = "created"

    save_store(path, store)
    emit({"ok": True, "action": action, "artifact": art, "store": str(path)})
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    path = store_from_args(args)
    store = load_store(path)
    arts = store["artifacts"]
    hits: list[dict[str, Any]] = []
    if args.reference:
        found = find_by_reference(arts, args.reference)
        if found:
            hits.append(found)
    elif args.name:
        hits = find_by_name(arts, args.name)
    elif args.id:
        hits = [a for a in arts if a.get("id") == args.id]
    else:
        print("error: provide --reference, --name, or --id", file=sys.stderr)
        return 2
    emit({"ok": True, "count": len(hits), "artifacts": hits, "store": str(path)})
    return 0 if hits else 1


def cmd_attach(args: argparse.Namespace) -> int:
    path = store_from_args(args)
    store = load_store(path)
    arts = store["artifacts"]

    art = None
    if args.reference:
        art = find_by_reference(arts, args.reference)
    elif args.id:
        for a in arts:
            if a.get("id") == args.id:
                art = a
                break
    elif args.name:
        matches = find_by_name(arts, args.name)
        if len(matches) == 1:
            art = matches[0]
        elif len(matches) > 1:
            print("error: multiple artifacts with that name; pass --reference or --id", file=sys.stderr)
            return 2

    if art is None:
        print("error: artifact not found", file=sys.stderr)
        return 1

    key = args.key
    if not key:
        print("error: --key required", file=sys.stderr)
        return 2

    raw = args.value
    try:
        value: Any = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw

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
            ontology["class"] = list({existing, value}) if existing != value else [existing]
    else:
        ontology[key] = value

    save_store(path, store)
    emit({"ok": True, "action": "attached", "artifact": art, "store": str(path)})
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    path = store_from_args(args)
    store = load_store(path)
    arts = store["artifacts"]
    hits = arts

    if args.name:
        needle = args.name.lower()
        hits = [a for a in hits if needle in str(a.get("name", "")).lower()]
    if args.reference:
        needle = args.reference
        hits = [a for a in hits if needle in str(a.get("reference", ""))]
    if args.class_name:
        cn = args.class_name
        filtered = []
        for a in hits:
            ont = a.get("ontology") or {}
            classes = ont.get("class") or ont.get("classes")
            if classes is None:
                continue
            if isinstance(classes, list):
                if cn in classes:
                    filtered.append(a)
            elif classes == cn:
                filtered.append(a)
        hits = filtered
    if args.key:
        filtered = []
        for a in hits:
            ont = a.get("ontology") or {}
            if args.key not in ont:
                continue
            if args.value is not None:
                try:
                    want = json.loads(args.value)
                except (json.JSONDecodeError, TypeError):
                    want = args.value
                if ont.get(args.key) != want:
                    continue
            filtered.append(a)
        hits = filtered

    emit({"ok": True, "count": len(hits), "artifacts": hits, "store": str(path)})
    return 0


def collect_class_names(store: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for a in store.get("artifacts") or []:
        ont = a.get("ontology") or {}
        classes = ont.get("class") or ont.get("classes")
        if classes is None:
            continue
        if isinstance(classes, list):
            for c in classes:
                if isinstance(c, str) and c.strip():
                    names.add(c.strip())
        elif isinstance(classes, str) and classes.strip():
            names.add(classes.strip())
    return sorted(names)


def format_inject(names: list[str], path: Path, label: str = "Artifact classes (names only)") -> str:
    payload = json.dumps(names, ensure_ascii=False)
    return (
        f"{label}: {payload}\n"
        f"store: {path}\n"
        "(instances/signals: call query_artifacts / artifact query — do not invent the full list)"
    )


def cmd_list_classes(args: argparse.Namespace) -> int:
    path = store_from_args(args)
    store = load_store(path)
    names = collect_class_names(store)
    if getattr(args, "inject", False):
        print(format_inject(names, path))
        return 0
    if args.plain:
        print(json.dumps(names, ensure_ascii=False))
    else:
        emit({"ok": True, "classes": names, "store": str(path)})
    return 0


def cmd_classes(args: argparse.Namespace) -> int:
    """Convenience: artifact classes [--inject] [--plain] [--project]."""
    return cmd_list_classes(args)


def cmd_paths(args: argparse.Namespace) -> int:
    store = store_from_args(args)
    pkg = Path(__file__).resolve().parent.parent
    cwd = Path.cwd().resolve()
    project_candidate = cwd / ".artifact" / "store.json"
    emit(
        {
            "store": str(store),
            "ARTIFACT_STORE": os.environ.get("ARTIFACT_STORE"),
            "ARTIFACT_PROJECT": os.environ.get("ARTIFACT_PROJECT"),
            "cwd": str(cwd),
            "project_store_exists": project_candidate.is_file(),
            "project_store_path": str(project_candidate),
            "looks_like_project": _looks_like_project_root(cwd),
            "package": str(pkg),
            "cli": str(Path(__file__).resolve()),
            "harness_inject": str(pkg / "scripts" / "harness_inject.py"),
            "mcp_server": str(pkg / "mcp" / "server.py"),
            "skill_claude": str(Path.home() / ".claude" / "skills" / "artifact"),
            "skill_codex": str(Path.home() / ".agents" / "skills" / "artifact"),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="artifact", description="Artifact store CLI")
    p.add_argument(
        "--store",
        default=None,
        help="Explicit store.json path (overrides ARTIFACT_STORE and project detection)",
    )
    p.add_argument(
        "--project",
        action="store_true",
        help="Use/create ./.artifact/store.json under cwd (project-local store)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("upsert", help="Create or update Name+Reference together")
    u.add_argument("--name", required=True)
    u.add_argument("--reference", default=None, help="Omit to generate art://<uuid>")
    u.add_argument("--kind", default=None, help="Optional real|virtual hint")
    u.add_argument(
        "--match-name",
        action="store_true",
        help="If reference is new but exactly one artifact has this name, update it",
    )
    u.set_defaults(func=cmd_upsert)

    r = sub.add_parser("resolve", help="Find by reference, name, or id")
    r.add_argument("--reference")
    r.add_argument("--name")
    r.add_argument("--id")
    r.set_defaults(func=cmd_resolve)

    a = sub.add_parser("attach", help="Attach or update ontology key")
    a.add_argument("--reference")
    a.add_argument("--name")
    a.add_argument("--id")
    a.add_argument("--key", required=True)
    a.add_argument("--value", required=True, help="JSON or plain string")
    a.set_defaults(func=cmd_attach)

    q = sub.add_parser("query", help="Query by name/reference/class/ontology")
    q.add_argument("--name")
    q.add_argument("--reference")
    q.add_argument("--class", dest="class_name")
    q.add_argument("--key")
    q.add_argument("--value")
    q.set_defaults(func=cmd_query)

    lc = sub.add_parser("list-classes", help="Short class-name list from store")
    lc.add_argument("--plain", action="store_true", help="Print only JSON array")
    lc.add_argument(
        "--inject",
        action="store_true",
        help="Print harness prompt fragment (same as: artifact classes --inject)",
    )
    lc.set_defaults(func=cmd_list_classes)

    cl = sub.add_parser("classes", help="Class list; prefer --inject at turn start")
    cl.add_argument("--plain", action="store_true", help="Print only JSON array")
    cl.add_argument(
        "--inject",
        action="store_true",
        help="Print prompt fragment for per-turn harness injection",
    )
    cl.set_defaults(func=cmd_classes)

    paths = sub.add_parser("paths", help="Print store and install paths")
    paths.set_defaults(func=cmd_paths)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
