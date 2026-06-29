// Frontend Javascript application logic
const API_BASE = window.location.origin;

document.addEventListener("DOMContentLoaded", () => {
    const validateForm = document.getElementById("validate-form");
    const restartBtns = document.querySelectorAll(".restart-btn");
    
    // View Sections
    const formView = document.getElementById("form-view");
    const trackerView = document.getElementById("tracker-view");
    const killView = document.getElementById("kill-view");
    const reportView = document.getElementById("report-view");
    
    let activeEventSource = null;
    let cachedRoadmap = [];
    const thesisTextarea = document.getElementById("thesis");
    const thesisCharCount = document.getElementById("thesis-char-count");
    const runPreFlightBtn = document.getElementById("run-pre-flight");
    const step2Container = document.getElementById("step-2-container");
    const pricePointGroup = document.getElementById("price-point-group");

    thesisTextarea.addEventListener("input", () => {
        const len = thesisTextarea.value.length;
        thesisCharCount.innerText = len;
        if (len >= 80) {
            thesisCharCount.style.color = "var(--success)";
        } else {
            thesisCharCount.style.color = "var(--text-secondary)";
        }
    });

    // Capture monetization multi-select values
    const getMonetizationChecked = () => Array.from(document.querySelectorAll('input[name="monetization_model"]:checked')).map(cb => cb.value);

    // Watch checkbox changes to show/hide Target Price Point
    const updatePricePointVisibility = () => {
        const checkedVals = getMonetizationChecked();
        if (checkedVals.includes("Flat") || checkedVals.includes("Seat-Based")) {
            pricePointGroup.style.display = "block";
            document.getElementById("target_price_point").setAttribute("required", "required");
        } else {
            pricePointGroup.style.display = "none";
            document.getElementById("target_price_point").removeAttribute("required");
            document.getElementById("target_price_point").value = "";
        }
    };
    
    document.querySelectorAll('input[name="monetization_model"]').forEach(cb => {
        cb.addEventListener("change", updatePricePointVisibility);
    });

    // Show/hide Traction details dynamically
    const currentStageSelect = document.getElementById("current_stage");
    const waitlistSizeGroup = document.getElementById("waitlist-size-group");
    const currentMrrGroup = document.getElementById("current-mrr-group");

    currentStageSelect.addEventListener("change", () => {
        const stage = currentStageSelect.value;
        if (stage === "Waitlist") {
            waitlistSizeGroup.style.display = "block";
            document.getElementById("waitlist_size").setAttribute("required", "required");
            currentMrrGroup.style.display = "none";
            document.getElementById("current_mrr").removeAttribute("required");
            document.getElementById("current_mrr").value = "";
        } else if (stage === "Revenue") {
            currentMrrGroup.style.display = "block";
            document.getElementById("current_mrr").setAttribute("required", "required");
            waitlistSizeGroup.style.display = "none";
            document.getElementById("waitlist_size").removeAttribute("required");
            document.getElementById("waitlist_size").value = "";
        } else {
            waitlistSizeGroup.style.display = "none";
            document.getElementById("waitlist_size").removeAttribute("required");
            document.getElementById("waitlist_size").value = "";
            currentMrrGroup.style.display = "none";
            document.getElementById("current_mrr").removeAttribute("required");
            document.getElementById("current_mrr").value = "";
        }
    });

    // Pre-Flight Check Call
    runPreFlightBtn.addEventListener("click", async () => {
        const thesisVal = thesisTextarea.value.trim();
        const nicheVal = document.getElementById("target_micro_niche").value.trim();
        const monetizationVal = getMonetizationChecked();
        const pricingDescVal = document.getElementById("pricing_description").value.trim();

        if (thesisVal.length < 80) {
            alert("Error: Thesis must be at least 80 characters long.");
            return;
        }
        if (!nicheVal) {
            alert("Error: Please enter a Target Micro-Niche.");
            return;
        }
        if (monetizationVal.length === 0) {
            alert("Error: Please select at least one Monetization Model.");
            return;
        }
        if (!pricingDescVal) {
            alert("Error: Please describe your pricing briefly.");
            return;
        }

        // Show loading state on button
        const originalText = runPreFlightBtn.innerText;
        runPreFlightBtn.innerText = "Checking Thesis...";
        runPreFlightBtn.disabled = true;

        try {
            const preFlightPayload = {
                thesis: thesisVal,
                target_micro_niche: nicheVal,
                monetization_model: monetizationVal,
                pricing_description: pricingDescVal
            };

            const preFlightResponse = await fetch(`${API_BASE}/pre-validate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(preFlightPayload)
            });

            if (!preFlightResponse.ok) {
                const errData = await preFlightResponse.json();
                throw new Error(errData.detail || "Pre-flight validation failed.");
            }

            // Success: reveal step 2 and transition smoothly
            step2Container.style.display = "block";
            step2Container.scrollIntoView({ behavior: "smooth" });
            runPreFlightBtn.innerText = "✓ Pre-Flight Passed";
            runPreFlightBtn.style.backgroundColor = "var(--success)";
            
        } catch (error) {
            alert(`Pre-Flight Rejected: ${error.message}`);
            runPreFlightBtn.innerText = originalText;
            runPreFlightBtn.disabled = false;
        }
    });

    // Final Form Submission
    validateForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            thesis: document.getElementById("thesis").value,
            target_micro_niche: document.getElementById("target_micro_niche").value,
            monetization_model: getMonetizationChecked(),
            pricing_description: document.getElementById("pricing_description").value,
            target_price_point: document.getElementById("target_price_point").value ? parseInt(document.getElementById("target_price_point").value, 10) : null,
            target_customer_persona: document.getElementById("target_customer_persona").value,
            marketing_budget_usd: parseInt(document.getElementById("marketing_budget_usd").value, 10),
            development_runway_weeks: parseInt(document.getElementById("development_runway_weeks").value, 10),
            team_size: document.getElementById("team_size").value,
            target_geography: document.getElementById("target_geography").value,
            unfair_advantage: document.getElementById("unfair_advantage").value,
            current_stage: document.getElementById("current_stage").value,
            waitlist_size: document.getElementById("waitlist_size").value ? parseInt(document.getElementById("waitlist_size").value, 10) : null,
            current_mrr: document.getElementById("current_mrr").value ? parseInt(document.getElementById("current_mrr").value, 10) : null,
            known_competitors: document.getElementById("known_competitors").value
        };

        try {
            // Show Tracker View immediately
            switchView(trackerView);
            resetTrackerSteps();
            
            const response = await fetch(`${API_BASE}/validate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("API Gateway rejected validation request.");
            
            const data = await response.json();
            const sessionId = data.session_id;
            
            document.getElementById("active-session-id").innerText = sessionId;
            
            // Connect to Real-time SSE status stream
            startStatusStream(sessionId);

        } catch (error) {
            alert(`Error: ${error.message}`);
            switchView(formView);
        }
    });

    // Reset views and go back to input form
    restartBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            validateForm.reset();
            
            // Forceful state reset: Clear all dynamic DOM text and elements
            document.getElementById("active-session-id").innerText = "";
            thesisCharCount.innerText = "0";
            thesisCharCount.style.color = "var(--text-secondary)";
            
            // Reset pre-flight button and container states
            runPreFlightBtn.innerText = "Run Pre-Flight Check";
            runPreFlightBtn.disabled = false;
            runPreFlightBtn.style.backgroundColor = "";
            step2Container.style.display = "none";
            pricePointGroup.style.display = "none";
            waitlistSizeGroup.style.display = "none";
            currentMrrGroup.style.display = "none";
            
            // Clear Kill View DOM elements
            document.getElementById("kill-reason-code").innerText = "";
            document.getElementById("kill-plain-translation").innerText = "";
            document.getElementById("kill-cac").innerText = "$0.00";
            document.getElementById("kill-ltv").innerText = "$0.00";
            document.getElementById("kill-churn").innerText = "0%";
            document.getElementById("kill-mrr").innerText = "$0.00";
            document.getElementById("kill-sat-score").innerText = "0.0";
            document.getElementById("kill-comp-count").innerText = "0";
            document.getElementById("kill-reddit-sentiment").innerText = "0.00";
            document.getElementById("kill-competitor-links").innerHTML = "";
            document.getElementById("kill-pivot-matrix").innerHTML = "";
            document.getElementById("kill-high-leverage-action").innerHTML = "";

            // Clear Report View DOM elements
            document.getElementById("thesis-confirmation-text").innerText = "";
            document.getElementById("report-sat-score").innerText = "0.0";
            document.getElementById("report-cac").innerText = "$0.00";
            document.getElementById("report-ltv").innerText = "$0.00";
            document.getElementById("report-viability-ratio").innerText = "0.00";
            document.getElementById("report-mrr").innerText = "$0.00";
            document.getElementById("report-mrr-3mo").innerText = "$0.00";
            document.getElementById("report-mrr-6mo").innerText = "$0.00";
            document.getElementById("report-mrr-12mo").innerText = "$0.00";
            document.querySelector("#risks-table tbody").innerHTML = "";
            document.getElementById("sources-list-container").innerHTML = "";
            document.getElementById("week-selector-buttons").innerHTML = "";
            document.getElementById("week-tasks-container").innerHTML = "";
            cachedRoadmap = [];

            resetTrackerSteps();
            switchView(formView);
        });
    });

    // Handle view swaps
    function switchView(targetView) {
        [formView, trackerView, killView, reportView].forEach(view => {
            view.classList.remove("active");
        });
        targetView.classList.add("active");
    }

    function resetTrackerSteps() {
        const steps = ["gatekeeper", "researcher", "numbers", "critic", "builder"];
        steps.forEach(step => {
            const el = document.getElementById(`step-${step}`);
            el.className = "step-card";
            el.querySelector(".badge").innerText = "Waiting";
        });
    }

    // Connect and listen to SSE Stream
    function startStatusStream(sessionId) {
        if (activeEventSource) activeEventSource.close();

        activeEventSource = new EventSource(`${API_BASE}/stream/${sessionId}`);
        
        activeEventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const status = data.status;
            const context = data.context || {};
            
            updateTrackerStatus(status);

            if (status === "builder_complete") {
                activeEventSource.close();
                renderReportDashboard(context);
                switchView(reportView);
            } else if (status === "killed") {
                activeEventSource.close();
                renderKillScreen(context);
                switchView(killView);
            } else if (status === "error" || status === "builder_failed") {
                activeEventSource.close();
                alert(`Analysis halted due to an internal execution error: ${status}`);
                switchView(formView);
            }
        };

        activeEventSource.onerror = () => {
            console.warn("SSE Connection lost. Retrying standard checks...");
        };
    }

    // Track active agent states
    function updateTrackerStatus(status) {
        const stepGate = document.getElementById("step-gatekeeper");
        const stepRes = document.getElementById("step-researcher");
        const stepNum = document.getElementById("step-numbers");
        const stepCrit = document.getElementById("step-critic");
        const stepBuild = document.getElementById("step-builder");

        if (status === "gatekeeper_running") {
            setStepState(stepGate, "active", "Running");
        } else if (status === "gatekeeper_complete") {
            setStepState(stepGate, "complete", "Finished");
        } else if (status === "researcher_running") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "active", "Running");
        } else if (status === "researcher_complete") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "complete", "Finished");
        } else if (status === "numbers_running") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "complete", "Finished");
            setStepState(stepNum, "active", "Running");
        } else if (status === "numbers_complete") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "complete", "Finished");
            setStepState(stepNum, "complete", "Finished");
        } else if (status === "critic_running") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "complete", "Finished");
            setStepState(stepNum, "complete", "Finished");
            setStepState(stepCrit, "active", "Running");
        } else if (status === "critic_complete" || status === "builder_running") {
            setStepState(stepGate, "complete", "Finished");
            setStepState(stepRes, "complete", "Finished");
            setStepState(stepNum, "complete", "Finished");
            setStepState(stepCrit, "complete", "Passed");
            setStepState(stepBuild, "active", "Building");
        }
    function setStepState(element, className, text) {
        element.className = `step-card ${className}`;
        element.querySelector(".badge").innerText = text;
    }

    // Render Kill Screen View
    function renderKillScreen(context) {
        const gatekeeperOut = context.gatekeeper_output || {};
        const criticOut = context.critic_decision || {};
        const researcherOut = context.researcher_output || {};
        const numbersOut = context.numbers_output || {};
        
        const killCode = criticOut.decision || "KILL: UNIT_ECON_BROKEN";
        document.getElementById("kill-reason-code").innerText = killCode;

        // Parse core economics variables
        const cac = numbersOut.estimated_cac ? parseFloat(numbersOut.estimated_cac).toFixed(2) : "0.00";
        const ltv = numbersOut.estimated_ltv ? parseFloat(numbersOut.estimated_ltv).toFixed(2) : "0.00";
        const mrr = numbersOut.estimated_mrr_usd ? parseFloat(numbersOut.estimated_mrr_usd).toFixed(2) : "0.00";
        const model = (gatekeeperOut.pricing_model || "unknown").toLowerCase();
        
        let churnText = "N/A";
        if (model === "freemium") churnText = "8%";
        else if (model === "flat_subscription") churnText = "4%";
        else if (model === "usage_based") churnText = "5%";

        const viabilityRatio = numbersOut.viability_ratio ? parseFloat(numbersOut.viability_ratio) : 0.00;
        const ratioEl = document.getElementById("kill-ratio");
        ratioEl.innerText = viabilityRatio.toFixed(2);
        
        // Color coding for viability ratio
        if (viabilityRatio < 3.0) {
            ratioEl.style.color = "var(--danger)";
        } else if (viabilityRatio <= 5.0) {
            ratioEl.style.color = "var(--warning)";
        } else {
            ratioEl.style.color = "var(--success)";
        }

        // 1. Plain-English Translation
        const descBox = document.getElementById("kill-plain-translation");
        if (killCode === "KILL: UNIT_ECON_BROKEN") {
            descBox.innerText = `Your ${model.replace("_", " ")} model produces an estimated CAC of $${cac} against an LTV of $${ltv}. That ratio is critically below the viable threshold. The model will burn cash regardless of market conditions. ` + 
                                `A viable business requires LTV to be at least 3× your CAC. Your current ratio is ${viabilityRatio.toFixed(2)}×, which means you lose money on every customer you acquire under these conditions.`;
        } else if (killCode === "KILL: SATURATION_NO_DIFFERENTIATOR") {
            const satScore = parseFloat(researcherOut.saturation_score || 0.0).toFixed(1);
            descBox.innerText = `The target niche is highly saturated with a score of ${satScore} out of 10.0, and your pitch lacks a clear, unique differentiator. Entering this space without a specialized focus is a high-risk venture.`;
        } else if (killCode === "KILL: CITATION_FAIL") {
            descBox.innerText = `Market research validation failed because over 20% of the active competitor websites found during domain crawling lacked valid source URLs, indicating that the concept lacks sufficient verifiable benchmarks.`;
        } else {
            descBox.innerText = criticOut.kill_reason || "The startup thesis failed validation because it did not clear the Critic's deterministic economic or search filters.";
        }

        // 2. Autopsy Report
        document.getElementById("kill-cac").innerText = `$${cac}`;
        document.getElementById("kill-ltv").innerText = `$${ltv}`;
        document.getElementById("kill-churn").innerText = churnText;
        document.getElementById("kill-mrr").innerText = `$${mrr}`;

        // 3. Hard Evidence
        document.getElementById("kill-sat-score").innerText = parseFloat(researcherOut.saturation_score || 0.0).toFixed(1);
        document.getElementById("kill-comp-count").innerText = researcherOut.competitor_count || 0;
        document.getElementById("kill-reddit-sentiment").innerText = parseFloat(researcherOut.sentiment_delta || 0.0).toFixed(2);
        
        // Reddit Sentiment Delta interpretation
        const redditInterp = document.getElementById("kill-reddit-interpretation");
        if (researcherOut.sentiment_interpretation) {
            redditInterp.innerText = researcherOut.sentiment_interpretation;
            redditInterp.style.display = "block";
        } else {
            // Fallback generated deterministically
            const sentiment = parseFloat(researcherOut.sentiment_delta || 0.0);
            if (sentiment < 0) {
                redditInterp.innerText = "Strong negative sentiment signals frustrated users and unmet needs in this market — this is an opportunity indicator, not a reason to avoid the space.";
            } else {
                redditInterp.innerText = "Positive sentiment suggests satisfied users — existing solutions are meeting needs. You need a strong differentiator to displace them.";
            }
            redditInterp.style.display = "block";
        }

        // Competitor Citations List
        const linksContainer = document.getElementById("kill-competitor-links");
        linksContainer.innerHTML = "";
        const competitors = researcherOut.competitor_list || [];
        competitors.forEach(comp => {
            const li = document.createElement("li");
            li.innerHTML = `<a href="${comp.url}" target="_blank">${comp.name} &rarr;</a>`;
            linksContainer.appendChild(li);
        });

        // 4. Pivot Matrix
        const pivotContainer = document.getElementById("kill-pivot-matrix");
        pivotContainer.innerHTML = "";
        
        let pivots = [];
        
        // Deterministic pivot viability ratio helper
        function calculateProjectedRatio(pricingModel, currentMrrVal, sentimentDeltaVal) {
            const modelName = pricingModel.toLowerCase();
            let baseCacVal = 240.0;
            let churnVal = 0.04;
            if (modelName.includes("usage")) {
                baseCacVal = 180.0;
                churnVal = 0.05;
            } else if (modelName.includes("freemium")) {
                baseCacVal = 310.0;
                churnVal = 0.08;
            } else if (modelName.includes("flat") || modelName.includes("seat")) {
                baseCacVal = 240.0;
                churnVal = 0.04;
            }
            
            let cacVal = baseCacVal;
            if (sentimentDeltaVal > 0) {
                const reduction = Math.min(sentimentDeltaVal * 0.20, 0.20);
                cacVal = baseCacVal * (1.0 - reduction);
            }
            
            const ltvVal = currentMrrVal / churnVal;
            return cacVal > 0 ? (ltvVal / cacVal) : 99.9;
        }

        const sentimentVal = parseFloat(researcherOut.sentiment_delta || 0.0);
        const rawMrr = numbersOut.estimated_mrr_usd ? parseFloat(numbersOut.estimated_mrr_usd) : 20.0;

        if (killCode === "KILL: UNIT_ECON_BROKEN") {
            const flatRatio = calculateProjectedRatio("Flat", rawMrr, sentimentVal);
            const enterpriseRatio = calculateProjectedRatio(model, 150.0, sentimentVal);

            pivots = [
                {
                    title: "Switch Monetization Model",
                    desc: "Transition from Freemium to Flat-Rate Subscription. This decreases assumed monthly churn from 8% to 4% and instantly doubles LTV.",
                    projected: flatRatio
                },
                {
                    title: "Target Enterprise Tier",
                    desc: `Raise the MRR benchmark from $${mrr} to $150+ by repackaging features into professional freelancer or agency bundles.`,
                    projected: enterpriseRatio
                }
            ];
        } else if (killCode === "KILL: SATURATION_NO_DIFFERENTIATOR") {
            pivots = [
                {
                    title: "Niche Down Focus",
                    desc: "Target an explicit sub-segment (e.g., invoices with automated escrow triggers specifically built for Spanish-speaking freelance contractors).",
                    projected: null
                },
                {
                    title: "Introduce AI-Agent Workflows",
                    desc: "Reposition the service as an autonomous smart collection agent rather than a manual template builder, shifting the value proposition.",
                    projected: null
                }
            ];
        } else {
            pivots = [
                {
                    title: "Expand Scraper Scope",
                    desc: "Use broader search keywords to ensure crawling finds authentic, established platforms with reachable web domains.",
                    projected: null
                },
                {
                    title: "Direct Competitor Benchmarking",
                    desc: "Enter a list of known competitors manually to bypass automated organic search indexing limits.",
                    projected: null
                }
            ];
        }

        pivots.forEach(p => {
            const div = document.createElement("div");
            div.className = "pivot-card";
            
            let ratioLine = "";
            if (p.projected !== null) {
                const isViable = p.projected >= 3.0;
                const ratioColor = isViable ? "var(--success)" : "var(--warning)";
                const labelText = isViable ? "VIABLE" : "MARGINAL";
                ratioLine = `<p style="margin-top: 0.5rem; font-weight: 600; color: ${ratioColor};">Projected Viability Ratio: ${p.projected.toFixed(1)}× (${labelText})</p>`;
            }

            div.innerHTML = `
                <h6>${p.title}</h6>
                <p>${p.desc}</p>
                ${ratioLine}
            `;
            pivotContainer.appendChild(div);
        });

        // 5. Single Highest-Leverage Action
        const leverageContainer = document.getElementById("kill-high-leverage-action");
        if (killCode === "KILL: UNIT_ECON_BROKEN") {
            leverageContainer.innerText = "The One Thing: Kill the freemium pricing structure immediately. You cannot afford to acquire free users with a base CAC of $310 under your current runway constraints.";
        } else if (killCode === "KILL: SATURATION_NO_DIFFERENTIATOR") {
            leverageContainer.innerText = "The One Thing: Rewrite your value proposition to include an explicit, automated differentiator (e.g., using 'unlike' or 'only') to stand out from existing competitors.";
        } else {
            leverageContainer.innerText = "The One Thing: Ensure you specify a functioning, indexable niche that has actual SaaS alternatives already operating on live web domains.";
        }
    }

    // Render Dashboard Panels View
    function renderReportDashboard(context) {
        const gatekeeperOut = context.gatekeeper_output || {};
        const researcherOut = context.researcher_output || {};
        const numbersOut = context.numbers_output || {};
        const criticOut = context.critic_decision || {};
        const builderOut = context.builder_output || {};

        // Confirmation summary
        document.getElementById("thesis-confirmation-text").innerText = criticOut.thesis_confirmation || "";

        // Saturation score
        const score = parseFloat(researcherOut.saturation_score || 0.0);
        document.getElementById("report-sat-score").innerText = score.toFixed(1);
        
        const satDescEl = document.getElementById("report-sat-desc");
        if (score < 4.0) {
            satDescEl.innerText = "Low Competition Saturation Opportunity";
            satDescEl.style.color = "var(--success)";
        } else if (score < 7.0) {
            satDescEl.innerText = "Moderate Saturation Detected";
            satDescEl.style.color = "var(--warning)";
        } else {
            satDescEl.innerText = "Highly Saturated Competitor Market";
            satDescEl.style.color = "var(--danger)";
        }

        // Financial KPIs
        document.getElementById("report-cac").innerText = `$${parseFloat(numbersOut.estimated_cac || 0).toFixed(2)}`;
        document.getElementById("report-ltv").innerText = `$${parseFloat(numbersOut.estimated_ltv || 0).toFixed(2)}`;
        
        const ratioVal = parseFloat(numbersOut.viability_ratio || 0).toFixed(2);
        document.getElementById("report-viability-ratio").innerText = ratioVal;
        
        const badgeEl = document.getElementById("report-viability-status");
        badgeEl.innerText = numbersOut.decision || "VIABLE";
        if (numbersOut.decision === "VIABLE") {
            badgeEl.className = "badge pass-badge";
        } else {
            badgeEl.className = "badge status";
        }

        // Projections
        const modelInfo = builderOut.financial_model || {};
        document.getElementById("report-mrr").innerText = `$${parseFloat(numbersOut.estimated_mrr_usd || 0).toFixed(2)}`;
        document.getElementById("report-mrr-3mo").innerText = `$${parseFloat(modelInfo.mrr_projection_3mo || 0).toFixed(2)}`;
        document.getElementById("report-mrr-6mo").innerText = `$${parseFloat(modelInfo.mrr_projection_6mo || 0).toFixed(2)}`;
        document.getElementById("report-mrr-12mo").innerText = `$${parseFloat(modelInfo.mrr_projection_12mo || 0).toFixed(2)}`;

        // Risks Table
        const risksBody = document.querySelector("#risks-table tbody");
        risksBody.innerHTML = "";
        const risks = builderOut.risk_matrix || [];
        risks.forEach(item => {
            const tr = document.createElement("tr");
            
            const p = parseFloat(item.probability);
            const imp = parseFloat(item.impact);
            const score = p * imp;
            
            let tier = "Low";
            let color = "var(--success)";
            if (score > 0.4) {
                tier = "High";
                color = "var(--danger)";
            } else if (score > 0.2) {
                tier = "Medium";
                color = "var(--warning)";
            }

            tr.innerHTML = `
                <td>${item.risk}</td>
                <td>${Math.round(p * 100)}%</td>
                <td>${Math.round(imp * 100)}%</td>
                <td><span style="color: ${color}; font-weight: 600;">${tier}</span></td>
            `;
            risksBody.appendChild(tr);
        });

        // Cited Sources
        const sourcesContainer = document.getElementById("sources-list-container");
        sourcesContainer.innerHTML = "";
        const competitors = researcherOut.competitor_list || [];
        competitors.forEach(comp => {
            const li = document.createElement("li");
            li.innerHTML = `
                <span><strong>${comp.name}</strong> (Founded: ${comp.founding_year || 'N/A'}, Reviews: ${comp.review_count || 0})</span>
                <a href="${comp.url}" target="_blank">View Site</a>
            `;
            sourcesContainer.appendChild(li);
        });

        // Setup Roadmap Weeks selector
        cachedRoadmap = builderOut.roadmap || [];
        setupRoadmapWeekSelectors();
    }

    // Setup Roadmap Weeks selectors (1-13)
    function setupRoadmapWeekSelectors() {
        const container = document.getElementById("week-selector-buttons");
        container.innerHTML = "";
        
        const weeksCount = 13;
        for (let w = 1; w <= weeksCount; w++) {
            const btn = document.createElement("button");
            btn.className = w === 1 ? "week-btn active" : "week-btn";
            btn.innerText = `Week ${w}`;
            btn.addEventListener("click", () => {
                document.querySelectorAll(".week-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                renderRoadmapWeekTasks(w);
            });
            container.appendChild(btn);
        }
        
        // Show week 1 tasks by default
        renderRoadmapWeekTasks(1);
    }

    // Render selected week's daily tasks
    function renderRoadmapWeekTasks(weekNum) {
        const container = document.getElementById("week-tasks-container");
        container.innerHTML = "";
        
        const weekTasks = cachedRoadmap.filter(task => parseInt(task.week) === weekNum);
        
        if (weekTasks.length === 0) {
            container.innerHTML = "<p>No tasks configured for this week.</p>";
            return;
        }

        // Sort tasks by day
        weekTasks.sort((a, b) => parseInt(a.day) - parseInt(b.day));
        
        weekTasks.forEach(task => {
            const card = document.createElement("div");
            card.className = "task-item";
            card.innerHTML = `
                <div class="task-row">
                    <span class="task-day">Day ${task.day}</span>
                    <span class="task-owner">${task.owner}</span>
                </div>
                <div class="task-desc">${task.task}</div>
                <div class="task-deliverable"><strong>Deliverable:</strong> ${task.deliverable}</div>
            `;
            container.appendChild(card);
        });
    }

    // Handle Report Page navigation tab changes
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const paneId = tab.getAttribute("data-tab");
            document.querySelectorAll(".tab-pane").forEach(pane => {
                pane.classList.remove("active");
            });
            document.getElementById(paneId).classList.add("active");
        });
    });

    const killRestartBtn = document.getElementById("kill-restart-btn");
    killRestartBtn.addEventListener("click", () => {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        const killCode = document.getElementById("kill-reason-code").innerText;

        // Clear previous highlights
        document.querySelectorAll(".kill-highlight").forEach(el => {
            el.style.border = "";
            el.style.padding = "";
            el.style.borderRadius = "";
            const existingTooltip = el.parentElement.querySelector(".pivot-tooltip");
            if (existingTooltip) existingTooltip.remove();
        });
        const prevTooltip = document.querySelector(".pivot-tooltip");
        if (prevTooltip) prevTooltip.remove();

        if (killCode === "KILL: UNIT_ECON_BROKEN") {
            const targetEl = document.querySelector(".monetization-checkbox-grid");
            if (targetEl) {
                targetEl.style.border = "2px solid var(--warning)";
                targetEl.style.padding = "0.5rem";
                targetEl.style.borderRadius = "8px";
                
                const tooltip = document.createElement("div");
                tooltip.className = "pivot-tooltip";
                tooltip.innerText = "Target variable: pricing/monetization model causing broken unit economics";
                tooltip.style.position = "absolute";
                tooltip.style.top = "-2.2rem";
                tooltip.style.left = "0";
                tooltip.style.backgroundColor = "var(--warning)";
                tooltip.style.color = "#000";
                tooltip.style.padding = "0.25rem 0.5rem";
                tooltip.style.borderRadius = "4px";
                tooltip.style.fontSize = "0.85rem";
                tooltip.style.fontWeight = "bold";
                tooltip.style.zIndex = "100";
                
                targetEl.parentElement.style.position = "relative";
                targetEl.parentElement.appendChild(tooltip);

                const cleanup = () => {
                    targetEl.style.border = "";
                    targetEl.style.padding = "";
                    targetEl.style.borderRadius = "";
                    tooltip.remove();
                    document.querySelectorAll('input[name="monetization_model"]').forEach(cb => {
                        cb.removeEventListener("change", cleanup);
                    });
                };
                document.querySelectorAll('input[name="monetization_model"]').forEach(cb => {
                    cb.addEventListener("change", cleanup);
                });
            }
        } else if (killCode === "KILL: SATURATION_NO_DIFFERENTIATOR" || killCode.includes("SATURATION")) {
            const targetEl = document.getElementById("target_micro_niche");
            if (targetEl) {
                targetEl.style.border = "2px solid var(--warning)";
                
                const tooltip = document.createElement("div");
                tooltip.className = "pivot-tooltip";
                tooltip.innerText = "Target variable: highly saturated niche lacking differentiation";
                tooltip.style.position = "absolute";
                tooltip.style.top = "-2.2rem";
                tooltip.style.left = "0";
                tooltip.style.backgroundColor = "var(--warning)";
                tooltip.style.color = "#000";
                tooltip.style.padding = "0.25rem 0.5rem";
                tooltip.style.borderRadius = "4px";
                tooltip.style.fontSize = "0.85rem";
                tooltip.style.fontWeight = "bold";
                tooltip.style.zIndex = "100";
                
                targetEl.parentElement.style.position = "relative";
                targetEl.parentElement.appendChild(tooltip);

                const cleanup = () => {
                    targetEl.style.border = "";
                    tooltip.remove();
                    targetEl.removeEventListener("input", cleanup);
                };
                targetEl.addEventListener("input", cleanup);
            }
        }

        resetTrackerSteps();
        switchView(formView);
    });
});
