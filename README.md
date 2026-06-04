# Memra — Core Behavioral Memory Engine

> A persistent, per-user psychological profiling backend that learns how you work, identifies your cognitive friction points, and adapts every AI response to route around them.

---

## What It Does

Most AI assistants forget you the moment a conversation ends. Memra doesn't.

Memra is a FastAPI backend that builds a persistent behavioral profile for each user across sessions. It watches for patterns in your conversations — the moments you freeze, the architecture decisions that cause analysis paralysis, the planning styles that stall you — and stores them as structured psychological constraints. Every subsequent AI response is then **adapted in real-time** to your specific cognitive profile: reframing tasks in ways that work for your brain, not a generic user's.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                      │
│                                                         │
│  /auth          → JWT registration & login              │
│  /chat/append   → Ingest conversation turns             │
│  /chat/respond  → AI response with live guardrails      │
│  /memory/update → Extract friction traits from session  │
│  /memory/merge  → Promote staged traits to profile      │
│  /memory/profile→ Read / reset behavior graph           │
│  /workspace/sync→ Async document ingestion              │
│  /chat/proactive-checkin → Context-aware session opener │
└─────────────────────────────────────────────────────────┘
         │                          │
    SQLite (SQLAlchemy)         Groq API (LLaMA 3.3 70B)
    users + messages            via Instructor (structured output)
```

---

## Key Features

### Feature 1 — Pending Commitment Isolation Queue
New behavioral observations extracted from a session are not immediately written to the active profile. They enter a **staging queue** (`pending_commitments`) first. This prevents a single session from corrupting the profile with noise. Once you're confident in a trait, you merge it explicitly.

### Feature 2 — Proactive Check-In Engine
On session start, instead of a blank prompt, Memra generates a **hyper-specific opening question** derived from your highest-priority unresolved goal or known friction point. It references the exact task by name. No generic greetings.

### Feature 3 — Live Guardrail Interception
Every `/chat/respond` call reads your verified psychological constraints (those with `confidence >= 0.6`) and **injects adaptive framing instructions** into the system prompt in real-time. If monolithic architecture causes you to freeze, the AI is instructed to always break tasks into the smallest decoupled unit first.

### Feature 4 — Socratic Mode
Pass `socratic_mode=true` to `/chat/respond` to switch the AI from a supportive accountability partner to a **ruthless Socratic interrogator** — one that audits your reasoning, calls out contradictions, and challenges weak assumptions without softening.

### Feature 5 — Async Workspace Sync
Drop a raw text document (notes, plans, retrospectives) to `/workspace/sync`. A background thread runs a full psychometric parse via the LLM and merges extracted goals, vulnerabilities, and constraints directly into your profile — without blocking the request.

### Feature 6 — Daily Context Rotation
`/chat/session/current` generates a **deterministic daily session ID** (`session_{user_id}_{date}`) to create clean, isolated conversation windows per day automatically.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | SQLite via SQLAlchemy |
| LLM Provider | Groq (LLaMA 3.3 70B Versatile) |
| Structured Output | Instructor (JSON mode) |
| Auth | JWT (HS256) via `python-jose` |
| Password Hashing | bcrypt via `passlib` |
| Server | Uvicorn |

---

## Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/your-username/memra.git
cd memra
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

### 3. Run

```bash
python app.py
```

Server starts at `http://127.0.0.1:8000`. Interactive API docs at `/docs`.

---

## API Reference

All protected routes require a Bearer token in the `Authorization` header.

### Auth

```bash
# Register
curl -X POST "http://127.0.0.1:8000/auth/register?user_id=alice&password=secret"

# Login — returns JWT
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -d "username=alice&password=secret"

export TOKEN="<access_token>"
```

### Core Workflow

