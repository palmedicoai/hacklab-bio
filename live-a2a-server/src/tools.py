# Standard library imports
import os
import logging
import requests
import xml.etree.ElementTree as ET

# Third-party imports
from dotenv import load_dotenv
import pandas as pd
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
import scholarly
from crewai.tools import tool

# Logger configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY2")

# Initialize Supabase client and OpenAI LLM
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    LLM = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2, api_key=OPENAI_API_KEY)
    logging.info("OpenAI client created successfully.")
except Exception as e:
    logging.error(f"Error initializing clients: {e}")
    exit()


# In-memory cache for DataFrames and last fetch time
_df_interventions_cache = None
_df_studies_cache = None
_last_fetch_time = 0
_CACHE_INTERVAL_SECONDS = 600  # 10 minutes


@tool("query_live_database")
def query_live_database(question: str) -> str:
    """
    Tool to answer questions about longevity intervention data.
    Uses cached DataFrames unless cache is expired (default: 10 minutes).
    Args:
        question (str): The user's query about longevity intervention data.
    Returns:
        str: The tool's answer or an error message.
    """
    import time

    global _df_interventions_cache, _df_studies_cache, _df_supabase_studies_cache, _last_fetch_time

    logging.info("Invoking query_live_database tool.")

    # Check cache validity
    cache_expired = (
        _df_interventions_cache is None
        or _df_studies_cache is None
        or "_df_supabase_studies_cache" not in globals()
        or _df_supabase_studies_cache is None
        or _last_fetch_time is None
        or (time.time() - _last_fetch_time) > _CACHE_INTERVAL_SECONDS
    )

    if cache_expired:
        logging.info("Cache expired or empty. Fetching data from Supabase...")
        try:
            interventions_response = (
                supabase.table("interventions").select("*").execute()
            )
            studies_response = supabase.table("study_extractions").select("*").execute()
            supabase_studies_response = supabase.table("studies").select("*").execute()

            if (
                hasattr(interventions_response, "error")
                and interventions_response.error is not None
            ):
                return f"Error fetching 'interventions': {interventions_response.error}"
            if (
                hasattr(studies_response, "error")
                and studies_response.error is not None
            ):
                return f"Error fetching 'study_extractions': {studies_response.error}"
            if (
                hasattr(supabase_studies_response, "error")
                and supabase_studies_response.error is not None
            ):
                return f"Error fetching 'studies': {supabase_studies_response.error}"

            # Convert data to Pandas DataFrames
            _df_interventions_cache = pd.DataFrame(interventions_response.data)
            # Add url_intervention column based on slug
            if "slug" in _df_interventions_cache.columns:
                _df_interventions_cache["url_intervention"] = (
                    "https://database.longevityadvice.com/#/intervention/"
                    + _df_interventions_cache["slug"].astype(str)
                )
            _df_studies_cache = pd.DataFrame(studies_response.data)
            _df_supabase_studies_cache = pd.DataFrame(supabase_studies_response.data)
            _last_fetch_time = time.time()

            if (
                _df_interventions_cache.empty
                or _df_studies_cache.empty
                or _df_supabase_studies_cache.empty
            ):
                return "Error: One of the tables was downloaded but is empty."

            logging.info(
                f"Loaded data: {len(_df_interventions_cache)} interventions, {len(_df_studies_cache)} study_extractions, {len(_df_supabase_studies_cache)} studies."
            )
        except Exception as e:
            logging.error(f"Exception while downloading data: {e}")
            return f"Exception while downloading data: {e}"
    else:
        logging.info("Using cached DataFrames.")

    logging.info("Step 2: Creating in-memory Pandas agent...")
    try:
        # Pass all dataframes to the agent
        agent = create_pandas_dataframe_agent(
            LLM,
            df=[_df_interventions_cache, _df_studies_cache, _df_supabase_studies_cache],
            verbose=True,
            allow_dangerous_code=True,
        )
        logging.info("Agent created.")
    except Exception as e:
        logging.info(f"Exception while creating agent: {e}")
        return f"Exception while creating agent: {e}"

    logging.info(f"Step 3: Executing query: '{question}'")
    try:
        response = agent.invoke(
            question
            + ", Please provide detailed answers with citations or URLs, and related studies where possible."
        )
        logging.info(f"Agent response: {response}")
        return response["output"]
    except Exception as e:
        logging.info(f"Error during agent execution: {e}")
        return f"Error during agent execution: {e}"


