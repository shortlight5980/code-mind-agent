# AGENT.md

This file provides guidance to coding agents when working with code in this repository.

## Local Shell Notes

- When reading files from PowerShell, explicitly pass an encoding, normally `Get-Content -Encoding UTF8`, because the shell output code page may be GBK while repository files are usually UTF-8.
- Run Python commands through the `AIP312` conda environment.
- Prefer UTF-8 Python output on Windows:
  ```powershell
  $env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
  ```
- Prefer `conda run --no-capture-output -n AIP312 python ...` for tests and scripts. The `--no-capture-output` flag avoids conda re-encoding captured output in a GBK console.

## Common Commands

### Running Tests

```powershell
# Run all tests
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python -m unittest discover tests

# Run specific test file
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python -m unittest tests/test_index_repo_split.py

# Run specific test class/method
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python -m unittest tests.test_index_repo_split.PythonAstSplitTests
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python -m unittest tests.test_index_repo_split.PythonAstSplitTests.test_keeps_small_class_as_single_block_with_decorators
```

### Running the Application

```powershell
# Start the FastAPI server
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python app.py

# Or with uvicorn
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python -m uvicorn app:app --reload
```

### Indexing a Repository

```powershell
# Index using config.yml repo.path
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python scripts/index_repo.py

# Index specific directory
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python scripts/index_repo.py /path/to/repo

# Index with custom persist directory
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'; conda run --no-capture-output -n AIP312 python scripts/index_repo.py /path/to/repo --persist-dir ./my_chroma_db
```

## High-Level Architecture

### Core Architecture

This is a RAG-based code repository Q&A system with an Agent-based architecture:

```text
FastAPI (app.py)
    ↓
ServiceManager (services/service_manager.py) [Singleton]
    ├→ Agent (agent/agent.py)
    │   ├→ Tools (agent/tools/*)
    │   │   ├→ RetrieveAndSummarize (RAG)
    │   │   ├→ ReadFile
    │   │   ├→ SearchCode
    │   │   └→ RunCommand
    │   └→ Security (agent/security.py)
    ├→ Vector DB (Chroma)
    ├→ BM25 Index
    ├→ Summarizer LLM
    └→ PromptManager (prompts/prompt_manager.py)
```

### Key Design Decisions

1. **ServiceManager Singleton Pattern**: All core services are managed by a single `ServiceManager` instance initialized in the FastAPI lifespan. Tools access services via global injection.

2. **Python AST-based Code Splitting**: The RAG system uses AST parsing for intelligent Python code chunking that preserves class/function boundaries, with a fallback indentation scanner for invalid Python. Located in `scripts/index_repo.py`.

3. **Two-Tier Retrieval**: Code and documents are retrieved separately with configurable `retrieval_k` values, then passed through a summarization layer before being given to the main LLM.

4. **Hybrid Retrieval**: The system can combine Chroma vector retrieval and BM25 retrieval using RRF fusion. BM25 index code lives in `utils/bm25_index.py`; fusion logic lives in `utils/fusion.py`.

5. **Security-First Tool Design**: File and command operations go through `agent/security.py`, which validates allowed directories, blocks sensitive files, and restricts commands.

### Important File Relationships

| File | Depends On | Purpose |
|------|------------|---------|
| `app.py` | `services/service_manager.py`, `agent/streaming.py` | FastAPI entrypoint; lifespan manages `ServiceManager` |
| `services/service_manager.py` | `agent/agent.py`, `utils/config.py`, `utils/summarizer.py`, `utils/bm25_index.py` | Initializes and provides access to core services |
| `agent/agent.py` | `agent/tools/*`, `prompts/prompt_manager.py` | Creates LangChain Agent with tools |
| `agent/tools/retrieve_and_summarize.py` | `utils/summarizer.py`, `utils/fusion.py` | RAG tool that retrieves and summarizes codebase context |
| `scripts/index_repo.py` | `utils/config.py`, `utils/logger.py`, `utils/bm25_index.py` | Indexes repo using AST-based splitting and builds Chroma/BM25 indexes |

### Data Flow for a Chat Request

1. User POSTs `/chat` to FastAPI route handler.
2. Handler gets `service_manager.agent`.
3. Agent calls `agent.aexecute(question, history)`.
4. Agent may call `RetrieveAndSummarize`.
5. Tool rewrites/expands the query.
6. Tool retrieves docs/code separately using configured retrieval mode: `vector`, `bm25`, or `hybrid`.
7. Hybrid mode fuses Chroma and BM25 results with RRF.
8. Retrieved context is passed through the summarizer LLM.
9. Agent generates final answer from summarized context.
10. JSON response is returned.

## Configuration

- Main config: `config.yml`, loaded by `utils/config.Config`.
- Environment secrets: `.env`; `DASHSCOPE_API_KEY` is required for embedding/indexing and LLM calls.
- Chroma persistence is configured under `chroma.persist_dir`.
- BM25 persistence is configured under `bm25.persist_path`.
- Retrieval behavior is configured under `retrieval.mode`, `retrieval.fusion`, `retrieval.rrf_k`, and `retrieval.identifier_boost`.

## Development Notes

- Prefer focused tests for new behavior.
- Use `rg`/`rg --files` for code search when available.
- Do not revert unrelated working tree changes.
- Preserve UTF-8 file content and explicitly specify file encodings in PowerShell commands.
