import asyncio
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Route:
    method: str
    uri: str
    action: str
    middleware: list[str]
    file: str
    line: int


async def extract_routes(repo_path: str) -> list[Route]:
    proc = await asyncio.create_subprocess_exec(
        "php", "artisan", "route:list", "--json",
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        return await _extract_routes_static(repo_path)

    import json
    routes = []
    try:
        data = json.loads(stdout.decode())
        for r in data:
            routes.append(Route(
                method=r.get("method", ""),
                uri=r.get("uri", ""),
                action=r.get("action", ""),
                middleware=r.get("middleware", []) if isinstance(r.get("middleware"), list) else [],
                file="",
                line=0,
            ))
    except json.JSONDecodeError:
        return await _extract_routes_static(repo_path)

    return routes


async def _extract_routes_static(repo_path: str) -> list[Route]:
    """Fallback: parse route files with regex when artisan isn't available."""
    route_pattern = re.compile(
        r"Route::(get|post|put|patch|delete|any|match)\(\s*['\"]([^'\"]+)['\"]"
        r".*?[\[,]\s*['\"]?([A-Za-z\\@]+)",
        re.DOTALL,
    )

    routes_dir = Path(repo_path) / "routes"
    if not routes_dir.exists():
        return []

    routes = []
    for route_file in routes_dir.glob("*.php"):
        content = route_file.read_text(errors="replace")
        for i, line_text in enumerate(content.split("\n"), 1):
            match = route_pattern.search(line_text)
            if match:
                routes.append(Route(
                    method=match.group(1).upper(),
                    uri=match.group(2),
                    action=match.group(3),
                    middleware=[],
                    file=str(route_file.relative_to(repo_path)),
                    line=i,
                ))

    return routes


def format_routes(routes: list[Route]) -> str:
    lines = ["# Routes", "", f"Total: {len(routes)}", ""]
    lines.append("| Method | URI | Action | Middleware |")
    lines.append("|--------|-----|--------|-----------|")
    for r in sorted(routes, key=lambda x: x.uri):
        mw = ", ".join(r.middleware) if r.middleware else "-"
        loc = f" ({r.file}:{r.line})" if r.file else ""
        lines.append(f"| {r.method} | `{r.uri}` | `{r.action}`{loc} | {mw} |")
    return "\n".join(lines)
