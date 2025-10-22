import uvicorn
import logging
import os
import click
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent import JudgeAgent
from agent_executor import JudgeAgentExecutor
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10006)
def main(host, port):
    try:
        capabilities = AgentCapabilities(streaming=False)
        skill = AgentSkill(
            id="judge_agent",
            name="Agent-as-a-Judge",
            description="Verify integrity and accuracy of longevity interventions, check evidence, compare studies, and mark as OK, Rejected, or for human review.",
            tags=["judge", "verification", "longevity"],
            examples=["Verify intervention integrity and evidence"],
        )
        agent_host_url = (
            os.getenv("HOST_OVERRIDE")
            if os.getenv("HOST_OVERRIDE")
            else f"http://{host}:{port}/"
        )
        agent_card = AgentCard(
            name="Longevity Interventions Judge Agent",
            description="Verify integrity and accuracy of interventions for longevity research. base your judgments on evidence and study comparisons.",
            url=agent_host_url,
            version="1.0.0",
            default_input_modes=JudgeAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=JudgeAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=JudgeAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )


        uvicorn.run(server.build(), host=host, port=port)
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
