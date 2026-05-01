"""CLI entry point for harness tools.

Usage:
    python -m src.pylon.harness.cli check-tools
    python -m src.pylon.harness.cli pre-investigate /path/to/repo /path/to/notes [keyword1 keyword2 ...]
"""

import asyncio
import sys

from .preinvestigate import check_tools, run_pre_investigation


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.pylon.harness.cli <command> [args]")
        print("Commands: check-tools, pre-investigate")
        sys.exit(1)

    command = sys.argv[1]

    if command == "check-tools":
        tools = check_tools()
        print("Tool availability:")
        all_ok = True
        for tool, available in tools.items():
            status = "ok" if available else "MISSING"
            print(f"  {tool}: {status}")
            if not available:
                all_ok = False
        if not all_ok:
            print("\nRun 'just install-system-tools' to install missing tools.")
            sys.exit(1)
        print("\nAll tools available.")

    elif command == "pre-investigate":
        if len(sys.argv) < 4:
            print("Usage: pre-investigate <repo_path> <notes_path> [keywords...]")
            sys.exit(1)
        repo_path = sys.argv[2]
        notes_path = sys.argv[3]
        keywords = sys.argv[4:] if len(sys.argv) > 4 else None

        print(f"Running pre-investigation on {repo_path}...")
        sections = asyncio.run(run_pre_investigation(
            repo_path=repo_path,
            notes_path=notes_path,
            keywords=keywords,
        ))
        print(f"\nGenerated {len(sections)} files:")
        for filename, content in sorted(sections.items()):
            line_count = content.count("\n")
            print(f"  {filename} ({line_count} lines)")
        print(f"\nOutput: {notes_path}/.pylon/pre-investigation/")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
