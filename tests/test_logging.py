import json
import logging

import pytest

from app.agent.tools import ToolRegistry
from app.config import Settings, settings
from app.logging_setup import APP_LOGGER_ROOT, configure_logging
from app.schemas.chat import ChatRequest
from app.services import chat_service


@pytest.fixture(autouse=True)
def restore_log_levels():
    yield
    logging.getLogger(APP_LOGGER_ROOT).setLevel(logging.NOTSET)


class StubK8s:
    async def get_pods(self, namespace):
        from app.schemas.kubernetes import PodInfo, PodListResponse

        return PodListResponse(
            items=[
                PodInfo(
                    name="backend-abc",
                    namespace=namespace,
                    status="Running",
                    ready=True,
                    restart_count=0,
                )
            ]
        )

    async def get_deployments(self, namespace):
        raise NotImplementedError

    async def get_deployment(self, namespace, name):
        raise NotImplementedError

    async def get_services(self, namespace):
        raise NotImplementedError

    async def get_service(self, namespace, name):
        raise NotImplementedError

    async def get_pod_logs(self, namespace, pod_name):
        return "log line"

    async def get_events(self, namespace):
        return []


def _settings(**overrides) -> Settings:
    defaults = {
        "agent_log_enabled": True,
        "agent_log_level": "INFO",
    }
    return Settings(**{**defaults, **overrides})


def test_enabled_sets_configured_level():
    configure_logging(_settings(agent_log_level="DEBUG"))

    assert logging.getLogger(APP_LOGGER_ROOT).level == logging.DEBUG


def test_invalid_level_falls_back_to_info():
    configure_logging(_settings(agent_log_level="NOT_A_LEVEL"))

    assert logging.getLogger(APP_LOGGER_ROOT).level == logging.INFO


def test_disabled_caps_at_error():
    configure_logging(_settings(agent_log_enabled=False))

    assert logging.getLogger(APP_LOGGER_ROOT).level == logging.ERROR


def test_settings_parse_env_style_values():
    parsed = Settings(agent_log_enabled="false", agent_log_level="debug")

    assert parsed.agent_log_enabled is False
    assert parsed.agent_log_level == "debug"


@pytest.mark.asyncio
async def test_tool_call_logged_at_info_without_result_body(caplog):
    configure_logging(_settings())
    registry = ToolRegistry(StubK8s(), settings)

    with caplog.at_level(logging.INFO, logger=APP_LOGGER_ROOT):
        await registry.execute("get_pods", {"namespace": "backend"})

    info_text = "\n".join(r.message for r in caplog.records if r.levelno == logging.INFO)
    assert "Tool call: get_pods" in info_text
    assert "'namespace': 'backend'" in info_text.replace('"', "'")
    assert "status=ok" in info_text
    assert '"items"' not in info_text


@pytest.mark.asyncio
async def test_result_preview_only_at_debug(caplog):
    configure_logging(_settings(agent_log_level="DEBUG"))
    registry = ToolRegistry(StubK8s(), settings)

    with caplog.at_level(logging.DEBUG, logger=APP_LOGGER_ROOT):
        result = await registry.execute("get_pods", {"namespace": "backend"})

    debug_text = "\n".join(r.message for r in caplog.records if r.levelno == logging.DEBUG)
    assert "Tool result preview" in debug_text
    assert result[:50] in debug_text


@pytest.mark.asyncio
async def test_unknown_tool_rejection_logged(caplog):
    configure_logging(_settings())
    registry = ToolRegistry(StubK8s(), settings)

    with caplog.at_level(logging.INFO, logger=APP_LOGGER_ROOT):
        await registry.execute("delete_namespace", {})

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("unknown tool 'delete_namespace'" in m for m in warnings)


@pytest.mark.asyncio
async def test_disabled_logging_suppresses_tool_activity(caplog):
    configure_logging(_settings(agent_log_enabled=False))
    registry = ToolRegistry(StubK8s(), settings)

    await registry.execute("get_pods", {"namespace": "backend"})

    assert caplog.records == []


@pytest.mark.asyncio
async def test_agent_loop_lifecycle_logged(caplog):
    from app.llm.mock import MockLLMClient

    configure_logging(_settings())
    chat_service.set_llm_client(MockLLMClient())

    try:
        with caplog.at_level(logging.INFO, logger=APP_LOGGER_ROOT):
            await chat_service.handle_chat(ChatRequest(message="why is backend broken?"))
    finally:
        chat_service.set_llm_client(None)

    info_text = "\n".join(r.message for r in caplog.records if r.levelno == logging.INFO)
    assert "Chat request received" in info_text
    assert "Agent loop starting: mode=native" in info_text
    assert "Agent loop complete" in info_text
