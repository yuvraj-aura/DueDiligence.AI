from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class PipelineContext(BaseModel):
    session_id: str = Field(..., description="Unique session identifier UUID")
    session_hash: str = Field(..., description="SHA-256 hash of session_id")
    raw_input: Dict[str, Any] = Field(..., description="Stated inputs from the user request")
    gatekeeper_output: Optional[Dict[str, Any]] = Field(None, description="Output from Agent 01 (Gatekeeper)")
    researcher_output: Optional[Dict[str, Any]] = Field(None, description="Output from Agent 02 (Researcher)")
    numbers_output: Optional[Dict[str, Any]] = Field(None, description="Output from Agent 03 (Numbers Engine)")
    critic_decision: Optional[Dict[str, Any]] = Field(None, description="Output from Agent 04 (Failsafe Critic)")
    builder_output: Optional[Dict[str, Any]] = Field(None, description="Output from Agent 05 (Builder)")
    pipeline_status: str = Field("PENDING", description="Current pipeline execution stage status")
