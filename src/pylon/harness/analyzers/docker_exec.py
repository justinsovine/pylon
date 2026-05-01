"""Run commands inside the Laravel app containers via docker exec.

This gives access to the real PHP environment: correct autoloader, correct
dependencies, correct database connection. Results are more accurate than
running tools against the source files directly.
"""

import asyncio
import json

CONTAINER_NAMES = {
    "esign": "esign-app",
    "onboard": "onboard-app",
    "scriptus-web": "scriptus-app",
}


async def _docker_exec(container: str, command: list[str], timeout: int = 60) -> tuple[str, int]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", container, *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return "", 1
    return stdout.decode(), proc.returncode


async def container_running(repo: str) -> bool:
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return False
    proc = await asyncio.create_subprocess_exec(
        "docker", "inspect", "--format", "{{.State.Running}}", container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip() == "true"


async def artisan_route_list(repo: str) -> list[dict]:
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return []
    output, code = await _docker_exec(container, ["php", "artisan", "route:list", "--json"])
    if code != 0:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return []


async def artisan_model_show(repo: str, model: str) -> dict:
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return {}
    output, code = await _docker_exec(
        container, ["php", "artisan", "model:show", model, "--json"]
    )
    if code != 0:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


async def run_phpstan_in_container(repo: str) -> str:
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return ""
    output, code = await _docker_exec(
        container,
        ["vendor/bin/phpstan", "analyse", "--error-format=json", "--no-progress", "--memory-limit=512M"],
        timeout=120,
    )
    return output


async def run_tests_in_container(repo: str, filter_pattern: str | None = None) -> tuple[str, int]:
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return "", 1
    cmd = ["php", "artisan", "test", "--stop-on-failure"]
    if filter_pattern:
        cmd.extend(["--filter", filter_pattern])
    return await _docker_exec(container, cmd, timeout=300)


async def get_container_env(repo: str, keys: list[str]) -> dict[str, str]:
    """Read specific env vars from the app container."""
    container = CONTAINER_NAMES.get(repo)
    if not container:
        return {}
    result = {}
    for key in keys:
        output, code = await _docker_exec(container, ["printenv", key])
        if code == 0:
            result[key] = output.strip()
    return result


def format_live_routes(routes: list[dict]) -> str:
    if not routes:
        return "# Routes (live)\n\nNo routes found (is the container running?)\n"

    lines = ["# Routes (live from artisan)", "", f"Total: {len(routes)}", ""]
    lines.append("| Method | URI | Action | Middleware |")
    lines.append("|--------|-----|--------|-----------|")
    for r in sorted(routes, key=lambda x: x.get("uri", "")):
        method = r.get("method", "")
        uri = r.get("uri", "")
        action = r.get("action", "")
        middleware = ", ".join(r.get("middleware", [])) if isinstance(r.get("middleware"), list) else str(r.get("middleware", ""))
        lines.append(f"| {method} | `{uri}` | `{action}` | {middleware} |")
    return "\n".join(lines)
