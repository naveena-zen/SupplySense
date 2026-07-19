# SupplySense — AI Supply Chain Risk & Inventory Intelligence

SupplySense is a real-time, AI-driven supply chain monitor and reactive investigator built for the **AI Agent Hackathon**. It features an autonomous background monitor agent that executes database audits on a schedule, and a reactive tool-use agent that resolves operational questions through a hand-rolled multi-turn loop.

---

## 🚀 Key Features

1. **Shared Reasoning Core (`risk.py`)**: Pure, database-free Python functions that pre-calculate stockout metrics, supplier risks, and delay impacts to guide LLM reasoning with precise data.
2. **Autonomous Monitor Agent**: Runs periodically via an `APScheduler` cron job. It snapshots database state, filters out healthy data to save tokens, prompts the LLM as an Operations Analyst, and writes structured alerts (`AgentDecision`) to PostgreSQL.
3. **Reactive Operations Agent**: A custom-built, hand-rolled multi-turn loop (capped at 5 turns) that intercepts natural language queries, executes database-backed Python tool handlers, feeds results back to the LLM, and logs execution traces.
4. **FastAPI Services**: Exposes REST interfaces for telemetry tables, manual agent scans, chats, and LLM executive summaries.
5. **Vite React Dashboard**: Premium dark mode UI featuring:
   - **Agent Activity Log Panel** (expandable cards detailing agent runs, telemetry, context, and mitigations).
   - **Collapsible Thought-Trace Chat Console** (visualizing the step-by-step reasoning and tool outputs).
   - **Telemetry tables** for at-risk products, shipping delays, and supply partners.
6. **Docker Orchestration**: Single-command boot orchestrating PostgreSQL, FastAPI API, and Vite client web server.

---

## 🛠️ Tech Stack
- **Frontend**: React, Vite, Tailwind CSS v3, Recharts, Lucide Icons
- **Backend**: FastAPI, Uvicorn, SQLAlchemy, APScheduler
- **Database**: PostgreSQL (managed via Alembic migrations)
- **AI Integrations**: Anthropic Claude API (primary) & Groq Llama API (fallback adapter)
- **Containerization**: Docker & Docker Compose

---

## 💻 Quick Start

### 1. Configure Credentials
Create a `.env` configuration file in the `backend/` folder (we have supplied a template):
```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=supplysense
DB_USER=postgres
DB_PASSWORD=postgres

# Provide either key. Claude is prioritized; Groq acts as fallback.
ANTHROPIC_API_KEY=your-anthropic-api-key
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

### 2. Run via Docker Compose (Recommended)
Launch the database, backend API, and React frontend with a single command from the workspace root:
```bash
docker-compose up --build
```
- **React Dashboard**: Access at [http://localhost](http://localhost)
- **FastAPI Documentation**: Access at [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Manual Local Installation

**A. Database & Backend Setup:**
1. Ensure a PostgreSQL database named `supplysense` is running locally.
2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Apply database migrations:
   ```bash
   $env:PYTHONPATH=".."; alembic upgrade head
   ```
4. Seed the mock database:
   ```bash
   $env:PYTHONPATH=".."; python seed.py
   ```
5. Launch the FastAPI server:
   ```bash
   uvicorn backend.main:app --reload
   ```

**B. Frontend Setup:**
1. Install node packages:
   ```bash
   cd frontend
   npm install
   ```
2. Launch Vite dev server:
   ```bash
   npm run dev
   ```
   Open the browser at [http://localhost:5173](http://localhost:5173).

---

## 🧪 Testing
Run the backend pytest suite to verify calculation schemas and database integration tool wrappers:
```bash
$env:PYTHONPATH="."; python -m pytest backend/tests
```

---

## 🗺️ System Design
For visual Mermaid flowcharts and structural diagrams of the two agent loops, please check the [ARCHITECTURE.md](ARCHITECTURE.md) document in the workspace root.
