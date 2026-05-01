import asyncio
import json
from dataclasses import dataclass


@dataclass
class PhpStanError:
    file: str
    line: int
    message: str
    level: str


async def run_phpstan(repo_path: str) -> list[PhpStanError]:
    proc = await asyncio.create_subprocess_exec(
        "phpstan", "analyse",
        "--error-format=json",
        "--no-progress",
        "--memory-limit=512M",
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    errors = []
    try:
        data = json.loads(stdout.decode())
        for file_path, file_errors in data.get("files", {}).items():
            for err in file_errors.get("messages", []):
                errors.append(PhpStanError(
                    file=file_path,
                    line=err.get("line", 0),
                    message=err.get("message", ""),
                    level=str(err.get("level", "")),
                ))
    except json.JSONDecodeError:
        pass

    return errors


def format_phpstan(errors: list[PhpStanError]) -> str:
    if not errors:
        return "# PHPStan\n\nNo errors found.\n"

    lines = ["# PHPStan Errors", "", f"Total: {len(errors)}", ""]
    by_file: dict[str, list[PhpStanError]] = {}
    for e in errors:
        by_file.setdefault(e.file, []).append(e)

    for file_path in sorted(by_file):
        lines.append(f"## {file_path}")
        for e in sorted(by_file[file_path], key=lambda x: x.line):
            lines.append(f"- L{e.line}: {e.message}")
        lines.append("")

    return "\n".join(lines)
