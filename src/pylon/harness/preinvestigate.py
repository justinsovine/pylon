import asyncio
import shutil
from pathlib import Path

from .analyzers.ctags import extract_symbols, format_symbols
from .analyzers.docker_exec import (
    artisan_route_list,
    container_running,
    format_live_routes,
    run_phpstan_in_container,
)
from .analyzers.phpstan import format_phpstan, run_phpstan
from .analyzers.php_routes import extract_routes, format_routes
from .analyzers.ripgrep import find_relevant_files, format_grep_results
from .analyzers.tree_sitter_php import (
    extract_classes,
    extract_models,
    format_classes,
    format_models,
)

TOOL_REQUIREMENTS = {
    "ctags": "universal-ctags",
    "rg": "ripgrep",
    "php": "php-cli",
    "phpstan": "phpstan",
    "docker": "docker",
}


def check_tools() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in TOOL_REQUIREMENTS}


async def run_pre_investigation(
    repo_path: str,
    notes_path: str,
    repo_name: str | None = None,
    keywords: list[str] | None = None,
    skip_phpstan: bool = False,
) -> dict[str, str]:
    """Run all zero-token analyzers and write results to notes directory.

    When the app container is running on the edoc network, uses live data
    (artisan route:list, phpstan inside container). Falls back to static
    analysis when containers aren't available.
    """
    available = check_tools()
    preinvest_dir = Path(notes_path) / ".pylon" / "pre-investigation"
    preinvest_dir.mkdir(parents=True, exist_ok=True)

    live = False
    if repo_name and available.get("docker"):
        live = await container_running(repo_name)

    sections: dict[str, str] = {}
    tasks = []

    # ctags: symbol index
    if available.get("ctags"):
        tasks.append(("symbols.md", _run_ctags(repo_path)))

    # ripgrep: keyword search
    if available.get("rg") and keywords:
        tasks.append(("keyword-matches.md", _run_ripgrep(repo_path, keywords)))

    # tree-sitter: class hierarchy + models (always from source, more detailed than artisan)
    tasks.append(("classes.md", _run_tree_sitter_classes(repo_path)))
    tasks.append(("models.md", _run_tree_sitter_models(repo_path)))

    # routes: live from artisan if container running, static fallback otherwise
    if live and repo_name:
        tasks.append(("routes.md", _run_live_routes(repo_name)))
    else:
        tasks.append(("routes.md", _run_routes(repo_path)))

    # phpstan: run inside container if available, local fallback otherwise
    if not skip_phpstan:
        if live and repo_name:
            tasks.append(("phpstan.md", _run_live_phpstan(repo_name)))
        elif available.get("phpstan"):
            tasks.append(("phpstan.md", _run_phpstan(repo_path)))

    results = await asyncio.gather(
        *[coro for _, coro in tasks],
        return_exceptions=True,
    )

    for (filename, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            content = f"# Error\n\nFailed: {result}\n"
        else:
            content = result
        sections[filename] = content
        (preinvest_dir / filename).write_text(content)

    summary = _build_summary(sections, available, live, repo_name)
    (preinvest_dir / "summary.md").write_text(summary)
    sections["summary.md"] = summary

    return sections


async def _run_ctags(repo_path: str) -> str:
    symbols = await extract_symbols(repo_path)
    return format_symbols(symbols)


async def _run_ripgrep(repo_path: str, keywords: list[str]) -> str:
    results = await find_relevant_files(repo_path, keywords)
    return format_grep_results(results)


async def _run_tree_sitter_classes(repo_path: str) -> str:
    classes = extract_classes(repo_path)
    return format_classes(classes)


async def _run_tree_sitter_models(repo_path: str) -> str:
    models = extract_models(repo_path)
    return format_models(models)


async def _run_routes(repo_path: str) -> str:
    routes = await extract_routes(repo_path)
    return format_routes(routes)


async def _run_live_routes(repo_name: str) -> str:
    routes = await artisan_route_list(repo_name)
    return format_live_routes(routes)


async def _run_phpstan(repo_path: str) -> str:
    errors = await run_phpstan(repo_path)
    return format_phpstan(errors)


async def _run_live_phpstan(repo_name: str) -> str:
    import json
    output = await run_phpstan_in_container(repo_name)
    if not output:
        return "# PHPStan (live)\n\nNo output (container error?)\n"
    try:
        data = json.loads(output)
        from .analyzers.phpstan import PhpStanError, format_phpstan
        errors = []
        for file_path, file_errors in data.get("files", {}).items():
            for err in file_errors.get("messages", []):
                errors.append(PhpStanError(
                    file=file_path,
                    line=err.get("line", 0),
                    message=err.get("message", ""),
                    level=str(err.get("level", "")),
                ))
        result = format_phpstan(errors)
        return result.replace("# PHPStan", "# PHPStan (live from container)")
    except json.JSONDecodeError:
        return f"# PHPStan (live)\n\nRaw output:\n```\n{output[:2000]}\n```\n"


def _build_summary(
    sections: dict[str, str],
    tools: dict[str, bool],
    live: bool,
    repo_name: str | None,
) -> str:
    lines = [
        "# Pre-Investigation Summary",
        "",
    ]

    if live:
        lines.append(f"Container `{repo_name}` is running. Used live data where possible.")
        lines.append("Routes and PHPStan results are from the actual app environment.")
    else:
        lines.append("App container not running. Used static analysis only.")
        lines.append("Start the app with `sail up -d` for live routes and PHPStan.")

    lines.extend([
        "",
        "## Tools",
        "",
    ])
    for tool, avail in tools.items():
        status = "ok" if avail else "MISSING"
        lines.append(f"- {tool}: {status}")

    lines.extend([
        "",
        f"## Generated Files ({len(sections)})",
        "",
    ])
    for filename, content in sorted(sections.items()):
        line_count = content.count("\n")
        lines.append(f"- `{filename}` ({line_count} lines)")

    lines.extend([
        "",
        "## For the investigate phase",
        "",
        "Read these files for structured data. Only open raw PHP files when",
        "tracing specific logic, validation rules, or complex behavior.",
    ])

    if live:
        lines.extend([
            "",
            "## Live capabilities available",
            "",
            "- `docker exec` into app container for artisan commands",
            "- Mailpit API for email verification",
            "- Browser testing via Playwright against live app",
        ])

    return "\n".join(lines)
