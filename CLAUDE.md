# NYT News Aggregator

## What this project does
- Fetches top stories, most-popular, and ESG/sustainability articles from the NYT API
- Summarizes each section using the Anthropic Claude API (OpenAI and Ollama supported as fallbacks)
- Schedules the pipeline via Airflow 3.0 DAGs (TaskFlow API)
- Generates an HTML digest and delivers it by email via SMTP
- Provides a `read-news` CLI for browsing digests in the terminal

## Current state
Fully restructured as a `src/news_aggregator/` Python package managed by Poetry.
- venv removed — Poetry handles the virtualenv (`.venv/` in project root, gitignored)
- All runtime Airflow files (`airflow.cfg`, `airflow.db`, `logs/`) live in `~/airflow/` (`$AIRFLOW_HOME`)
- Type hints, loguru logging, and Pydantic models applied throughout
- Unit tests in `tests/` using pytest (all external dependencies mocked — no API keys needed)
- GitHub Actions CI/CD at `.github/workflows/ci.yml`: lint (ruff), typecheck (mypy), test matrix (Python 3.9–3.12)

## Package structure
```
src/news_aggregator/
├── clients/
│   ├── nyt_client.py      # NYTimesClient — top stories, popular, ESG search; save/load helpers
│   └── llm_client.py      # LLMClient — Anthropic / OpenAI / Ollama with auto-selection
├── models/
│   └── article.py         # Pydantic Article, DigestSection, Digest models
├── email/
│   └── sender.py          # SMTP delivery via smtplib (Gmail TLS)
└── cli/
    └── read_news.py        # Terminal digest reader — entry point: read-news
```

Airflow DAGs remain at the repo root under `dags/`. The `include/` folder is a backwards-compat shim that re-exports from `news_aggregator.clients.llm_client`.

## Conventions
- Type hints on all public functions
- `loguru` for logging (no `print()` or stdlib `logging` in library code)
- Pydantic v2 for all data models
- Poetry for dependency management (`pyproject.toml`)
- `from __future__ import annotations` at the top of every module

## Python version
- Pinned: **3.12.3** via `.python-version` (pyenv)
- Supported range: `>=3.9,!=3.13,<3.14`
- 3.13 excluded by Apache Airflow 3.0; 3.14 not yet stable across the dependency stack

## Environment variables (.env — gitignored, see .env.example)
- `NYT_API_KEY` — NYTimes developer API key
- `ANTHROPIC_API_KEY` — Claude API key (primary LLM)
- `OPENAI_API_KEY` — optional fallback LLM
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` — Gmail SMTP settings
- `EMAIL_FROM`, `EMAIL_TO` — sender and comma-separated recipients
- `AIRFLOW_HOME` — should be set to `~/airflow` in shell profile

## Airflow setup
- `AIRFLOW_HOME=~/airflow` (set in `~/.zshrc`)
- Config: `~/airflow/airflow.cfg` — `dags_folder` points to this repo's `dags/`
- DB: `~/airflow/airflow.db` (SQLite, LocalExecutor)
- Logs: `~/airflow/logs/`
- `load_examples = False`
- Use `airflow api-server` (not `airflow webserver` — renamed in Airflow 3.0)
- Activate venv before running airflow commands: `source .venv/bin/activate`

## Dependency management
- Core deps: installed by default with `poetry install`
- `apache-airflow`: optional extra — `poetry install --extras airflow` (required for local Airflow usage)
- `openai`: optional extra — `poetry install --extras openai`
- `dev` tools (pytest, ruff, mypy): `poetry install --extras dev`
- To install everything: `poetry install --extras "airflow openai dev"`
- `--with` flag is for Poetry native groups, not PEP 621 optional deps — always use `--extras` here

## Running tests
```bash
poetry install --extras dev
pytest tests/ -m "not integration"   # fast, no API keys needed
pytest tests/ -m integration          # requires live keys in .env
```

## CI/CD
GitHub Actions at `.github/workflows/ci.yml`:
- `lint` job: `ruff check` + `ruff format --check` on Python 3.12
- `typecheck` job: `mypy src/news_aggregator/` on Python 3.12
- `test` job: matrix across Python 3.9, 3.10, 3.11, 3.12; runs `pytest tests/ -m "not integration"`
- No API keys needed in CI — all external calls are mocked

## Key known issues / fixes applied
- `fetch_esg_articles` task: NYT API can return `"docs": null` — fixed with `or []` guard in `nyt_client.py`
- `graphviz` warning: install system package (`sudo apt install graphviz`) + Python binding (`pip install graphviz`) for DAG graph rendering in the UI
- `poetry install --with dev` fails — `--with` is for Poetry groups; use `--extras dev` instead
