#!/usr/bin/env python3
"""Print short class-name list for per-turn harness injection.

Prefer:  artifact classes --inject
Equiv:   python3 harness_inject.py --format prompt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from artifact_cli import (  # noqa: E402
    collect_class_names,
    format_inject,
    load_store,
    resolve_store_path,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Emit Artifact class-name inject payload")
    p.add_argument(
        "--format",
        choices=("json", "text", "prompt"),
        default="prompt",
        help="json / text / prompt (default prompt = inject fragment)",
    )
    p.add_argument("--label", default="Artifact classes (names only)")
    p.add_argument("--store", default=None, help="Explicit store.json path")
    p.add_argument(
        "--project",
        action="store_true",
        help="Use/create ./.artifact/store.json under cwd",
    )
    args = p.parse_args()

    path = resolve_store_path(
        project=args.project,
        explicit=args.store,
        create_project=args.project,
    )
    store = load_store(path)
    names = collect_class_names(store)

    if args.format == "json":
        print(json.dumps({"classes": names, "store": str(path)}, ensure_ascii=False))
    elif args.format == "text":
        for n in names:
            print(n)
    else:
        print(format_inject(names, path, label=args.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
