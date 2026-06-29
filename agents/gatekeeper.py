from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from pydantic import BaseModel, Field

class GatekeeperOutput(BaseModel):
    niche_slug: str = Field(..., description="kebab-case-niche-label-max-5-words")
    value_proposition: str = Field(..., description="One sentence, max 40 words, subject-verb-object format")
    target_audience: str = Field(..., description="Specific descriptor. No vague terms.")
    pricing_model: str = Field(..., description="usage_based | flat_subscription | freemium")
    falsifiable_assumptions: list[str] = Field(..., description="Three assumptions that market research must confirm or deny")
    runway_weeks: int = Field(..., description="runway in weeks")
    marketing_budget_usd: int = Field(..., description="marketing budget in USD")

GATEKEEPER_PROMPT = """
You are a precision input normalizer for a market validation system.
Given raw user input, output ONLY a valid JSON object with these exact fields:

{
  "niche_slug": "kebab-case-niche-label-max-5-words",
  "value_proposition": "One sentence, max 40 words, subject-verb-object format",
  "target_audience": "Specific descriptor. No vague terms like 'businesses' or 'users'.",
  "pricing_model": "usage_based | flat_subscription | freemium",
  "falsifiable_assumptions": [
    "Assumption 1 that market research must confirm or deny",
    "Assumption 2",
    "Assumption 3"
  ],
  "runway_weeks": integer,
  "marketing_budget_usd": integer
}

Return ONLY the JSON. No preamble. No explanation. No markdown.
"""

gatekeeper_agent = LlmAgent(
    name="gatekeeper",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=GATEKEEPER_PROMPT,
    output_schema=GatekeeperOutput,
    output_key="gatekeeper_output"
)

class PreFlightOutput(BaseModel):
    passed: bool = Field(..., description="True if the thesis is coherent and specific enough, False otherwise")
    reason: str = Field(..., description="A detailed explanation if passed is False, otherwise empty string")

PRE_FLIGHT_PROMPT = """
You are a startup thesis pre-flight gatekeeper.
Given a startup thesis, target micro-niche, and monetization model, evaluate if they are coherent and specific.
If the thesis is too vague (e.g. "an AI app", "a website for dogs") or fundamentally nonsensical, output passed=False and provide a clear, actionable reason.
If it is specific enough to run market research on, output passed=True and reason="".
Return ONLY valid JSON.
"""

pre_flight_agent = LlmAgent(
    name="pre_flight_gatekeeper",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=PRE_FLIGHT_PROMPT,
    output_schema=PreFlightOutput,
    output_key="pre_flight_output"
)

