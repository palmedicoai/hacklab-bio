"""
Crew AI-based agents for A2A protocol.

This module defines agent classes for JudgeAgent, LIVE Agent,
pathway analysis, and hypothesis synthesis. Each agent is designed to perform specific
biomedical data tasks using CrewAI and integrates with external tools and APIs.
"""

import os
import logging

from crewai import LLM, Agent, Crew, Task
from crewai.process import Process
from dotenv import load_dotenv
from tools import (
    pubmed_tool,
    query_live_database,
    google_scholar_tool,
    get_user_personal_data,
)


load_dotenv()
logger = logging.getLogger(__name__)


class JudgeAgent:
    """
    Agent-as-a-Judge: Verifies the integrity and accuracy of interventions.
    Reviews studies, evidence, compares data, and marks the result.
    Tools: LIVE Database (NLP to SQL), PubMed, Personal Health Data.
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
            self.model = LLM(model="gemini/gemini-2.5-flash")
        elif os.getenv("GOOGLE_API_KEY"):
            self.model = LLM(
                model="gemini/gemini-2.5-flash",
                api_key=os.getenv("GOOGLE_API_KEY"),
                max_completion_tokens=5000,
            )
        else:
            self.model = LLM(model="gpt-4o")
        self.judge_agent = Agent(
            role="Judge Agent",
            goal="Assess the reliability and biological relevance of studies or datasets about longevity interventions such as drugs, diets, or therapies. Produce a concise, natural-language summary that addresses the question and follows scientific evaluation criteria.",
            backstory=(
                "You are the Judge Agent, a scientific evaluator specializing in longevity and aging research. Your task is to assess the reliability and biological relevance of studies or datasets about longevity interventions such as drugs, diets, or therapies.\n"
                "Instructions: Evaluate the study based on study design quality (controls, sample size, replicates), intervention parameters (dosage, duration, administration, side effects), outcome reliability (lifespan or healthspan effects, statistical significance, reproducibility), biological relevance, and source integrity (peer review, transparency, data availability).\n"
                "Consistency Check – Compare results, dosages, or effects across multiple studies. If multiple studies report similar findings, confidence in the results is higher.\n"
                "Source Reliability – Assess the credibility of the publication or database (peer review, funding transparency, conflict of interest, data availability).\n"
                "Experimental Model – Consider the model organism used and how well results may translate to humans.\n"
                "Reproducibility Evidence – Evaluate whether the results have been replicated in independent studies. Flag findings that appear in a single study without support.\n"
                "Statistics – Check for proper statistical reporting, significance (p-values, effect sizes), and robustness of conclusions.\n"
                "Additional Guidance: Summarize the most consistent evidence-supported dosage or effect range rather than picking a single number if values vary across studies. Provide a clear, plain-language summary as if explaining the credibility and key findings to someone with scientific background but not familiar with the specific study. If critical information is missing, mention it clearly.\n"
                "Behavior Instructions: Be objective, data-driven, and biologically grounded. If critical data is missing or unclear, explicitly note 'insufficient data for evaluation'. Compare findings across studies when possible and reason based on biological logic, known longevity mechanisms, and reproducibility of results."
            ),
            verbose=False,
            allow_delegation=False,
            tools=[pubmed_tool, google_scholar_tool, query_live_database],
            llm=self.model,
            max_steps=2
        )
        self.judge_task = Task(
            description=(
                "If you are given input for an Longevity intervention but no specific scientific papers or datasets search on the LIVE database for relevant studies and after that search each studies on PubMed.\n"
                "Given input from the Automation Agent or a user query, produce a concise, natural-language response or summary that addresses the question.\n"
                "Evaluate the study or dataset using the following criteria: Consistency Check, Source Reliability, Experimental Model, Reproducibility Evidence, and Statistics.\n"
                "Summarize the most consistent evidence-supported dosage or effect range if values vary.\n"
                "If critical information is missing, mention it clearly as 'insufficient data for evaluation'.\n"
                "Be objective, data-driven, and biologically grounded."
            ),
            expected_output=(
                "A clear, plain-language summary of the reliability and biological relevance of the intervention or study, including evidence, key findings, and any missing data."
            ),
            agent=self.judge_agent,
        )
        self.crew = Crew(
            agents=[self.judge_agent],
            tasks=[self.judge_task],
            process=Process.sequential,
            verbose=False,
        )

    def invoke(self, intervention_data, session_id):
        inputs = {"intervention_data": intervention_data, "session_id": session_id}
        return self.crew.kickoff(inputs)

    async def stream(self, intervention_data: dict):
        raise NotImplementedError("Streaming is not supported by CrewAI.")


class LiveAgent:
    """
    Live-Agent: Answers questions about longevity interventions, cites studies, and restricts responses according to the database.
    Tools: LIVE Database (NLP to SQL), PubMed, Personal Health Data.
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
            self.model = LLM(model="gemini-2.5-flash")
        elif os.getenv("GOOGLE_API_KEY"):
            self.model = LLM(
                model="gemini/gemini-2.5-flash",
                api_key=os.getenv("GOOGLE_API_KEY"),
                max_completion_tokens=5000,
            )
        else:
            self.model = LLM(model="gpt-4o")
        self.live_agent = Agent(
            role="Longevity Intervention Expert",
            goal="Answer any question about healthy and longevity interventions, cite studies, and restrict answers to LIVE database content.",
            backstory="You are an expert agent for longevity interventions. You answer questions strictly based on the Longevity Interventions database, PubMed, and personal health data. You always cite which study is good, warn that this is not medical advice, and clarify if the evidence is clinical, trial, or animal-based.",
            verbose=False,
            allow_delegation=False,
            tools=[ query_live_database],
            llm=self.model,
            max_steps=3
        )
        self.live_task = Task(
            description=(
                "Respond to questions about healthy and longevity interventions using only database content. Cite studies, provide a summary of possible interventions, and include links or urls either LIVE database or article. Always warn: 'This is not medical advice. Consult a medical professional.' Clarify if evidence is clinical, trial, or animal-based."
            ),
            expected_output=(
                "A summary of possible longevity interventions, with study citations and links. Includes required warnings."
            ),
            agent=self.live_agent,
        )
        self.crew = Crew(
            agents=[self.live_agent],
            tasks=[self.live_task],
            process=Process.sequential,
            verbose=False,
        )

    def invoke(self, question, session_id):
        inputs = {"user_query": question, "session_id": session_id}
        return self.crew.kickoff(inputs)

    async def stream(self, question: str):
        raise NotImplementedError("Streaming is not supported by CrewAI.")

    def invoke(self, artifacts, session_id):
        """
        Run the orchestrator agent with the given artifacts and session ID.

        Args:
            artifacts (dict): Integrated artifacts from other agents (literature, genomic, pathway, etc.).
            session_id (str): The session identifier.

        Returns:
            str: Well-formed, plausible, and verifiable research hypotheses supported by the integrated artifacts.
        """
        inputs = {"artifacts": artifacts, "session_id": session_id}
        return self.crew.kickoff(inputs)

    async def stream(self, artifacts: dict):
        """
        Streaming is not supported for this agent.
        """
        raise NotImplementedError("Streaming is not supported by CrewAI.")
