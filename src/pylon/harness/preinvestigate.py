import asyncio
import shutil
from pathlib import Path

from .analyzers.ctags import extract_symbols, format_symbols
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
}


def check_tools() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in TOOL_REQUIREMENTS}


async def run_pre_investigation(
    repo_path: str,
    notes_path: str,
    keywords: list[str] | None = None,
    skip_phpstan: bool = False,
) -> dict[str, str]:
    """Run all zero-token analyzers and write results to notes directory.

    Returns dict of {filename: content} for each section produced.
    """
    available = check_tools()
    preinvest_dir = Path(notes_path) / ".pylon" / "pre-investigation"
    preinvest_dir.mkdir(parents=True, exist_ok=True)

    sections: dict[str, str] = {}
    tasks = []

    # ctags: symbol index
    if available.get("ctags"):
        tasks.append(("symbols.md", _run_ctags(repo_path)))

    # ripgrep: keyword search
    if available.get("rg") and keywords:
        tasks.append(("keyword-matches.md", _run_ripgrep(repo_path, keywords)))

    # tree-sitter: class hierarchy + models
    tasks.append(("classes.md", _run_tree_sitter_classes(repo_path)))
    tasks.append(("models.md", _run_tree_sitter_models(repo_path)))

    # routes
    tasks.append(("routes.md", _run_routes(repo_path, available.get("php", False))))

    # phpstan (optional, slower)
    if not skip_phpstan and available.get("phpstan"):
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

    # Write combined summary
    summary = _build_summary(sections, available)
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


async def _run_routes(repo_path: str, php_available: bool) -> str:
    routes = await extract_routes(repo_path)
    return format_routes(routes)


async def _run_phpstan(repo_path: str) -> str:
    errors = await run_phpstan(repo_path)
    return format_phpstan(errors)


def _build_summary(sections: dict[str, str], tools: dict[str, bool]) -> str:
    lines = [
        "# Pre-Investigation Summary",
        "",
        "Zero-token static analysis completed. Claude worker should read these",
        "files instead of scanning the codebase from scratch.",
        "",
        "## Tools Used",
        "",
    ]
    for tool, available in tools.items():
        status = "ok" if available else "MISSING"
        lines.append(f"- {tool}: {status}")

    lines.append("")
    lines.append("## Generated Files")
    lines.append("")
    for filename, content in sorted(sections.items()):
        line_count = content.count("\n")
        lines.append(f"- `{filename}` ({line_count} lines)")

    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append("The investigate phase should reference these files for structured")
    lines.append("data (symbols, routes, models, relationships) and only read source")
    lines.append("files when tracing specific logic or behavior.")

    return "\n".join(lines)
