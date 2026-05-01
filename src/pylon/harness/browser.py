"""Browser testing harness using Playwright.

Runs headless Chromium against the live app containers via the edoc network.
Used by the test phase to verify features work in a real browser after
implementation.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BrowserTestResult:
    name: str
    passed: bool
    url: str
    duration_ms: int
    screenshot: str | None = None
    error: str | None = None
    console_errors: list[str] = field(default_factory=list)


@dataclass
class BrowserTestSuite:
    results: list[BrowserTestResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


APP_URLS = {
    "esign": "https://dev.esign.test",
    "onboard": "https://dev.onboard.test",
    "scriptus-web": "https://dev.scriptus.test",
}


async def run_browser_tests(
    repo: str,
    test_steps: list[dict],
    screenshots_dir: str | None = None,
    credentials: dict | None = None,
) -> BrowserTestSuite:
    """Execute browser test steps against a live app.

    test_steps format:
    [
        {
            "name": "Login as admin",
            "action": "login",
            "url": "/login",
            "credentials": {"email": "...", "password": "..."},
        },
        {
            "name": "Navigate to worker profiles",
            "action": "navigate",
            "url": "/admin/workers",
            "assert_text": "Worker Profiles",
        },
        {
            "name": "Export button exists",
            "action": "assert_element",
            "selector": "[data-testid='export-btn']",
        },
        {
            "name": "Click export",
            "action": "click",
            "selector": "[data-testid='export-btn']",
            "wait_for": "download",
        },
    ]
    """
    from playwright.async_api import async_playwright

    base_url = APP_URLS.get(repo, "")
    if not base_url:
        return BrowserTestSuite(results=[BrowserTestResult(
            name="setup",
            passed=False,
            url="",
            duration_ms=0,
            error=f"Unknown repo: {repo}",
        )])

    suite = BrowserTestSuite()
    screenshots_path = Path(screenshots_dir) if screenshots_dir else None
    if screenshots_path:
        screenshots_path.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors"],
        )
        context = await browser.new_context(
            base_url=base_url,
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        console_errors: list[str] = []
        page.on("console", lambda msg: (
            console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type == "error" else None
        ))

        if credentials:
            result = await _do_login(page, base_url, credentials, screenshots_path)
            suite.results.append(result)
            if not result.passed:
                await browser.close()
                return suite

        for step in test_steps:
            if step.get("action") == "login":
                continue

            import time
            start = time.monotonic()

            try:
                result = await _execute_step(page, step, base_url, screenshots_path)
                result.duration_ms = int((time.monotonic() - start) * 1000)
                result.console_errors = list(console_errors)
                console_errors.clear()
            except Exception as e:
                result = BrowserTestResult(
                    name=step.get("name", "unnamed"),
                    passed=False,
                    url=page.url,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=str(e),
                )
                if screenshots_path:
                    screenshot_file = screenshots_path / f"error-{step.get('name', 'unnamed')}.png"
                    await page.screenshot(path=str(screenshot_file))
                    result.screenshot = str(screenshot_file)

            suite.results.append(result)

            if not result.passed and step.get("stop_on_fail", True):
                break

        await browser.close()

    return suite


async def _do_login(page, base_url: str, credentials: dict, screenshots_path: Path | None) -> BrowserTestResult:
    import time
    start = time.monotonic()
    try:
        await page.goto("/login")
        await page.fill('input[name="email"]', credentials["email"])
        await page.fill('input[name="password"]', credentials["password"])
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle", timeout=10000)

        if "/login" in page.url:
            return BrowserTestResult(
                name="login",
                passed=False,
                url=page.url,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="Still on login page after submit",
            )

        return BrowserTestResult(
            name="login",
            passed=True,
            url=page.url,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        return BrowserTestResult(
            name="login",
            passed=False,
            url=page.url if page else "",
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(e),
        )


async def _execute_step(page, step: dict, base_url: str, screenshots_path: Path | None) -> BrowserTestResult:
    action = step.get("action", "")
    name = step.get("name", "unnamed")

    if action == "navigate":
        url = step.get("url", "/")
        await page.goto(url)
        await page.wait_for_load_state("networkidle", timeout=15000)

        if step.get("assert_text"):
            content = await page.content()
            if step["assert_text"] not in content:
                return BrowserTestResult(
                    name=name, passed=False, url=page.url, duration_ms=0,
                    error=f"Expected text '{step['assert_text']}' not found",
                )

    elif action == "click":
        selector = step.get("selector", "")
        await page.click(selector, timeout=5000)
        if step.get("wait_for") == "navigation":
            await page.wait_for_load_state("networkidle", timeout=15000)
        elif step.get("wait_for") == "download":
            async with page.expect_download(timeout=30000):
                pass

    elif action == "assert_element":
        selector = step.get("selector", "")
        element = await page.query_selector(selector)
        if not element:
            return BrowserTestResult(
                name=name, passed=False, url=page.url, duration_ms=0,
                error=f"Element '{selector}' not found",
            )

    elif action == "fill":
        await page.fill(step.get("selector", ""), step.get("value", ""))

    elif action == "assert_url":
        expected = step.get("url_contains", "")
        if expected not in page.url:
            return BrowserTestResult(
                name=name, passed=False, url=page.url, duration_ms=0,
                error=f"URL '{page.url}' does not contain '{expected}'",
            )

    elif action == "wait":
        await page.wait_for_timeout(step.get("ms", 1000))

    if screenshots_path and step.get("screenshot", False):
        screenshot_file = screenshots_path / f"{name}.png"
        await page.screenshot(path=str(screenshot_file))

    return BrowserTestResult(name=name, passed=True, url=page.url, duration_ms=0)


def format_browser_results(suite: BrowserTestSuite) -> str:
    lines = [
        "# Browser Test Results",
        "",
        f"Passed: {suite.passed}/{suite.total}",
        "",
    ]

    for r in suite.results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"- [{status}] {r.name} ({r.duration_ms}ms)")
        if r.error:
            lines.append(f"  Error: {r.error}")
        if r.console_errors:
            lines.append(f"  Console errors: {len(r.console_errors)}")
            for ce in r.console_errors[:5]:
                lines.append(f"    {ce}")
        if r.screenshot:
            lines.append(f"  Screenshot: {r.screenshot}")

    return "\n".join(lines)
