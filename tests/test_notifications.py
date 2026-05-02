from unittest.mock import AsyncMock, patch

import pytest

from pylon.notifications import (
    notify_decisions_pending,
    notify_phase_failed,
    notify_pipeline_completed,
    send_slack,
)


@pytest.fixture
def mock_httpx():
    with patch("pylon.notifications.httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client


class TestSendSlack:
    async def test_skips_when_no_webhook_url(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = ""
            await send_slack("test message")
            mock_httpx.post.assert_not_called()

    async def test_sends_when_webhook_configured(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            await send_slack("hello")
            mock_httpx.post.assert_called_once_with(
                "https://hooks.slack.com/test",
                json={"text": "hello"},
            )

    async def test_logs_warning_on_failure(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_httpx.post.side_effect = Exception("connection refused")
            await send_slack("hello")


class TestNotifyDecisionsPending:
    async def test_formats_mrkdwn(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.api_base_url = "http://localhost:8000"
            await notify_decisions_pending(
                slug="ESIGN-42",
                repo="esign",
                assignee="jsovine",
                phase="investigate",
                round_number=1,
                count=3,
            )
            call_args = mock_httpx.post.call_args
            text = call_args[1]["json"]["text"]
            assert "*Pylon*" in text
            assert "3 decisions pending" in text
            assert "ESIGN-42" in text
            assert "@jsovine" in text
            assert "Investigate Round 1" in text
            assert "<http://localhost:8000/tickets/ESIGN-42/decisions|Answer decisions>" in text

    async def test_no_assignee(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.api_base_url = "http://localhost:8000"
            await notify_decisions_pending(
                slug="ESIGN-42", repo="esign", assignee=None,
                phase="plan", round_number=2, count=1,
            )
            text = mock_httpx.post.call_args[1]["json"]["text"]
            assert "@" not in text


class TestNotifyPhaseFailed:
    async def test_truncates_long_error(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            long_error = "x" * 500
            await notify_phase_failed(
                slug="ESIGN-42", repo="esign", phase="implement", error=long_error,
            )
            text = mock_httpx.post.call_args[1]["json"]["text"]
            code_block = text.split("```")[1]
            assert len(code_block) == 200


class TestNotifyPipelineCompleted:
    async def test_with_pr_url(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            await notify_pipeline_completed(
                slug="ESIGN-42", repo="esign", pr_url="https://github.com/org/repo/pull/1",
            )
            text = mock_httpx.post.call_args[1]["json"]["text"]
            assert "pipeline complete" in text
            assert "<https://github.com/org/repo/pull/1|View PR>" in text

    async def test_without_pr_url(self, mock_httpx):
        with patch("pylon.notifications.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            await notify_pipeline_completed(slug="ESIGN-42", repo="esign", pr_url=None)
            text = mock_httpx.post.call_args[1]["json"]["text"]
            assert "View PR" not in text
