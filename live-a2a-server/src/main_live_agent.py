import logging
import os
import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent import LiveAgent
from agent_executor import LiveAgentExecutor
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10007)
def main(host, port):
    try:

        capabilities = AgentCapabilities(streaming=False)
        skill = AgentSkill(
            id="live_agent",
            name="LIVE  Agent",
            description="Answer any question about healthy and longevity interventions, cite studies, and restrict answers to database content.",
            tags=["longevity", "intervention", "database"],
            examples=["List possible longevity interventions with citations"],
        )
        agent_host_url = (
            os.getenv("HOST_OVERRIDE")
            if os.getenv("HOST_OVERRIDE")
            else f"http://{host}:{port}/"
        )
        agent_card = AgentCard(
            name="LIVE  Agent",
            description="Answer questions about Longevity Interventions Verified Evidence (LIVE! Database), cite studies, and restrict answers to database content.",
            url=agent_host_url,
            version="1.0.0",
            default_input_modes=LiveAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=LiveAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=LiveAgentExecutor(),
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
