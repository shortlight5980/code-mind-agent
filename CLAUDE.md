# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Running Tests
```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests/test_index_repo_split.py

# Run specific test class/method
python -m unittest tests.test_index_repo_split.PythonAstSplitTests
python -m unittest tests.test_index_repo_split.PythonAstSplitTests.test_keeps_small_class_as_single_block_with_decorators
```

### Running the Application
```bash
# Start the FastAPI server
python app.py

# Or with uvicorn
uvicorn app:app --reload
```

### Indexing a Repository
```bash
# Index using config.yml repo.path
python scripts/index_repo.py

# Index specific directory
python scripts/index_repo.py /path/to/repo

# Index with custom persist directory
python scripts/index_repo.py /path/to/repo --persist-dir ./my_chroma_db
```

## High-Level Architecture

### Core Architecture
This is a RAG-based (Retrieval-Augmented Generation) code repository Q&A system with an Agent-based architecture:

```
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
    ├→ Summarizer LLM
    └→ PromptManager (prompts/prompt_manager.py)
```

### Key Design Decisions

1. **ServiceManager Singleton Pattern**: All core services (Agent, Vector DB, LLMs) are managed by a single `ServiceManager` instance initialized in the FastAPI lifespan. Tools access services via global injection.

2. **Python AST-based Code Splitting**: The RAG system uses AST parsing for intelligent Python code chunking (preserves class/function boundaries) with a fallback indentation-scanner for invalid Python. Located in `scripts/index_repo.py`.

3. **Two-Tier Retrieval**: Code and documents are retrieved separately with configurable `retrieval_k` values (defaults: docs=5, codes=10), then passed through a summarization layer before being given to the main LLM.

4. **Security-First Tool Design**: All file/command operations go through `agent/security.py` which validates:
   - Paths are within allowed directories (normalizes `../`)
   - Files aren't sensitive (`.env`, `*.pem`, `*.key`, etc.)
   - Commands are whitelisted and don't have dangerous args (e.g., `ls -R` is blocked)

### Important File Relationships

| File | Depends On | Purpose |
|------|-----------|--------|
| `app.py` | `services/service_manager.py`, `agent/streaming.py` | FastAPI entrypoint, lifespan manages ServiceManager |
| `services/service_manager.py` | `agent/agent.py`, `utils/config.py`, `utils/summarizer.py` | Initializes and provides access to all services |
| `agent/agent.py` | `agent/tools/*`, `prompts/prompt_manager.py` | Creates LangChain Agent with tools |
| `agent/tools/retrieve_and_summarize.py` | `utils/summarizer.py` | RAG tool that accesses Vector DB via ServiceManager |
| `scripts/index_repo.py` | `utils/config.py`, `utils/logger.py` | Indexes repo using AST-based splitting |

### Data Flow for a Chat Request

1. User POSTs `/chat` → FastAPI route handler
2. Gets `service_manager.agent`
3. Calls `agent.aexecute(question, history)`
4. Agent may decide to use `RetrieveAndSummarize` tool
5. Tool does async similarity search on Chroma (code+docs separately)
6. Results passed through summarizer LLM
7. Agent generates final answer from tool results
8. JSON response returned

### Configuration

- Main config: `config.yml` (loaded by `utils/config.Config`)
- Environment secrets: `.env` (DASHSCOPE_API_KEY required)
- Chroma DB persistence directory configured in `config.yml`
