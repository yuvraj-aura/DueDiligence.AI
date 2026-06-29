import logging
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

logger = logging.getLogger("agents.numbers_engine")

class NumbersEngineInput(BaseModel):
    # This represents what we send to the LLM to get the MRR estimation
    value_proposition: str
    target_audience: str
    pricing_model: str
    constraints: str

class NumbersEngineOutput(BaseModel):
    estimated_mrr_usd: float = Field(..., description="Estimated Average Monthly Recurring Revenue (MRR) per user in USD based on value proposition and audience.")
    reasoning: str = Field(..., description="Brief logical explanation justifying this MRR estimate.")

NUMBERS_PROMPT = """
You are a SaaS financial modeling agent.
Given the product's value proposition, target audience, pricing model, and user constraints,
estimate a realistic Average Monthly Recurring Revenue (MRR) per user in USD.

For example:
- Freelance graphic designers using invoicing tools typically pay $10-$20/mo.
- SMBs using marketing automation typically pay $50-$150/mo.
- Enterprise customers pay $500+/mo.

Output ONLY a JSON object containing the estimated MRR and your reasoning:
{
  "estimated_mrr_usd": float,
  "reasoning": "string"
}
"""

def calculate_cac(pricing_model: str, sentiment_delta: float) -> float:
    """
    Computes CAC based on industry benchmarks, adjusted downwards by sentiment delta if positive.
    """
    # Normalize pricing model names
    model = pricing_model.lower().strip()
    if "usage" in model:
        base_cac = 180.0
    elif "freemium" in model:
        base_cac = 310.0
    else:  # Default to flat subscription
        base_cac = 240.0
        
    # Program a function to adjust this base CAC downwards if the sentiment delta is positive
    if sentiment_delta > 0:
        # Reduce CAC by up to 20% if sentiment delta is +1.0
        reduction = min(sentiment_delta * 0.20, 0.20)
        cac = base_cac * (1.0 - reduction)
    else:
        cac = base_cac
        
    return round(cac, 2)

def calculate_ltv(pricing_model: str, estimated_mrr: float) -> float:
    """
    Computes LTV using average MRR and PRD mandated churn rates:
    Freemium: 8%, Flat subscription: 4%, Usage-based: 5%
    """
    model = pricing_model.lower().strip()
    if "freemium" in model:
        churn_rate = 0.08
    elif "usage" in model:
        churn_rate = 0.05
    else:  # flat_subscription
        churn_rate = 0.04
        
    ltv = estimated_mrr / churn_rate
    return round(ltv, 2)

def compute_viability(ltv: float, cac: float) -> tuple[float, str]:
    """
    Calculates viability ratio (LTV / CAC) and assigns status:
    BROKEN (< 3.0), MARGINAL (3.0–5.0), VIABLE (> 5.0)
    """
    if cac <= 0:
        ratio = 99.9
    else:
        ratio = round(ltv / cac, 4)
        
    if ratio < 3.0:
        status = "BROKEN"
    elif ratio <= 5.0:
        status = "MARGINAL"
    else:
        status = "VIABLE"
        
    return ratio, status

# ADK Numbers Agent definition
numbers_agent = LlmAgent(
    name="numbers_engine",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=NUMBERS_PROMPT,
    output_schema=NumbersEngineOutput,
    output_key="numbers_output"
)