```bash
# 1. Get today's session ID
curl "http://127.0.0.1:8000/chat/session/current" \
  -H "Authorization: Bearer $TOKEN"

# 2. Start conversation — proactive opener
curl -X POST "http://127.0.0.1:8000/chat/proactive-checkin?session_id=SESSION_ID" \
  -H "Authorization: Bearer $TOKEN"

# 3. Append messages
curl -X POST "http://127.0.0.1:8000/chat/append" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","session_id":"SESSION_ID","role":"user","content":"I keep freezing when I think about refactoring the monolith."}'

# 4. Get AI response (with live guardrails applied)
curl -X POST "http://127.0.0.1:8000/chat/respond?session_id=SESSION_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"I keep freezing when I think about refactoring the monolith."}'

# 5. Extract friction traits from session → staging queue
curl -X POST "http://127.0.0.1:8000/memory/update?session_id=SESSION_ID" \
  -H "Authorization: Bearer $TOKEN"

# 6. Merge staged traits into active profile
curl -X POST "http://127.0.0.1:8000/memory/merge" \
  -H "Authorization: Bearer $TOKEN"

# 7. Inspect full behavior graph
curl "http://127.0.0.1:8000/memory/profile" \
  -H "Authorization: Bearer $TOKEN"
```

### Workspace Sync (async document ingestion)

```bash
curl -X POST "http://127.0.0.1:8000/workspace/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"My goals are to ship the API by Q3. I always overthink database schema design..."}'
```

---

## Data Model

### User Behavior Profile (stored as JSON in SQLite)

```json
{
  "primary_goals": ["Ship v1 API by Q3", "..."],
  "psychological_constraints": [
    {
      "friction_trigger": "Monolithic architecture",
      "observed_cognitive_state": "Analysis paralysis",
      "mitigation_instruction": "Focus on decoupling smallest component or utility function first",
      "times_observed": 3,
      "confidence": 0.75,
      "last_seen": "2026-06-05 14:22:00"
    }
  ],
  "execution_style": {
    "preferred_pacing": "Sprint-based",
    "communication_preference": "Direct and technical",
    "vulnerabilities": ["Over-planning before execution"]
  },
  "pending_commitments": []
}
```

### Confidence Model

Traits start at `confidence: 0.3` when first staged. Each time the same `friction_trigger` is observed again and merged, confidence increases by `+0.15` (capped at `1.0`). The guardrail interception system only activates traits at `confidence >= 0.6` — requiring at least 3 observed instances before influencing AI behavior.

---

## Project Structure

```
memra/
├── app.py          # All FastAPI routes and business logic
├── auth.py         # JWT creation, verification, password hashing
├── database.py     # SQLAlchemy models, engine, session context
├── memra.db        # SQLite database (auto-created on first run)
├── .env            # GROQ_API_KEY (not committed)
└── requirements.txt
```

---

## Requirements

```
fastapi
uvicorn
sqlalchemy
python-jose[cryptography]
passlib[bcrypt]
python-dotenv
groq
instructor
pydantic
python-multipart
```

---

## Roadmap

### Coming Soon

| Feature | Where | Description |
|---|---|---|
| **Passive Reflection** | `app.py` — `evening_checkin` | Automatically auto-triggers `/memory/update` at the end of evening checks without manual user input |
| **Trait Decay Loop** | `app.py` — Profile Load Hook | Applies a daily linear confidence penalty to traits unobserved for more than 7 days |
| **Profile Pruning** | `app.py` — `decay_stale_constraints` | Permanently deletes traits from DB when confidence hits `<= 0.1` to maintain clean state |
| **Episodic memory with embeddings** | — | ChromaDB or Qdrant — semantic search over past sessions, not just current profile |
| **Behavioral drift detection** | — | Track when the user drifts from their stated goals over days, not just per-session |
| **Session recap reports** | — | Auto-generate a weekly digest: wins, slippage, momentum score |
| **True Socratic depth** | — | Chain contradictions across sessions, not just per-message |
| **Momentum score engine** | — | Quantify execution velocity as a number clients can act on |
| **Visual goal dependency graph** | — | Show which tasks unlock others — the critical path, live |
| **Extraction accuracy evals** | — | Measure whether the profile actually matches real behavior |
| **Team / pair mode** | — | Two engineers holding each other accountable — viral loop |

---

## License

MIT
