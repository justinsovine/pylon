import asyncio
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Symbol:
    name: str
    kind: str
    file: str
    line: int
    scope: str | None = None


async def extract_symbols(repo_path: str) -> list[Symbol]:
    proc = await asyncio.create_subprocess_exec(
        "ctags",
        "--output-format=json",
        "--languages=PHP",
        "--kinds-PHP=cfimd",  # classes, functions, interfaces, methods, constants
        "--fields=+nS",  # line number + scope
        "-R",
        "app/",
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    symbols = []
    for line in stdout.decode().strip().split("\n"):
        if not line:
            continue
        try:
            tag = json.loads(line)
            symbols.append(Symbol(
                name=tag.get("name", ""),
                kind=tag.get("kind", ""),
                file=tag.get("path", ""),
                line=tag.get("line", 0),
                scope=tag.get("scope", None),
            ))
        except json.JSONDecodeError:
            continue

    return symbols


def format_symbols(symbols: list[Symbol]) -> str:
    lines = ["# Symbol Index", ""]

    by_kind: dict[str, list[Symbol]] = {}
    for s in symbols:
        by_kind.setdefault(s.kind, []).append(s)

    kind_labels = {
        "class": "Classes",
        "interface": "Interfaces",
        "method": "Methods",
        "function": "Functions",
        "define": "Constants",
    }

    for kind in ["class", "interface", "function", "method"]:
        group = by_kind.get(kind, [])
        if not group:
            continue
        label = kind_labels.get(kind, kind)
        lines.append(f"## {label} ({len(group)})")
        lines.append("")
        for s in sorted(group, key=lambda x: (x.file, x.line)):
            scope = f" ({s.scope})" if s.scope else ""
            lines.append(f"- `{s.name}`{scope} -- {s.file}:{s.line}")
        lines.append("")

    return "\n".join(lines)
