# Testing

This repo uses a layered validation model. The right command depends on what changed.

## Default Command
For most code changes, start here:

```bash
scripts/run_local_checks.sh
```

This command:
- creates `.venv` if needed
- installs backend dependencies
- runs guarded unit tests
- runs deterministic repository checks

## Validation Layers

### Deterministic Repository Checks
Use when:
- docs changed
- workflow files changed
- config or repo-policy files changed

Command:
```bash
python tests/run_repo_checks.py
```

Artifact:
- `tests/repo_checks/results.json`

### Unit And API Tests
Use when:
- backend logic changed
- API behavior changed
- runtime logic changed

Typical commands:
```bash
python3 tests/run_unit_tests.py
```

Optional if `pytest` is already available in your environment:
```bash
pytest tests -q
```

Targeted examples:
```bash
.venv/bin/python -m unittest tests.test_runtime_service -v
.venv/bin/python -m unittest tests.test_api_runtime_responsiveness -v
```

### Runtime Evals
Use when:
- runtime lifecycle behavior changed
- retry logic changed
- event-loop responsiveness changed
- scheduler or background execution behavior changed

Command:
```bash
python tests/run_runtime_evals.py
```

Why this matters:
- the `#51` migration step added explicit responsiveness expectations while blocking orchestration runs in the worker pool

### LLM And Workflow Evals
Use when:
- prompts changed
- tool-calling behavior changed
- orchestration policy changed
- model-facing output quality is part of the change

Deterministic harness:
```bash
python tests/run_llm_evals.py --mode mock
```

Live run:
```bash
python tests/run_llm_evals.py --mode live
```

Artifacts:
- `tests/llm_evals/results/latest.json`
- timestamped result files under `tests/llm_evals/results/`

## Environment Notes
- `TEST_DATABASE_URL` should point to a dedicated destructive test database.
- `EVAL_DATABASE_URL` should point to a dedicated evaluation database.
- Live LLM evals need provider credentials and will report `blocked` if the key is missing.

## Minimum Honest Validation By Change Type
- Docs-only updates: `python tests/run_repo_checks.py`
- General backend change: `scripts/run_local_checks.sh`
- Runtime/orchestrator change: `scripts/run_local_checks.sh` plus `python tests/run_runtime_evals.py`
- Prompt/tool-routing change: `scripts/run_local_checks.sh` plus `python tests/run_llm_evals.py --mode mock`

## Reporting In PRs
Include:
- exact commands run
- whether results passed, failed, or were blocked
- any gaps you intentionally left unrun

### Test Environment Setup

Ensure proper test environment configuration:

```bash
# Backend dependencies
cd backend
pip install -r requirements.txt

# Environment variables
export OPENAI_API_KEY="your-api-key"

# Database setup (if needed)
python -c "from database.db_manager import DatabaseManager; DatabaseManager().create_tables()"
```

## Extending the Test Suite

### Adding New Test Categories

To add new test categories:

1. Define test cases in the appropriate category
2. Implement validation logic
3. Add to the main test runner
4. Update documentation

### Custom Test Scenarios

For specific use cases, create focused test scripts:

```python
# Example: Document Q&A specific testing
async def test_document_qa():
    # Custom RAG testing logic
    pass
```

## Test Metrics and Performance

### Performance Tracking

Tests track token usage and execution time:

```python
# Token usage statistics
total_tokens = sum(result.get('token_usage', 0) for result in self.test_results)
avg_tokens = total_tokens / len(self.test_results) if self.test_results else 0
```

### Success Criteria

- **Pass Rate**: Target 90%+ for production deployment
- **Response Time**: Monitor agent response latency
- **Tool Accuracy**: Validate correct tool selection rates

## Related Documentation

- [Development Guide](DEVELOPMENT_GUIDE.md) - Development workflow including testing
- [Architecture](ARCHITECTURE.md) - System architecture affecting test design
- [API Documentation](API.md) - API endpoints used in integration testing
- [Setup Guide](SETUP.md) - Environment setup for testing
