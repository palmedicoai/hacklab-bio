from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    InvalidParamsError,
    Part,
    Task,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    completed_task,
    new_artifact,
)
from a2a.utils.errors import ServerError
from agent import (
    JudgeAgent,
    LiveAgent,
)

class JudgeAgentExecutor(AgentExecutor):
    """AgentExecutor for JudgeAgent."""

    def __init__(self) -> None:
        self.agent = JudgeAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        intervention_data = context.get_user_input()
        try:
            result = self.agent.invoke(intervention_data, context.context_id)
            print(f"Final Result ===> {result}")
        except Exception as e:
            print("Error invoking agent: %s", e)
            raise ServerError(error=ValueError(f"Error invoking agent: {e}")) from e

        parts = [
            Part(
                root=TextPart(
                    text=str(result) if result else "failed to verify interventions"
                ),
            )
        ]
        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts, f"judge_{context.task_id}")],
                [context.message],
            )
        )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        return False


class LiveAgentExecutor(AgentExecutor):
    """AgentExecutor for LiveAgent."""

    def __init__(self) -> None:
        self.agent = LiveAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        question = context.get_user_input()
        try:
            result = self.agent.invoke(question, context.context_id)
            print(f"Final Result ===> {result}")
        except Exception as e:
            print("Error invoking agent: %s", e)
            raise ServerError(error=ValueError(f"Error invoking agent: {e}")) from e

        parts = [
            Part(
                root=TextPart(
                    text=(
                        str(result) if result else "failed to answer longevity question"
                    )
                ),
            )
        ]
        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts, f"live_{context.task_id}")],
                [context.message],
            )
        )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        return False
