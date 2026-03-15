# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product Overview

"Clear Route" — a web application that lets non-technical users define and run business optimization problems using Genetic Algorithms. An AI translates natural language intent into optimization components (genes, objective functions, constraints) and generates Python code for PyGAD execution.

See `PRODUCT.md` for full product specification.

## Architecture

Three Docker containers orchestrated via docker-compose:

- **Frontend** — React + Material UI (JavaScript)
- **Backend** — Python FastAPI
- **Database** — PostgreSQL

### Backend (Python/FastAPI)
- Serves REST API for auth, projects, chat, optimization execution
- Integrates with LLM providers (Gemini, OpenAI, Anthropic, Ollama) via user-configured API keys
- Dynamically generates Python optimization code from AI-defined genes/objectives/constraints
- Runs genetic algorithm optimization using PyGAD
- Executes AI-generated fitness functions in a sandboxed context

### Frontend (React/Material UI)
- Login/registration flow
- Home screen: list and create optimization projects
- Project screen with two-panel layout:
  - **Left panel**: Chat interface for describing optimization problems
  - **Right panel** with three tabs:
    - **Definition**: Editable fields for genes, objectives, constraints (AI-populated, user-editable)
    - **Benchmark**: Dynamic UI based on gene definitions for testing known inputs against objective functions
    - **Executions**: Run optimizations (configurable iterations), view convergence graphs (mono-objective) or Pareto fronts (multi-objective), AI-generated result interpretation

### Data Model
PostgreSQL stores: users, projects, chat history, gene definitions, objective descriptions, constraint descriptions, generated Python fitness functions, and execution results.

## Key Domain Concepts

- **Genes**: Decision variables — enum (dropdown), numeric (with decimals & boundaries), or string type
- **Objective Function**: Mono-objective (single fitness value, min/max) or multi-objective (Pareto front)
- **Constraints**: Business rules that the solution must satisfy
- **Fitness Function**: AI-generated Python code executed by PyGAD at runtime
- **Benchmark**: Pre-optimization testing of known inputs to validate the objective function

## Development Commands

```bash
# Start all services (postgres, backend, frontend)
docker-compose up --build

# Start in background
docker-compose up -d --build

# Backend only
docker-compose up backend

# Run alembic migration (inside backend container)
docker-compose exec backend alembic upgrade head

# Generate new migration after model changes
docker-compose exec backend alembic revision --autogenerate -m "description"

# Access backend shell
docker-compose exec backend bash

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API docs**: http://localhost:8000/docs
- **Health check**: GET http://localhost:8000/api/health

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app entrypoint, CORS, router registration
    config.py            # Pydantic settings (env vars)
    database.py          # SQLAlchemy engine, session, Base
    models/              # SQLAlchemy ORM models (User, Project, ChatMessage, Execution, UserSettings)
    schemas/             # Pydantic request/response schemas
    routes/
      deps.py            # Auth dependency (get_current_user via JWT)
      auth.py            # Register/login endpoints
      projects.py        # CRUD for optimization projects
      chat.py            # Chat with LLM, auto-extracts JSON to update project definitions
      benchmark.py       # Execute fitness function with test gene values
      executions.py      # Run PyGAD optimization (background task), poll progress
      settings.py        # LLM provider/key management
    services/
      llm.py             # Multi-provider LLM client (OpenAI, Anthropic, Gemini, Ollama) + system prompt
      optimization.py    # PyGAD runner, gene parsing, fitness compilation, result extraction
      benchmark.py       # Evaluate single solution against fitness function
  alembic/               # Database migrations
frontend/
  src/
    api.js               # Fetch wrapper with auth headers
    App.js               # React Router + MUI theme setup
    components/Layout.js # AppBar with navigation
    pages/
      LoginPage.js       # Auth form
      RegisterPage.js    # Registration form
      HomePage.js        # Project list with create/delete
      ProjectPage.js     # Core page: chat + definition/benchmark/executions tabs
      SettingsPage.js    # LLM provider/key configuration
```

## API Routes

All routes under `/api/`:
- `POST /auth/register`, `POST /auth/login` — authentication
- `GET|POST /projects/` — list/create projects
- `GET|PUT|DELETE /projects/{id}` — project CRUD
- `GET|POST /projects/{id}/messages` — chat history and LLM interaction
- `POST /projects/{id}/benchmark` — test gene values against fitness function
- `GET|POST /projects/{id}/executions` — list/start optimizations
- `GET /projects/{id}/executions/{id}` — poll execution status/results

## Key Implementation Details

- **Chat → Project update flow**: When the LLM responds with a ```json block containing `genes_description`, `objectives_description`, `constraints_description`, or `fitness_function_code`, the project is auto-updated (see `chat.py:_extract_json_updates`)
- **Fitness function execution**: Code is compiled in a restricted namespace with safe builtins + math + numpy (see `optimization.py:compile_fitness_function`)
- **Gene format**: `- Name: [type](params) - description` where type is `int`, `float`, or `enum`
- **Optimization runs as BackgroundTask**: Progress is polled by frontend every 2s
- **Result interpretation**: After optimization completes, LLM is called to interpret results in business terms

## LLM Provider Configuration

Users configure their own API keys in Settings for: Gemini, OpenAI, Anthropic, or a local Ollama server IP. Model selection is per-user.
