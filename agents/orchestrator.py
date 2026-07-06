import asyncio
import logging
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.context import PipelineContext
from agents.gatekeeper import gatekeeper_agent
from api.session_cache import SessionCache
from data_layer.telemetry import write_signal

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("orchestrator")

session_service = InMemorySessionService()
cache = SessionCache()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    reraise=True
)
async def run_agent_with_retry(runner, user_id, session_id, message):
    """
    Enforces up to 5 attempts with exponential backoff
    on all ADK agent run loops to catch and recover from transient API errors.
    """
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message
    ):
        pass

async def run_pipeline(session_id: str, session_hash: str, inputs: dict):
    """
    Sequentially runs the AI due diligence validation pipeline.
    Invokes Agent 01 (Gatekeeper) and updates the session status.
    """
    logger.info(f"Orchestrator: Starting pipeline execution for session {session_id}...")
    
    # 1. Instantiate the PipelineContext
    context = PipelineContext(
        session_id=session_id,
        session_hash=session_hash,
        raw_input=inputs,
        pipeline_status="gatekeeper_running"
    )
    
    # Update SessionCache with new status
    session_data = {
        "session_id": session_id,
        "session_hash": session_hash,
        "status": "gatekeeper_running",
        "inputs": inputs,
        "context": context.dict()
    }
    await cache.set_session(session_id, session_data)

    # 2. Setup Runner for Gatekeeper agent
    runner = Runner(
        agent=gatekeeper_agent,
        session_service=session_service,
        app_name="ai-due-diligence",
        auto_create_session=True
    )

    # Format the inputs as a message for the model
    monetization_str = ", ".join(inputs.get('monetization_model', []))
    if inputs.get('pricing_description'):
        monetization_str += f" ({inputs.get('pricing_description')})"

    traction_info = ""
    if inputs.get('current_stage') == "Waitlist" and inputs.get('waitlist_size') is not None:
        traction_info = f", Waitlist Size: {inputs.get('waitlist_size')}"
    elif inputs.get('current_stage') == "Revenue" and inputs.get('current_mrr') is not None:
        traction_info = f", Current MRR: ${inputs.get('current_mrr')}"

    constraints_str = (
        f"Runway: {inputs.get('development_runway_weeks')} weeks, "
        f"Budget: ${inputs.get('marketing_budget_usd')}, "
        f"Team: {inputs.get('team_size')}, "
        f"Price point: ${inputs.get('target_price_point') or 0}, "
        f"Geography: {inputs.get('target_geography')}, "
        f"Current stage: {inputs.get('current_stage')}{traction_info}, "
        f"Unfair advantage: {inputs.get('unfair_advantage')}"
    )
    prompt_inputs = (
        f"Thesis: {inputs.get('thesis')}\n"
        f"Niche: {inputs.get('target_micro_niche')}\n"
        f"Monetization: {monetization_str}\n"
        f"Constraints: {constraints_str}\n"
        f"Known Competitors: {inputs.get('known_competitors') or ''}"
    )
    user_content = types.Content(
        role="user",
        parts=[types.Part(text=prompt_inputs)]
    )

    try:
        # 3. Run Gatekeeper agent asynchronously with retries
        await run_agent_with_retry(runner, "default_user", session_id, user_content)
            
        # 4. Extract output from runner session state
        session = await session_service.get_session(
            app_name="ai-due-diligence",
            user_id="default_user",
            session_id=session_id
        )
        
        gatekeeper_result = session.state.get("gatekeeper_output")
        
        if gatekeeper_result:
            context.gatekeeper_output = gatekeeper_result
            context.pipeline_status = "gatekeeper_complete"
            
            logger.info(f"Orchestrator: Gatekeeper completed successfully for session {session_id}.")
            
            # Update telemetry database (validation_sessions table)
            telemetry_payload = {
                "id": session_id,
                "session_hash": session_hash,
                "niche_slug": gatekeeper_result.get("niche_slug"),
                "pricing_model": gatekeeper_result.get("pricing_model"),
                "outcome": "PENDING"
            }
            # We call write_signal asynchronously
            await write_signal("validation_sessions", telemetry_payload)
            
            # --- START SPRINT 3: RESEARCHER AGENT EXECUTION ---
            context.pipeline_status = "researcher_running"
            session_data["status"] = "researcher_running"
            session_data["context"] = context.dict()
            await cache.set_session(session_id, session_data)
            
            # 1. Gather scraper data in parallel
            from agents.researcher import gather_market_data, researcher_agent
            niche_slug = gatekeeper_result.get("niche_slug")
            market_data = await gather_market_data(niche_slug)
            
            # 2. Setup Runner for Researcher agent
            researcher_runner = Runner(
                agent=researcher_agent,
                session_service=session_service,
                app_name="ai-due-diligence",
                auto_create_session=True
            )
            
            # 3. Format inputs for Researcher agent and run
            researcher_prompt_input = (
                f"Market Data gathered by MCP scrapers:\n"
                f"Niche Slug: {niche_slug}\n"
                f"Saturation Score (Computed): {market_data['saturation_score']}\n"
                f"Competitor Count: {market_data['competitor_count']}\n"
                f"Sentiment Delta: {market_data['sentiment_delta']}\n"
                f"Product Hunt Launches (18mo): {market_data['ph_launches_18mo']}\n"
                f"GitHub Repos (12mo): {market_data['gh_repos_12mo']}\n"
                f"Competitors details: {market_data['competitor_list']}\n"
            )
            
            researcher_message = types.Content(
                role="user",
                parts=[types.Part(text=researcher_prompt_input)]
            )
            
            # Run Researcher agent asynchronously with retries
            await run_agent_with_retry(researcher_runner, "default_user", session_id, researcher_message)
                
            # 4. Extract researcher output from session
            session = await session_service.get_session(
                app_name="ai-due-diligence",
                user_id="default_user",
                session_id=session_id
            )
            researcher_result = session.state.get("researcher_output")
            
            if researcher_result:
                context.researcher_output = researcher_result
                context.pipeline_status = "researcher_complete"
                logger.info(f"Orchestrator: Researcher completed successfully for session {session_id}.")
                
                # 5. Write saturation signals telemetry to database
                saturation_payload = {
                    "session_hash": session_hash,
                    "niche_slug": niche_slug,
                    "saturation_score": researcher_result.get("saturation_score"),
                    "competitor_count": researcher_result.get("competitor_count"),
                    "sentiment_delta": researcher_result.get("sentiment_delta"),
                    "sources_cited": len(researcher_result.get("competitor_list", []))
                }
                await write_signal("saturation_signals", saturation_payload)
                
                # --- START SPRINT 4: NUMBERS ENGINE AGENT EXECUTION ---
                context.pipeline_status = "numbers_running"
                session_data["status"] = "numbers_running"
                session_data["context"] = context.dict()
                await cache.set_session(session_id, session_data)
                
                # 1. Setup Runner for Numbers agent
                from agents.numbers_engine import numbers_agent, calculate_cac, calculate_ltv, compute_viability
                numbers_runner = Runner(
                    agent=numbers_agent,
                    session_service=session_service,
                    app_name="ai-due-diligence",
                    auto_create_session=True
                )
                
                # 2. Format inputs for Numbers agent and run
                pricing_model = gatekeeper_result.get("pricing_model")
                numbers_prompt_input = (
                    f"Product details:\n"
                    f"Value Proposition: {gatekeeper_result.get('value_proposition')}\n"
                    f"Target Audience: {gatekeeper_result.get('target_audience')}\n"
                    f"Pricing Model: {pricing_model}\n"
                    f"Constraints: {inputs.get('constraints')}\n"
                )
                
                numbers_message = types.Content(
                    role="user",
                    parts=[types.Part(text=numbers_prompt_input)]
                )
                
                # Run Numbers agent asynchronously with retries
                await run_agent_with_retry(numbers_runner, "default_user", session_id, numbers_message)
                    
                # 3. Extract numbers output from session
                session = await session_service.get_session(
                    app_name="ai-due-diligence",
                    user_id="default_user",
                    session_id=session_id
                )
                numbers_result = session.state.get("numbers_output")
                
                if numbers_result:
                    estimated_mrr = numbers_result.get("estimated_mrr_usd", 20.0)
                    sentiment_delta = researcher_result.get("sentiment_delta", 0.0)
                    
                    # 4. Perform deterministic calculations
                    cac = calculate_cac(pricing_model, sentiment_delta)
                    ltv = calculate_ltv(pricing_model, estimated_mrr)
                    ratio, dec = compute_viability(ltv, cac)
                    
                    # Update context with the complete financial benchmarks
                    benchmarks_result = {
                        "estimated_mrr_usd": estimated_mrr,
                        "estimated_cac": cac,
                        "estimated_ltv": ltv,
                        "viability_ratio": ratio,
                        "decision": dec,
                        "reasoning": numbers_result.get("reasoning", "")
                    }
                    
                    context.numbers_output = benchmarks_result
                    context.pipeline_status = "numbers_complete"
                    logger.info(f"Orchestrator: Numbers Engine completed successfully for session {session_id}.")
                    
                    # 5. Write benchmarks telemetry to database
                    benchmarks_payload = {
                        "session_hash": session_hash,
                        "niche_slug": niche_slug,
                        "pricing_model": pricing_model,
                        "estimated_cac": cac,
                        "estimated_ltv": ltv,
                        "viability_ratio": ratio
                    }
                    await write_signal("cac_ltv_benchmarks", benchmarks_payload)
                    
                    # --- START SPRINT 5: CRITIC AGENT EXECUTION ---
                    context.pipeline_status = "critic_running"
                    session_data["status"] = "critic_running"
                    session_data["context"] = context.dict()
                    await cache.set_session(session_id, session_data)
                    
                    from agents.critic import run_critic_evaluation
                    critic_result = await run_critic_evaluation(context.dict())
                    
                    context.critic_decision = critic_result
                    
                    if "KILL:" in critic_result.get("decision", ""):
                        context.pipeline_status = "killed"
                        logger.info(f"Orchestrator: Critic KILLED idea for session {session_id}. Reason: {critic_result.get('decision')}")
                        
                        # Write failure taxonomy telemetry
                        failure_payload = {
                            "session_hash": session_hash,
                            "niche_slug": niche_slug,
                            "kill_reason": critic_result.get("decision"),
                            "saturation_score": researcher_result.get("saturation_score", 0.0),
                            "retry_count": 0
                        }
                        await write_signal("failure_taxonomy", failure_payload)
                        
                        # Update outcome in validation_sessions
                        await write_signal("validation_sessions", {
                            "id": session_id,
                            "session_hash": session_hash,
                            "niche_slug": niche_slug,
                            "pricing_model": pricing_model,
                            "outcome": "KILLED"
                        })
                    else:
                        context.pipeline_status = "critic_complete"
                        logger.info(f"Orchestrator: Critic PASSED idea for session {session_id}. Launching Builder...")
                        
                        # Save state
                        session_data["status"] = "builder_running"
                        session_data["context"] = context.dict()
                        await cache.set_session(session_id, session_data)
                        
                        # --- START SPRINT 6: BUILDER AGENT EXECUTION ---
                        from agents.builder import builder_agent, validate_and_expand_roadmap
                        builder_runner = Runner(
                            agent=builder_agent,
                            session_service=session_service,
                            app_name="ai-due-diligence",
                            auto_create_session=True
                        )
                        
                        # Ingest the entire context as input
                        builder_prompt_input = (
                            f"Generate product roadmap and execution plan for the validated thesis:\n"
                            f"Value Proposition: {gatekeeper_result.get('value_proposition')}\n"
                            f"Target Audience: {gatekeeper_result.get('target_audience')}\n"
                            f"Pricing Model: {pricing_model}\n"
                            f"Saturation Score: {researcher_result.get('saturation_score')}\n"
                            f"LTV: ${benchmarks_result.get('estimated_ltv')}\n"
                            f"CAC: ${benchmarks_result.get('estimated_cac')}\n"
                            f"Viability Ratio: {benchmarks_result.get('viability_ratio')}\n"
                            f"Confirmation Summary: {critic_result.get('thesis_confirmation')}\n"
                        )
                        
                        builder_message = types.Content(
                            role="user",
                            parts=[types.Part(text=builder_prompt_input)]
                        )
                        
                        # Run Builder agent asynchronously with retries
                        await run_agent_with_retry(builder_runner, "default_user", session_id, builder_message)
                            
                        # Retrieve builder output
                        session = await session_service.get_session(
                            app_name="ai-due-diligence",
                            user_id="default_user",
                            session_id=session_id
                        )
                        builder_result = session.state.get("builder_output")
                        
                        if builder_result:
                            # Run deterministic Python post-processing verification
                            roadmap_list = builder_result.get("roadmap", [])
                            cleaned_roadmap = validate_and_expand_roadmap(roadmap_list, gatekeeper_result.get("value_proposition"))
                            
                            builder_result["roadmap"] = cleaned_roadmap
                            context.builder_output = builder_result
                            context.pipeline_status = "builder_complete"
                            logger.info(f"Orchestrator: Builder completed successfully for session {session_id}.")
                            
                            # Update outcome in validation_sessions to PASSED
                            await write_signal("validation_sessions", {
                                "id": session_id,
                                "session_hash": session_hash,
                                "niche_slug": niche_slug,
                                "pricing_model": pricing_model,
                                "outcome": "PASSED"
                            })
                        else:
                            context.pipeline_status = "builder_failed"
                            logger.warning(f"Orchestrator: Builder failed to generate output for session {session_id}.")
                else:
                    context.pipeline_status = "numbers_failed"
                    logger.warning(f"Orchestrator: Numbers Engine failed to generate output for session {session_id}.")
            else:
                context.pipeline_status = "researcher_failed"
                logger.warning(f"Orchestrator: Researcher failed to generate output for session {session_id}.")
                
        else:
            context.pipeline_status = "gatekeeper_failed"
            logger.warning(f"Orchestrator: Gatekeeper failed to generate output for session {session_id}.")

    except Exception as e:
        context.pipeline_status = "error"
        logger.error(f"Orchestrator: Error running pipeline for session {session_id}: {e}")

    # 5. Save updated context to SessionCache
    session_data["status"] = context.pipeline_status
    session_data["context"] = context.dict()
    await cache.set_session(session_id, session_data)

    if context.pipeline_status == "builder_complete":
        try:
            from data_layer.roadmap_persistence import persist_roadmap
            thesis_text = inputs.get("thesis", "")
            await persist_roadmap(session_id, thesis_text, context.builder_output)
        except Exception as e:
            logger.error(f"Orchestrator: Failed to persist roadmap to SQLite for session {session_id}: {e}")
