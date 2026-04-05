# NYTimes News Aggregator

A practical NYTimes news aggregator with AI-powered summarization, scheduled via Apache Airflow 3.0 and delivered by email.

## Features

- Fetches top stories, most-popular, and ESG/sustainability articles from the NYT API
- Summarizes each section using Claude (or OpenAI / Ollama as fallbacks)
- Generates an HTML email digest and delivers it via SMTP
- Scheduled daily via Airflow 3.0 TaskFlow API
- CLI reader for browsing digests in the terminal

---

## Prerequisites

### pyenv

pyenv manages per-project Python versions. Install it if you don't have it:

```bash
# macOS (Homebrew)
brew install pyenv

# Linux
curl https://pyenv.run | bash
```

Add to `~/.zshrc` (or `~/.bashrc`):

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

Then reload: `source ~/.zshrc`

### Poetry

Poetry manages dependencies and virtual environments. Install it with the official installer (do **not** use `pip install poetry` — it can conflict with project environments):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Add to `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload: `source ~/.zshrc`

Verify both are available:

```bash
pyenv --version    # e.g. pyenv 2.x.x
poetry --version   # e.g. Poetry 2.x.x
```

---

## Quick Start

```bash
# 1. Clone and enter the project
cd news-aggregator

# 2. Set up Python 3.12 via pyenv (.python-version pins 3.12.3 automatically)
pyenv install 3.12.3   # if not already installed
# pyenv local is not needed — .python-version in the repo root handles it

# 3. Point Poetry at the pyenv-managed Python, then install
poetry env use $(pyenv which python)
poetry install --extras "airflow dev"   # core + Airflow + dev tools
# For full install with OpenAI support:
# poetry install --extras "airflow openai dev"

# 4. Activate the virtual environment
#    Poetry creates .venv/ inside the project — activate it once per shell session.
source .venv/bin/activate
#    All subsequent commands (python, airflow, read-news) now use the project venv.

# 5. Set AIRFLOW_HOME (add to ~/.zshrc to persist)
export AIRFLOW_HOME=~/airflow

# 6. Copy and fill in your credentials
cp .env.example .env
$EDITOR .env           # set NYT_API_KEY, ANTHROPIC_API_KEY, SMTP_*, EMAIL_*

# 7. Initialise the Airflow database
airflow db migrate

# 8. Test connections
python scripts/test_nytimes.py
python scripts/test_llm.py

# 9. Start Airflow (two separate terminal tabs, venv activated in each)
airflow scheduler
# --- new tab ---
airflow api-server
# Open http://localhost:8080  (Airflow 3.0 UI)

# 10. Trigger the DAG and read your digest
airflow dags trigger 05_nytimes_aggregator
read-news --interactive
```

---

## Project Structure

```
news-aggregator/
├── src/
│   └── news_aggregator/            # Installable Python package
│       ├── clients/
│       │   ├── nyt_client.py       # NYTimes API (top stories, popular, ESG search)
│       │   └── llm_client.py       # Multi-provider LLM (Claude / GPT / Ollama)
│       ├── models/
│       │   └── article.py          # Pydantic Article, DigestSection, Digest models
│       ├── email/
│       │   └── sender.py           # SMTP email delivery (Gmail TLS)
│       └── cli/
│           └── read_news.py        # Terminal digest reader (entry point: read-news)
├── dags/
│   ├── 01_hello_airflow.py         # Basics: DAG, tasks, dependencies
│   ├── 02_python_operators.py      # PythonOperator, XCom, templates
│   ├── 03_taskflow_api.py          # Modern @task / @dag decorators
│   ├── 04_branching_sensors.py     # Branching, sensors, trigger rules
│   └── 05_nytimes_aggregator.py    # Production pipeline (fetch → summarize → email)
├── scripts/
│   ├── test_nytimes.py             # Verify NYT API key and client
│   ├── test_llm.py                 # Verify LLM provider availability
│   └── read_news.py                # Thin shim → news_aggregator.cli.read_news
├── include/
│   └── llm_client.py               # Backwards-compat shim (imports from src/)
├── docs/
│   └── LLM_INTEGRATION_GUIDE.md    # Architecture, prompt engineering, best practices
├── data/articles/                  # Runtime output — gitignored
├── .env                            # Secrets — gitignored
├── .env.example                    # Template for .env
├── .python-version                 # pyenv pin (3.12.3)
└── pyproject.toml                  # Poetry config, dependencies, entry points
```

**Runtime files** (live in `$AIRFLOW_HOME`, default `~/airflow/`):

```
~/airflow/
├── airflow.cfg
├── airflow.db
└── logs/
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in each value. The full set of variables:

| Variable | Required | Description |
|---|---|---|
| `NYT_API_KEY` | Yes | NYTimes developer API key |
| `ANTHROPIC_API_KEY` | One of these | Claude API key (recommended) |
| `OPENAI_API_KEY` | One of these | OpenAI API key |
| `SMTP_HOST` | For email | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | For email | e.g. `587` |
| `SMTP_USER` | For email | Your Gmail address |
| `SMTP_PASSWORD` | For email | Gmail App Password (16 chars) |
| `EMAIL_FROM` | For email | Sender address |
| `EMAIL_TO` | For email | Comma-separated recipients |
| `AIRFLOW_HOME` | Recommended | e.g. `~/airflow` |

The system auto-selects the best available LLM (Anthropic → OpenAI → Ollama → no-op fallback). Email delivery is skipped gracefully if SMTP vars are absent.

---

## Learning Path

Work through the DAGs in order to learn Airflow concepts:

### DAG 01 — Hello Airflow
`dags/01_hello_airflow.py`

- DAG definition and parameters
- `BashOperator`
- Task dependencies with `>>`
- Cron scheduling

### DAG 02 — Python Operators
`dags/02_python_operators.py`

- `PythonOperator`
- Passing parameters with `op_kwargs`
- XCom for sharing data between tasks
- Jinja template variables (`{{ ds }}` etc.)

### DAG 03 — TaskFlow API
`dags/03_taskflow_api.py`

- `@task` decorator (modern approach)
- Automatic XCom handling via function arguments
- `@dag` decorator
- Multiple outputs with `multiple_outputs=True`

### DAG 04 — Branching & Sensors
`dags/04_branching_sensors.py`

- `BranchPythonOperator` / `@task.branch`
- `FileSensor`, `PythonSensor`
- `ShortCircuitOperator`
- Trigger rules (`none_failed_min_one_success`, `all_done`, etc.)

### DAG 05 — NYTimes Aggregator (Production)
`dags/05_nytimes_aggregator.py`

- Production-ready TaskFlow pipeline
- External API integration with retry logic
- LLM summarization with graceful degradation
- Parallel task execution
- HTML digest generation
- SMTP email delivery
- Automatic cleanup of old files

---

## LLM Integration

The pipeline summarizes each news section independently, then generates an overall daily digest. All LLM interaction goes through `LLMClient` in `src/news_aggregator/clients/llm_client.py`.

### Supported Providers

| Provider | Cost | Setup |
|---|---|---|
| **Anthropic Claude** | ~$0.25–15 / M tokens | Set `ANTHROPIC_API_KEY` |
| **OpenAI GPT** | ~$0.15–30 / M tokens | Set `OPENAI_API_KEY` |
| **Ollama (local)** | Free | Install Ollama, `ollama pull llama3.2` |

### Quick Setup

**Option 1: Anthropic Claude (recommended)**
```bash
# https://console.anthropic.com/
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> .env
```

**Option 2: OpenAI GPT**
```bash
# https://platform.openai.com/api-keys
echo 'export OPENAI_API_KEY=sk-...' >> .env
```

**Option 3: Ollama (free, local)**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2
# No API key needed — client auto-detects localhost:11434
```

### Test Your Configuration
```bash
poetry run python scripts/test_llm.py
```

See `docs/LLM_INTEGRATION_GUIDE.md` for architecture patterns, prompt engineering, cost management, and production best practices.

---

## Email Setup (Gmail)

1. Enable 2-Step Verification on your Google account
2. Go to **Google Account → Security → App passwords**
3. Create an App Password (select "Mail" / "Other")
4. Set the 16-character password as `SMTP_PASSWORD` in `.env`

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # App Password
export EMAIL_FROM=you@gmail.com
export EMAIL_TO=you@gmail.com,friend@gmail.com
```

---

## Key Airflow Concepts

### Operators

| Operator | Purpose |
|---|---|
| `BashOperator` | Run shell commands |
| `PythonOperator` | Run Python callables |
| `@task` decorator | Modern Python tasks (TaskFlow) |
| `BranchPythonOperator` | Conditional paths |
| `FileSensor` | Wait for a file to appear |
| `PythonSensor` | Wait for a callable to return `True` |
| `ShortCircuitOperator` | Skip downstream if condition is False |
| `EmptyOperator` | Structural placeholder / join point |

### XCom

```python
# Traditional
ti.xcom_push(key="data", value={"foo": "bar"})
data = ti.xcom_pull(task_ids="upstream", key="data")

# TaskFlow (automatic — just use function arguments)
@task
def get_data() -> dict:
    return {"foo": "bar"}

@task
def use_data(data: dict) -> None:
    print(data["foo"])

result = get_data()
use_data(result)   # XCom wired automatically
```

### Scheduling

