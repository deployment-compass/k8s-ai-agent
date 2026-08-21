import logging
import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.agent.prompts import build_system_prompt
from app.agent.tools import ToolRegistry
from app.config import Settings
from app.llm.base import BaseLLMClient, LLMBadRequestError, LLMParseError, LLMMessage
from app.llm.parsing import extract_json_object, validate_structured_output
from app.schemas.chat import ChatResponse, ToolUsage

logger = logging.getLogger(__name__)

_prompted_mode_active = False


def set_prompted_mode(enabled: bool) -> None:
    """Force prompted mode for the rest of the process (used by tests)."""
    global _prompted_mode_active
    _prompted_mode_active = enabled


@dataclass
class AgentResult:
    chat_response: ChatResponse
    tools_used: list[ToolUsage] = field(default_factory=list)


@dataclass
class _StepOutcome:
    final_response: ChatResponse | None = None
    downgrade_requested: bool = False


_CORRECTIVE_MESSAGE = (
    "Your previous reply was not valid JSON matching the required schema. "
    "Respond again with ONLY the corrected JSON object, no other text."
)


class AgentLoop:
    """Runs one chat request: LLM reasoning interleaved with safe tool execution."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        registry: ToolRegistry,
        settings: Settings,
    ):
        self._llm = llm_client
        self._registry = registry
        self._settings = settings

    async def run(self, user_message: str) -> AgentResult:
        mode = self._initial_mode()
        started = time.perf_counter()
        logger.info(
            "Agent loop starting: mode=%s max_tool_iterations=%d",
            mode,
            self._settings.agent_max_tool_iterations,
        )
        messages = [
            LLMMessage.system(build_system_prompt(mode)),
            LLMMessage.user(user_message),
        ]
        tools_used: list[ToolUsage] = []
        first_step = True
        rounds = 0

        while True:
            try:
                outcome = await self._step(messages, mode, tools_used, first_step)
            except LLMBadRequestError:
                if mode == "native" and self._auto_mode():
                    logger.warning(
                        "Provider rejected the tools parameter; "
                        "downgrading to prompted mode for this process."
                    )
                    mode = "prompted"
                    messages = self._fresh_messages(user_message, mode)
                    tools_used.clear()
                    first_step = False
                    continue
                raise
            first_step = False

            if outcome.final_response is not None:
                self._log_complete(started, mode, rounds, len(tools_used), "final answer produced")
                return AgentResult(chat_response=outcome.final_response, tools_used=tools_used)

            if outcome.downgrade_requested:
                logger.warning(
                    "Model returned neither tool calls nor structured output; "
                    "downgrading to prompted mode for this process."
                )
                set_prompted_mode(True)
                mode = "prompted"
                messages = self._fresh_messages(user_message, mode)
                tools_used.clear()
                continue

            rounds += 1
            if rounds >= self._settings.agent_max_tool_iterations:
                logger.warning(
                    "Tool budget reached (%d rounds); forcing final answer.",
                    rounds,
                )
                break

        final = await self._force_final_answer(messages, mode)
        self._log_complete(started, mode, rounds, len(tools_used), "forced after budget")
        return AgentResult(chat_response=final, tools_used=tools_used)

    @staticmethod
    def _log_complete(
        started: float, mode: str, rounds: int, tool_calls: int, outcome: str
    ) -> None:
        logger.info(
            "Agent loop complete: mode=%s rounds=%d tool_calls=%d duration=%.2fs (%s)",
            mode,
            rounds,
            tool_calls,
            time.perf_counter() - started,
            outcome,
        )

    def _initial_mode(self) -> str:
        configured = self._settings.llm_tool_mode.strip().lower()
        if configured == "prompted" or _prompted_mode_active:
            return "prompted"
        return "native"

    def _auto_mode(self) -> bool:
        return self._settings.llm_tool_mode.strip().lower() == "auto"

    def _fresh_messages(self, user_message: str, mode: str) -> list[LLMMessage]:
        return [
            LLMMessage.system(build_system_prompt(mode)),
            LLMMessage.user(user_message),
        ]

    async def _step(
        self,
        messages: list[LLMMessage],
        mode: str,
        tools_used: list[ToolUsage],
        first_step: bool,
    ) -> _StepOutcome:
        if mode == "native":
            response = await self._llm.complete(
                messages, tools=self._registry.definitions()
            )
            if response.tool_calls:
                await self._execute_native_calls(response, messages, tools_used)
                return _StepOutcome()

            parsed = self._try_parse_structured(response.content)
            if parsed is not None:
                return _StepOutcome(final_response=parsed)

            action = _parse_prompted_action(response.content)
            if action is not None:
                return await self._apply_action(action, messages, tools_used)

            if first_step and self._auto_mode():
                return _StepOutcome(downgrade_requested=True)

            return _StepOutcome(final_response=await self._corrective_retry(messages))

        response = await self._llm.complete(messages)
        action = _parse_prompted_action(response.content)
        if action is None:
            return _StepOutcome(final_response=await self._corrective_retry(messages))
        return await self._apply_action(action, messages, tools_used)

    async def _execute_native_calls(
        self,
        response,
        messages: list[LLMMessage],
        tools_used: list[ToolUsage],
    ) -> None:
        messages.append(
            LLMMessage.assistant(content=response.content, tool_calls=response.tool_calls)
        )
        for call in response.tool_calls:
            result = await self._run_tool(call.name, call.arguments, tools_used)
            messages.append(LLMMessage.tool_result(call.id, call.name, result))

    async def _apply_action(
        self,
        action: "_PromptedAction",
        messages: list[LLMMessage],
        tools_used: list[ToolUsage],
    ) -> _StepOutcome:
        if action.kind == "final":
            return _StepOutcome(final_response=action.chat_response)

        result = await self._run_tool(action.tool or "", action.arguments, tools_used)
        messages.append(
            LLMMessage.user(
                f"Tool '{action.tool}' executed. Result:\n{result}\n\n"
                "Respond with your next tool_call JSON or your final_answer JSON."
            )
        )
        return _StepOutcome()

    async def _run_tool(
        self, name: str, arguments: dict, tools_used: list[ToolUsage]
    ) -> str:
        tools_used.append(ToolUsage(tool=name, arguments=arguments))
        return await self._registry.execute(name, arguments)

    async def _corrective_retry(self, messages: list[LLMMessage]) -> ChatResponse:
        logger.warning("Model output failed structured parsing; requesting corrected JSON.")
        response = await self._llm.complete(
            [*messages, LLMMessage.user(_CORRECTIVE_MESSAGE)]
        )
        parsed = self._try_parse_structured(response.content)
        if parsed is None:
            raise LLMParseError(
                "Model failed to produce valid structured output after retry."
            )
        return parsed

    async def _force_final_answer(
        self, messages: list[LLMMessage], mode: str
    ) -> ChatResponse:
        suffix = (
            " Respond ONLY with the final_answer JSON object."
            if mode == "prompted"
            else ""
        )
        messages.append(
            LLMMessage.user(f"Tool budget reached.{suffix} Answer with what you have.")
        )
        response = await self._llm.complete(messages)
        parsed = self._try_parse_structured(response.content)
        if parsed is None:
            action = _parse_prompted_action(response.content)
            if action is not None and action.kind == "final":
                return action.chat_response
            raise LLMParseError(
                "Model failed to produce a final answer after exhausting the tool budget."
            )
        return parsed

    @staticmethod
    def _try_parse_structured(content: str | None) -> ChatResponse | None:
        if not content:
            return None
        try:
            return validate_structured_output(content, ChatResponse)
        except LLMParseError:
            return None


@dataclass
class _PromptedAction:
    kind: str
    tool: str | None = None
    arguments: dict = field(default_factory=dict)
    chat_response: ChatResponse | None = None


def _parse_prompted_action(content: str | None) -> _PromptedAction | None:
    if not content:
        return None
    try:
        data = extract_json_object(content)
    except LLMParseError:
        return None

    action = data.get("action")
    if action == "tool_call":
        tool = data.get("tool")
        if isinstance(tool, str):
            arguments = data.get("arguments")
            return _PromptedAction(
                kind="tool",
                tool=tool,
                arguments=arguments if isinstance(arguments, dict) else {},
            )
        return None

    if action == "final_answer" or "answer" in data:
        try:
            response = ChatResponse(
                answer=str(data.get("answer", "")),
                reasoning_summary=str(data.get("reasoning_summary", "")),
                suggested_next_steps=data.get("suggested_next_steps") or [],
            )
        except (ValidationError, ValueError):
            return None
        return _PromptedAction(kind="final", chat_response=response)

    return None
