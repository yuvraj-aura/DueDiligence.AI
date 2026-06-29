# DueDiligence.AI

An automated, adversarial multi-agent system that stress-tests software startup ideas before a single line of code is written. It prevents developers and founders from building products that have broken unit economics or are entering oversaturated markets.

---

## 🚀 System Architecture Overview

DueDiligence.AI orchestrates a pipeline of specialized AI agents to rigorously evaluate startup ideas. It combines web-scraping intelligence, sentiment analysis, and deterministic financial modeling with strict validator filters to produce an absolute **GO / NO-GO** decision.

```mermaid
graph TD
    A[Founder Input Form] -->|1. Submit Step 1| B(Pre-Flight Agent)
    B -->|Passed Coherence| C[Unlock Step 2 Fields]
    C -->|2. Run Full Validation| D(Orchestrator Engine)
    
    subgraph Multi-Agent Validation Pipeline
        D --> E[Gatekeeper Agent]
        E -->|Normalize Inputs| F[Researcher Agent]
        F -->|Reddit, PH & Web Crawl| G[Numbers Engine]
        G -->|Calculate CAC, LTV & Viability Ratio| H[Critic Agent]
        H -->|Check Hard Thresholds| I{Survival Decision}
        
        I -->|KILL: Broken Econ / Saturation| J[Kill View Dashboard]
        I -->|PASS: Viable Concept| K[Builder Agent]
        K -->|Generate 90-Day Blueprint| L[Report Dashboard]
    end
```

---

## 🛠️ Key Architectural Components

### 1. Two-Step Pre-Flight Validation
* **Step 1 Coherence Check**: The frontend verifies minimum length constraints (80+ characters) and sends the thesis to a lightweight `pre_flight_agent` using Gemini 2.5 Flash to ensure it describes a concrete software idea rather than generic queries.
* **Step 2 Parameter Intake**: Upon passing, the UI reveals quantitative inputs including Runway, Target Geography, Customer Persona, Marketing Budget, and traction indicators (Waitlist size or MRR).

### 2. Multi-Agent Pipeline
* **Gatekeeper Agent**: Sanitizes and normalizes the pricing inputs (e.g. translating multi-select monetization schemes into normalized categories) to ensure compatibility.
* **Researcher Agent**: Runs concurrent web scrapes across GitHub, Product Hunt, and Google via custom MCP tools. It computes a **Market Saturation Score (0.0 to 10.0)** and a **Reddit Sentiment Delta** indicating user frustration (opportunity) vs user satisfaction (market barrier).
* **Numbers Engine**: A mathematical agent applying industry benchmarks to estimate **Customer Acquisition Cost (CAC)**, **Lifetime Value (LTV)**, and the critical **Viability Ratio ($LTV/CAC$)**.
* **Critic Agent**: Acts as the ultimate validator. If the viability ratio is below $3.0\times$ or if saturation is high without a clear unfair advantage, the Critic triggers a hard `KILL` filter (e.g. `KILL: UNIT_ECON_BROKEN` or `KILL: SATURATION_NO_DIFFERENTIATOR`).
* **Builder Agent**: Triggered only upon survival. This agent compiles the final product roadmap, risk mitigation matrix, and daily task list divided into a 90-day timeline.

---

## 📈 Kill Screen v1.1 Specifications

When the system triggers a `KILL` decision, the user is redirected to the **Autopsy Dashboard** featuring:
* **Viability Ratio Card**: Displays the computed $LTV / CAC$ ratio colored dynamically based on survival risk (Red `< 3.0`, Amber `3.0–5.0`, Green `> 5.0`).
* **Plain-English Explanations**: Synthesizes the core reason for failure to close comprehension gaps (e.g., explaining why acquiring free users on a $310 CAC destroys a 3-month runway).
* **Reddit Sentiment Delta interpretation**: Displays an LLM-generated translation explaining if the online sentiment implies an active market opportunity or a high entry barrier.
* **Alternative Scenario Pivot Projections**: Calculates projected viability ratios dynamically for critical pivots:
  * *Switch Monetization Model*: Simulates shifting from freemium to flat-rate subscription models (lowering monthly churn to 4%).
  * *Target Enterprise Tier*: Simulates raising MRR benchmarks to a premium $150+ tier.
* **Stress-Test Pivot Flow**: Replaces standard resets with a custom CTA that keeps all form fields pre-populated and highlights the exact variable that killed the thesis with a yellow border and tooltip.

---

## 💻 Tech Stack

* **Backend**: FastAPI (Python 3.11+), Pydantic v2 (Strict schema validation), Uvicorn.
* **Agent Brain**: Gemini 2.5 Flash (via Google GenAI ADK).
* **Frontend**: Vanilla HTML5, CSS3, & Modern Javascript (Zero frameworks, zero loading lag, fluid CSS grid layouts).
* **Database**: SQLite (Telemetry logging and telemetry caching).

---

## ⚙️ Quick Start Installation

### Prerequisites
* Python 3.10+
* Git
* Gemini API Key (stored in your environment variables as `GEMINI_API_KEY`)

### Setup Commands
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yuvraj-aura/DueDiligence.AI.git
   cd DueDiligence.AI
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

5. **Start the API Server**:
   ```bash
   python -m uvicorn api.main:app --reload
   ```

6. **Access the Frontend**:
   Open `ui/index.html` directly in your web browser or access the server endpoint at `http://localhost:8000/ui/index.html`.
