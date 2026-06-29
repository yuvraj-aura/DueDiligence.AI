import asyncio
import logging
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from mcp_servers.web_scraper import search_competitors
from mcp_servers.reddit_sentiment import analyze_reddit_sentiment
from mcp_servers.product_signals import get_market_signals

logger = logging.getLogger("agents.researcher")

class CompetitorDetail(BaseModel):
    name: str = Field(..., description="Name of the competitor")
    url: str = Field(..., description="Source URL of the competitor")
    founding_year: int = Field(..., description="Founding year of the competitor")
    review_count: int = Field(..., description="Number of reviews or votes")

class ResearcherOutput(BaseModel):
    saturation_score: float = Field(..., description="Calculated score from 0.00 to 10.00")
    competitor_count: int = Field(..., description="Number of competitors found")
    sentiment_delta: float = Field(..., description="Reddit sentiment delta between -1.0 and +1.0")
    ph_launches_18mo: int = Field(..., description="Product Hunt launches count")
    gh_repos_12mo: int = Field(..., description="GitHub repositories count")
    competitor_list: list[CompetitorDetail] = Field(..., description="List of competitors with URLs, founding years, and review counts")
    summary: str = Field(..., description="Detailed summary explaining the saturation score and cited sources with URLs")
    sentiment_interpretation: str = Field(..., description="A single plain-English interpretation sentence explaining what the Reddit sentiment delta means for market opportunity.")

RESEARCHER_PROMPT = """
You are a precision market intelligence researcher.
Your task is to analyze the gathered market search results and compile a clean summary.

You must ensure that EVERY single competitor, Reddit thread, or search statistic you cite includes its source URL. Unsourced claims are strictly forbidden.

Summarize the opportunities, saturation risk, and customer sentiment for the niche.
For the sentiment_interpretation field, write a single plain-English interpretation sentence explaining what the Reddit sentiment delta means. 
If the delta is negative (e.g., below 0.0), it represents frustrated users (opportunity indicator).
If positive (e.g., above 0.0), it suggests satisfied users (need for a strong differentiator).
Ensure the output JSON strictly matches the requested schema fields.
"""

def compute_saturation_score(
    competitor_count: int,
    ph_launches_18mo: int,
    gh_repos_12mo: int,
    sentiment_delta: float
) -> float:
    """
    Deterministically computes the saturation score between 0.0 and 10.0
    based on competitor density, recent launch activity, and Reddit community sentiment.
    """
    # Competitor density: 0–4 points
    comp_score = min(competitor_count / 10, 1.0) * 4.0

    # Recent market activity: 0–3 points
    activity_score = min((ph_launches_18mo + gh_repos_12mo) / 30, 1.0) * 3.0

    # Sentiment: negative sentiment = more saturated / frustrated market = higher score
    # Positive sentiment = underserved, eager market = lower score
    sentiment_score = (1.0 - ((sentiment_delta + 1.0) / 2.0)) * 3.0

    return round(comp_score + activity_score + sentiment_score, 2)

async def gather_market_data(niche_slug: str) -> dict:
    """
    Runs the custom scraping MCP tools in parallel using asyncio.gather.
    Then calculates the market saturation score.
    """
    logger.info(f"Researcher: Executing custom MCP tools in parallel for '{niche_slug}'...")
    
    # Run SerpAPI scraper, Reddit sentiment analyzer, and PH/GitHub signals concurrently
    competitors_task = search_competitors(niche_slug)
    sentiment_task = analyze_reddit_sentiment(niche_slug)
    signals_task = get_market_signals(niche_slug)
    
    competitors, sentiment, signals = await asyncio.gather(
        competitors_task,
        sentiment_task,
        signals_task
    )
    
    competitor_count = len(competitors)
    ph_launches = signals.get("ph_launches_18mo", 0)
    gh_repos = signals.get("gh_repos_12mo", 0)
    
    saturation_score = compute_saturation_score(
        competitor_count=competitor_count,
        ph_launches_18mo=ph_launches,
        gh_repos_12mo=gh_repos,
        sentiment_delta=sentiment
    )
    
    logger.info(f"Researcher: Parallel gathering complete. Saturation Score: {saturation_score}")
    
    return {
        "saturation_score": saturation_score,
        "competitor_count": competitor_count,
        "sentiment_delta": sentiment,
        "ph_launches_18mo": ph_launches,
        "gh_repos_12mo": gh_repos,
        "competitor_list": competitors,
        "signals_sources": signals.get("sources", {})
    }

# ADK Researcher Agent definition
researcher_agent = LlmAgent(
    name="researcher",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=RESEARCHER_PROMPT,
    output_schema=ResearcherOutput,
    output_key="researcher_output"
)
