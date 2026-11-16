# Bug Assessment: PowerShell Wildcard Glob Failure When Running Knowledge Base Pytest Suite

- **Slug**: pytest-knowledge-glob-error
- **Created**: 2026-11-16
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

```text
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api> uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v
================================================================== test session starts ===================================================================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api
configfile: pyproject.toml
plugins: anyio-4.14.2, cov-7.1.0
collected 0 items                                                                                                                                          

==================================================================== warnings summary ==================================================================== 
.venv\Lib\site-packages\fastapi\testclient.py:1
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: 
Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

main.py:40
main.py:40
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\main.py:40: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    from services.reporting.presentation import routes as reporting  # noqa: E402

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================================================== 3 warnings in 0.01s =================================================================== 
ERROR: file or directory not found: tests/unit/test_knowledge*.py
```

## Symptom

When running the Automated Verification Gates command documented in `specs/026-rag-knowledge-base/quickstart.md` (`uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v`) inside a Windows PowerShell session, `pytest` collects `0 items` and exits with code 4 (`ERROR: file or directory not found: tests/unit/test_knowledge*.py`). Expected behavior is that all unit and integration tests for the `026-rag-knowledge-base` feature (including Qdrant vector store adapter tests) are discovered and executed across both POSIX shells (`bash`/`zsh`) and Windows PowerShell.

## Reproduction

1. Open a Windows PowerShell terminal in the repository root.
2. Change directory to `services/api`:
   ```powershell
   cd services/api
   ```
3. Run the verification command from `specs/026-rag-knowledge-base/quickstart.md`:
   ```powershell
   uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v
   ```
4. Observe `collected 0 items` and `ERROR: file or directory not found: tests/unit/test_knowledge*.py`.

## Suspected Code Paths

- `specs/026-rag-knowledge-base/quickstart.md:187` — Specifies `uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v`, relying on POSIX shell glob expansion (`*`) which Windows PowerShell does not perform for external native executables (`uv.exe` / `pytest.exe`), and also omits `tests/integration/test_qdrant_adapter.py`.
- `services/api/pyproject.toml:45-46` — Configures `[tool.pytest.ini_options]`, where pytest markers or testpaths can be configured if needed.

## Root Cause Hypothesis

Unlike POSIX shells (`bash`, `zsh`), Windows PowerShell does not expand wildcard globs (`*`) in arguments passed to external native executables (`uv`). Instead, PowerShell passes the literal strings `tests/unit/test_knowledge*.py` and `tests/integration/test_knowledge*.py` to `pytest`. Because `pytest` treats positional path arguments as literal file or directory paths on the filesystem rather than glob patterns, `pytest` fails immediately with `ERROR: file or directory not found: tests/unit/test_knowledge*.py`. Additionally, the glob `tests/integration/test_knowledge*.py` inadvertently excludes `services/api/tests/integration/test_qdrant_adapter.py`, which is part of the `026-rag-knowledge-base` integration test suite. Confidence: **high**.

## Proposed Remediation

**Preferred**: Update `specs/026-rag-knowledge-base/quickstart.md` (Section 5: Automated Verification Gates) to invoke `pytest` with explicit, cross-platform file paths (or `-k` expression / directory targets) that work identically in Windows PowerShell, Command Prompt, and POSIX shells, and include `tests/integration/test_qdrant_adapter.py`:

```bash
uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v
```
(Or concisely via pytest keyword filtering: `uv run pytest tests/unit tests/integration -k "knowledge or qdrant" -v`.)

**Alternatives** (optional):
- Use `uv run pytest tests/unit tests/integration -k "knowledge or qdrant" -v`: Shorter command line and automatically picks up future `test_knowledge_*.py` files without relying on shell glob expansion, though `-k` matches test/module names by substring.
- Add a custom pytest marker (e.g., `@pytest.mark.knowledge`) in `services/api/pyproject.toml` and decorate the knowledge test modules: Requires modifying multiple test files and `pyproject.toml`, which is heavier than necessary for a documentation command fix.

**Files likely to change**:
- `specs/026-rag-knowledge-base/quickstart.md`

**Tests to add or update**:
- Verify that executing the updated `uv run pytest ... -v` command in Windows PowerShell from `services/api` discovers and passes all 6 knowledge base unit and integration test modules (`test_knowledge_chunking.py`, `test_knowledge_config.py`, `test_knowledge_guardrails.py`, `test_knowledge_service.py`, `test_knowledge_routes.py`, and `test_qdrant_adapter.py`).

## Risks & Considerations

- Low risk: Updating the verification gate command in `specs/026-rag-knowledge-base/quickstart.md` only affects documentation and developer/CI command execution, ensuring cross-platform compatibility across Windows PowerShell and POSIX shells.
- Note: The `StarletteDeprecationWarning` warnings shown in the console output (`httpx` in `starlette.testclient` and `HTTP_422_UNPROCESSABLE_ENTITY` in `services/reporting/presentation/routes.py`) are non-fatal deprecation warnings from upstream Starlette/FastAPI versions and do not cause the exit code 4 failure.

## Open Questions

- None.
