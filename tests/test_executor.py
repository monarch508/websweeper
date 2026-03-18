"""Unit tests for the step executor — mock-based, no real browser."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from websweeper.executor import (
    ExecutionError,
    execute_step,
    execute_steps,
    resolve_input,
    resolve_target,
)


class TestResolveTarget:
    def test_id_target(self):
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator

        result = resolve_target(page, {"type": "id", "value": "username"})

        page.locator.assert_called_once_with("#username")
        assert result is locator

    def test_css_target(self):
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator

        result = resolve_target(page, {"type": "css", "value": ".my-class"})

        page.locator.assert_called_once_with(".my-class")
        assert result is locator

    def test_text_target(self):
        page = MagicMock()
        locator = MagicMock()
        page.get_by_text.return_value = locator

        result = resolve_target(page, {"type": "text", "value": "Click me"})

        page.get_by_text.assert_called_once_with("Click me")
        assert result is locator

    def test_role_target(self):
        page = MagicMock()
        locator = MagicMock()
        page.get_by_role.return_value = locator

        result = resolve_target(
            page, {"type": "role", "value": "Submit", "role": "button", "name": "Submit"}
        )

        page.get_by_role.assert_called_once_with("button", name="Submit")
        assert result is locator

    def test_placeholder_target(self):
        page = MagicMock()
        locator = MagicMock()
        page.get_by_placeholder.return_value = locator

        result = resolve_target(page, {"type": "placeholder", "value": "Enter email"})

        page.get_by_placeholder.assert_called_once_with("Enter email")
        assert result is locator

    def test_unknown_target_type_raises(self):
        page = MagicMock()

        with pytest.raises(ExecutionError, match="Unknown target type"):
            resolve_target(page, {"type": "xpath", "value": "//div"})


class TestResolveInput:
    def test_resolves_template_vars(self):
        result = resolve_input("{username}", {"username": "sean"})
        assert result == "sean"

    def test_resolves_multiple_vars(self):
        result = resolve_input(
            "{username}:{password}", {"username": "sean", "password": "secret"}
        )
        assert result == "sean:secret"

    def test_no_template_returns_unchanged(self):
        result = resolve_input("plain text", {"username": "sean"})
        assert result == "plain text"

    def test_no_context_returns_unchanged(self):
        result = resolve_input("{username}", None)
        assert result == "{username}"


class TestExecuteStep:
    @pytest.mark.asyncio
    async def test_fill_step(self):
        page = MagicMock()
        locator = AsyncMock()
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        await execute_step(page, {
            "action": "fill",
            "target": {"type": "id", "value": "email"},
            "input": "test@example.com",
        })

        locator.fill.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_fill_with_template(self):
        page = MagicMock()
        locator = AsyncMock()
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        await execute_step(
            page,
            {
                "action": "fill",
                "target": {"type": "id", "value": "user"},
                "input": "{username}",
            },
            context={"username": "sean"},
        )

        locator.fill.assert_called_once_with("sean")

    @pytest.mark.asyncio
    async def test_click_step(self):
        page = MagicMock()
        locator = AsyncMock()
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        await execute_step(page, {
            "action": "click",
            "target": {"type": "id", "value": "submit"},
        })

        locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_step(self):
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()

        await execute_step(page, {"action": "wait", "wait_ms": 2000})

        page.wait_for_timeout.assert_called_with(2000)

    @pytest.mark.asyncio
    async def test_wait_after(self):
        page = MagicMock()
        locator = AsyncMock()
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        await execute_step(page, {
            "action": "click",
            "target": {"type": "id", "value": "btn"},
            "wait_after": 3000,
        })

        locator.click.assert_called_once()
        page.wait_for_timeout.assert_called_with(3000)

    @pytest.mark.asyncio
    async def test_unknown_action_raises(self):
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()

        with pytest.raises(ExecutionError):
            await execute_step(page, {"action": "fly"})

    @pytest.mark.asyncio
    async def test_failure_wraps_exception(self):
        page = MagicMock()
        locator = AsyncMock()
        locator.click.side_effect = TimeoutError("Element not found")
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        with pytest.raises(ExecutionError, match="Element not found"):
            await execute_step(page, {
                "action": "click",
                "target": {"type": "id", "value": "missing"},
                "description": "Click missing element",
            })


class TestExecuteSteps:
    @pytest.mark.asyncio
    async def test_runs_all_steps(self):
        page = MagicMock()
        locator = AsyncMock()
        page.locator.return_value = locator
        page.wait_for_timeout = AsyncMock()

        steps = [
            {"action": "click", "target": {"type": "id", "value": "btn1"}},
            {"action": "click", "target": {"type": "id", "value": "btn2"}},
            {"action": "click", "target": {"type": "id", "value": "btn3"}},
        ]

        await execute_steps(page, steps)

        assert locator.click.call_count == 3
