import asyncio
import json
from dataclasses import dataclass


@dataclass
class GrepMatch:
    file: str
    line: int
    text: str


async def search(repo_path: str, pattern: str, globs: list[str] | None = None) -> list[GrepMatch]:
    args = [
        "rg",
        "--json",
        "--max-count", "5",  # max matches per file
        "--max-filesize", "100K",
    ]
    if globs:
        for g in globs:
            args.extend(["--glob", g])
    args.append(pattern)

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    matches = []
    for line in stdout.decode().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "match":
                data = entry["data"]
                matches.append(GrepMatch(
                    file=data["path"]["text"],
                    line=data["line_number"],
                    text=data["lines"]["text"].strip(),
                ))
        except (json.JSONDecodeError, KeyError):
            continue

    return matches


async def find_relevant_files(
    repo_path: str,
    keywords: list[str],
) -> dict[str, list[GrepMatch]]:
    results = {}
    tasks = [search(repo_path, kw, globs=["*.php"]) for kw in keywords]
    task_results = await asyncio.gather(*tasks)
    for kw, matches in zip(keywords, task_results):
        if matches:
            results[kw] = matches
    return results


def format_grep_results(results: dict[str, list[GrepMatch]]) -> str:
    lines = ["# Keyword Search Results", ""]
    for keyword, matches in results.items():
        lines.append(f"## `{keyword}` ({len(matches)} matches)")
        lines.append("")
        for m in matches:
            lines.append(f"- {m.file}:{m.line} -- `{m.text[:120]}`")
        lines.append("")
    return "\n".join(lines)
