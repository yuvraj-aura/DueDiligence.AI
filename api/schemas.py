from pydantic import BaseModel, Field
from typing import Optional, List

class PreValidateRequest(BaseModel):
    thesis: str = Field(..., min_length=80, description="Stated startup idea or thesis, minimum 80 characters")
    target_micro_niche: str = Field(..., description="Target micro-niche name")
    monetization_model: List[str] = Field(..., description="Selected monetization models")
    pricing_description: str = Field(..., description="Brief pricing description")

class ValidationRequest(BaseModel):
    thesis: str = Field(..., min_length=80, description="Stated startup idea or thesis, minimum 80 characters")
    target_micro_niche: str = Field(..., description="Target micro-niche name")
    monetization_model: List[str] = Field(..., description="Selected monetization models")
    pricing_description: str = Field(..., description="Brief pricing description")
    target_price_point: Optional[int] = Field(None, description="Optional target price point in USD")
    target_customer_persona: str = Field(..., description="Target customer persona")
    marketing_budget_usd: int = Field(..., description="Marketing budget in USD, numbers only")
    development_runway_weeks: int = Field(..., description="Development runway in weeks")
    team_size: str = Field(..., description="Team size description")
    target_geography: str = Field(..., description="Target geography")
    unfair_advantage: str = Field(..., description="Unfair advantage description")
    current_stage: str = Field(..., description="Current stage description")
    waitlist_size: Optional[int] = Field(None, description="Optional waitlist size if current_stage is Waitlist")
    current_mrr: Optional[int] = Field(None, description="Optional current MRR in USD if current_stage is Revenue")
    known_competitors: Optional[str] = Field(None, description="Known competitors description")