```python
schedule="0 8 * * *"   # Daily at 8 AM
schedule="@daily"       # Midnight
schedule="@hourly"      # Every hour
schedule=None           # Manual trigger only
```

---

## NYTimes API Setup

1. Go to <https://developer.nytimes.com/>
2. Create a free account and click **Apps → New App**
3. Enable: **Top Stories**, **Article Search**, **Most Popular**
4. Copy the API key into `.env` as `NYT_API_KEY`

---

## Daily Usage

```bash
# Activate the venv (once per shell session)
source .venv/bin/activate

# Install / update dependencies
poetry install --extras "airflow dev"

# Test API connections
python scripts/test_nytimes.py
python scripts/test_llm.py

# Trigger the pipeline manually
source .env
airflow dags trigger 05_nytimes_aggregator

# Read the digest
read-news --interactive     # terminal reader
read-news --open            # open HTML in browser
read-news --section world   # specific section
read-news --popular         # most popular
```

---

## Troubleshooting

### "NYT_API_KEY not configured"
Edit `.env` and set `NYT_API_KEY=<your key>`, then `source .env`.

### "No articles found"
```bash
poetry run python scripts/test_nytimes.py
```

### "LLM summaries not appearing"
```bash
python scripts/test_llm.py
# Confirm at least one provider shows ✅
```

### "DAG not showing in UI"
```bash
# Check for syntax errors
python dags/05_nytimes_aggregator.py
# Scheduler picks up new DAGs within ~30 seconds
```

### Checking logs
Airflow task logs are at `$AIRFLOW_HOME/logs/` (default `~/airflow/logs/`):
```bash
ls ~/airflow/logs/dag_id=05_nytimes_aggregator/
```

### Port 8080 already in use
```bash
lsof -i :8080           # find what's using it
# or run api-server on a different port:
airflow api-server --port 8081
```

---

## Python Version Compatibility

The project targets **Python 3.12** (pinned in `.python-version`) and is designed to support **3.9 through 3.12**.

| Python | Status |
|---|---|
| 3.9 | Supported (minimum) |
| 3.10 | Supported |
| 3.11 | Supported |
| 3.12 | Supported — **recommended, pinned via pyenv** |
| 3.13 | Not supported — excluded by Apache Airflow 3.0 (`!=3.13`) |
| 3.14+ | Not yet supported — packages not stable for this version |

If you need to switch to a different 3.9–3.12 patch version, update `.python-version` and re-run `poetry install`.

## Versions

- Python: 3.12.3 (pyenv pin), supports 3.9–3.12
- Apache Airflow: 3.0
- Anthropic SDK: ≥ 0.40
- Pydantic: ≥ 2.0
- loguru: ≥ 0.7

---

## Testing

Unit tests live in `tests/`. All external calls (NYT API, Anthropic, SMTP) are mocked — no API keys needed to run the test suite.

```bash
# Run unit tests (fast, no API keys)
poetry run pytest tests/ -m "not integration" -v

# Run integration tests (requires live API keys in .env)
source .env
poetry run pytest tests/ -m integration -v
```

### Test coverage

| Module | Test file |
|---|---|
| `models/article.py` | `tests/test_article_model.py` |
| `clients/nyt_client.py` | `tests/test_nyt_client.py` |
| `clients/llm_client.py` | `tests/test_llm_client.py` |
| `email/sender.py` | `tests/test_email_sender.py` |
| `cli/read_news.py` | `tests/test_cli_read_news.py` |

---

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push and pull request to `main`:

| Job | What it does | Python |
|---|---|---|
| `lint` | `ruff check` + `ruff format --check` | 3.12 |
| `typecheck` | `mypy src/news_aggregator/` | 3.12 |
| `test` | `pytest tests/ -m "not integration"` | 3.9, 3.10, 3.11, 3.12 |

All jobs use Poetry dependency caching to keep runs fast. No API keys are needed — integration tests are excluded in CI.

---

## Next Steps

1. **Add More Sources** — RSS feeds, Guardian API, Reuters
2. **Add a Database** — store articles in PostgreSQL with SQLAlchemy
3. **Categorize with LLM** — sentiment analysis, topic tagging
4. **Docker Compose** — package Airflow + Postgres for a production-like setup
5. **CeleryExecutor** — run tasks in parallel across workers
6. **Airflow Connections** — store API keys in the Connections UI instead of `.env`

---

## Resources

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Airflow TaskFlow API](https://airflow.apache.org/docs/apache-airflow/stable/tutorial/taskflow.html)
- [NYTimes API Documentation](https://developer.nytimes.com/docs)
- [Anthropic Documentation](https://docs.anthropic.com/)
- [OpenAI Documentation](https://platform.openai.com/docs/)
- [Ollama](https://ollama.ai/)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [loguru Documentation](https://loguru.readthedocs.io/)
