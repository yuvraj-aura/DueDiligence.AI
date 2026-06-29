import logging
import json
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.genai import Client
import os

logger = logging.getLogger("agents.critic")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class CriticOutput(BaseModel):
    decision: str = Field(..., description="PASS or KILL: CITATION_FAIL | KILL: SATURATION_NO_DIFFERENTIATOR | KILL: UNIT_ECON_BROKEN")
    kill_reason: str = Field("", description="Detailed explanation if killed, empty if passed.")
    thesis_confirmation: str = Field("", description="One paragraph summarizing why the idea passed and citing competitor source URLs.")

CRITIC_PROMPT = """
You are a Failsafe Critic evaluating a startup thesis confirmation.
All hard deterministic gates have passed. 
Your task is to write a single, high-density "Thesis Confirmation" paragraph.
This paragraph must dynamically summarize why the idea cleared all validation gates, 
and you MUST explicitly cite the competitor URLs provided by the Researcher.

Output ONLY a JSON object:
{
  "decision": "PASS",
  "kill_reason": "",
  "thesis_confirmation": "Your high-density paragraph here citing the sources."
}
"""

def check_citation_failure(competitor_list: list) -> bool:
    """
    Filter 1: Citation Failure.
    Check the Researcher's output. If more than 20% of the listed competitors
    lack a valid source URL, return True (indicating failure).
    """
    if not competitor_list:
        return True  # 100% lack sources if list is empty
        
    invalid_count = 0
    for comp in competitor_list:
        url = comp.get("url", "").strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            invalid_count += 1
            
    pct_invalid = invalid_count / len(competitor_list)
    return pct_invalid > 0.20

def check_saturation_threshold(saturation_score: float, value_proposition: str) -> bool:
    """
    Filter 2: Saturation Threshold.
    If the saturation_score is greater than 8.0 and no unique differentiator
    was flagged by the Gatekeeper in the value proposition, return True (indicating failure).
    """
    if saturation_score <= 8.0:
        return False
        
    # Check for differentiation keywords
    diff_keywords = ["unlike", "unique", "differentiator", "different", "only", "first", "specialized", "tailored", "proprietary", "customized", "automated", "reminders", "dedicated"]
    has_diff = any(kw in value_proposition.lower() for kw in diff_keywords)
    
    return not has_diff

def check_unit_economics(viability_ratio: float) -> bool:
    """
    Filter 3: Unit Economics.
    If the viability_ratio is less than 3.0, return True (indicating failure).
    """
    return viability_ratio < 3.0

async def run_critic_evaluation(context_dict: dict) -> dict:
    """
    Runs the deterministic critic filters in Python before calling the LLM.
    Returns the critic output dictionary.
    """
    gatekeeper_out = context_dict.get("gatekeeper_output", {})
    researcher_out = context_dict.get("researcher_output", {})
    numbers_out = context_dict.get("numbers_output", {})
    
    competitors = researcher_out.get("competitor_list", [])
    saturation_score = researcher_out.get("saturation_score", 0.0)
    value_proposition = gatekeeper_out.get("value_proposition", "")
    viability_ratio = numbers_out.get("viability_ratio", 0.0)
    
    # 1. Deterministic Python validation filters
    if check_citation_failure(competitors):
        logger.warning("Critic: Filter triggered: KILL: CITATION_FAIL")
        return {
            "decision": "KILL: CITATION_FAIL",
            "kill_reason": "More than 20% of listed competitors lack a valid source URL.",
            "thesis_confirmation": ""
        }
        
    if check_saturation_threshold(saturation_score, value_proposition):
        logger.warning("Critic: Filter triggered: KILL: SATURATION_NO_DIFFERENTIATOR")
        return {
            "decision": "KILL: SATURATION_NO_DIFFERENTIATOR",
            "kill_reason": f"Saturation score is {saturation_score} (> 8.0) and no unique differentiator was identified in the value proposition.",
            "thesis_confirmation": ""
        }
        
    if check_unit_economics(viability_ratio):
        logger.warning("Critic: Filter triggered: KILL: UNIT_ECON_BROKEN")
        return {
            "decision": "KILL: UNIT_ECON_BROKEN",
            "kill_reason": f"Viability ratio {viability_ratio} is less than 3.0, indicating broken unit economics.",
            "thesis_confirmation": ""
        }
        
    # 2. If all filters pass, invoke Gemini model
    logger.info("Critic: All filters passed. Invoking Gemini for Thesis Confirmation...")
    
    # Format researcher details for confirmation context
    citations = "\n".join([f"- {c.get('name')}: {c.get('url')}" for c in competitors])
    prompt_input = (
        f"Value Proposition: {value_proposition}\n"
        f"Audience: {gatekeeper_out.get('target_audience')}\n"
        f"Viability Ratio: {viability_ratio}\n"
        f"Competitors & Sources:\n{citations}\n"
    )
    
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            logger.warning("Critic: GEMINI_API_KEY not set. Generating mock pass confirmation.")
            comp_links = ", ".join([f"{c.get('name')} ({c.get('url')})" for c in competitors[:2]])
            return {
                "decision": "PASS",
                "kill_reason": "",
                "thesis_confirmation": f"The idea passed all validation gates. It addresses an underserved market with viable unit economics. Competitors like {comp_links} serve as valid references."
            }
            
        client = Client(api_key=GEMINI_API_KEY)
        from tenacity import retry, stop_after_attempt, wait_exponential
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6), reraise=True)
        def _generate_with_retry():
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{CRITIC_PROMPT}\nInput:\n{prompt_input}",
            )
            
        response = _generate_with_retry()
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        result = json.loads(text)
        return {
            "decision": "PASS",
            "kill_reason": "",
            "thesis_confirmation": result.get("thesis_confirmation", "")
        }
    except Exception as e:
        logger.error(f"Critic: Error running Gemini confirmation: {e}")
        return {
            "decision": "PASS",
            "kill_reason": "",
            "thesis_confirmation": "The idea cleared all gates successfully."
        }

critic_agent = LlmAgent(
    name="critic",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=CRITIC_PROMPT,
    output_schema=CriticOutput,
    output_key="critic_decision"
)