@tool("get_user_personal_data")
def get_user_personal_data(filters: dict):
    """
    Query the 'user_personal_data' table in Supabase to retrieve personal and medical information for users.
    Args:
        filters (dict): Dictionary of filters, e.g. {"email": "user@example.com"}
    Returns:
        list: Query results containing the relevant fields for each user.

    Fields returned:
        - id: User unique identifier (UUID)
        - email: User email address
        - name: User name
        - gender: Gender
        - age: Age
        - chronological_age: Chronological age (years)
        - diabetes: Existing medical condition (Diabetes)
        - albumin: Albumin (g/dL)
        - creatinine: Creatinine (mg/dL)
        - glucose: Glucose (mg/dL)
        - crp: C-reactive protein (mg/L)
        - lymphocyte_percent: Lymphocyte Percent (%)
        - mcv: Mean Cell Volume (fL)
        - rdw: Red Cell Distribution Width (%)
        - alkaline_phosphatase: Alkaline Phosphatase (IU/L)
        - wbc_count: White Blood Cell Count (10^3 cells/µL)
    """
    table = "user_personal_data"
    query = supabase.table(table).select(
        "id, email, name, gender, age, chronological_age, diabetes, albumin, creatinine, glucose, crp, lymphocyte_percent, mcv, rdw, alkaline_phosphatase, wbc_count"
    )
    for key, value in filters.items():
        query = query.eq(key, value)
    response = query.execute()
    return response.data


@tool("pubmed_tool")
def pubmed_tool(query: str, max_results: int = 5) -> str:
    """
    Search PubMed for scientific articles using the NCBI E-utilities API.
    Args:
        query (str): The search term or query string.
        max_results (int): Maximum number of articles to return (default: 5).
    Returns:
        str: A summary of PubMed search results, or an error message.

    Each result includes:
        - PMID
        - Title
        - Authors
        - Journal
        - Year
    """
    logging.info(
        f"Invoking pubmed_tool with query='{query}', max_results={max_results}"
    )
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
    try:
        esearch_resp = requests.get(esearch_url, params=params)
        esearch_resp.raise_for_status()
        ids = esearch_resp.json()["esearchresult"].get("idlist", [])
        if not ids:
            logging.info(f"pubmed_tool: No articles found for query: {query}")
            return f"No articles found for query: {query}"
        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        summary_resp = requests.get(esummary_url, params=summary_params)
        summary_resp.raise_for_status()
        summaries = summary_resp.json()["result"]
        output = []
        for pmid in ids:
            item = summaries.get(pmid, {})
            title = item.get("title", "No title")
            authors = ", ".join([a["name"] for a in item.get("authors", [])])
            journal = item.get("fulljournalname", "")
            year = item.get("pubdate", "")
            output.append(
                f"PMID: {pmid}\nTitle: {title}\nAuthors: {authors}\nJournal: {journal}\nYear: {year}\n---"
            )
        logging.info("pubmed_tool executed successfully")
        return "\n".join(output)
    except Exception as e:
        logging.error(f"Error in pubmed_tool: {e}")
        return f"Error querying PubMed: {e}"


@tool("google_scholar_tool")
def google_scholar_tool(query: str, max_results: int = 5) -> str:
    """
    Search Google Scholar for scientific articles using the scholarly library.
    Note: Google Scholar does not provide an official public API. This tool uses the 'scholarly' Python package.
    Args:
        query (str): The search term or query string.
        max_results (int): Maximum number of articles to return (default: 5).
    Returns:
        str: A summary of Google Scholar search results, or an error message.

    Each result includes:
        - Title
        - Authors
        - Year
        - Venue
    """
    logging.info(
        f"Invoking google_scholar_tool with query='{query}', max_results={max_results}"
    )
    try:
        results = scholarly.search_pubs(query)
        output = []
        for i, pub in enumerate(results):
            if i >= max_results:
                break
            title = getattr(pub, "bib", {}).get("title", "No title")
            author = getattr(pub, "bib", {}).get("author", "")
            year = getattr(pub, "bib", {}).get("pub_year", "")
            venue = getattr(pub, "bib", {}).get("venue", "")
            output.append(
                f"Title: {title}\nAuthors: {author}\nYear: {year}\nVenue: {venue}\n---"
            )
        if not output:
            logging.info(f"google_scholar_tool: No articles found for query: {query}")
            return f"No articles found for query: {query}"
        logging.info("google_scholar_tool executed successfully")
        return "\n".join(output)
    except Exception as e:
        logging.error(f"Error in google_scholar_tool: {e}")
        return f"Error querying Google Scholar: {e}"
