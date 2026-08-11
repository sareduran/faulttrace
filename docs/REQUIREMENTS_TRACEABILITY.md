# FaultTrace requirement traceability

This document maps the Foundry Local summer-school milestones to concrete implementation and verification evidence in the repository.

| Requirement | Status | Implementation evidence | Verification evidence |
|---|---|---|---|
| Original local RAG application | Complete | `app.py`, `src/faulttrace/analysis.py`, `src/faulttrace/qa.py` | Streamlit smoke test and live demo |
| User interface | Complete | Six-tab Streamlit interface in `app.py` | `tests/test_dashboard.py`, Streamlit AppTest |
| TXT/MD/PDF ingestion | Complete | `src/faulttrace/document_ingestion.py` | `tests/test_document_ingestion.py` |
| Heading-aware chunking | Complete | `chunk_content()` and `prepare_document_chunks()` in `src/faulttrace/knowledge_base.py` | `tests/test_knowledge_base.py` |
| Foundry Local embeddings | Complete | `FoundryEmbeddingService` using `qwen3-embedding-0.6b` | Six-case live retrieval evaluation |
| SQLite text and vector storage | Complete | `knowledge_chunks` schema in `src/faulttrace/knowledge_base.py` | index/search/replace/delete tests |
| Semantic top-K retrieval | Complete | cosine similarity and `limit=3` search | `tests/test_knowledge_base.py`, Evaluation tab |
| Foundry Local LLM | Complete | `FoundryChatService` using `qwen3.5-2b-text` | Deep analysis and Ask FaultTrace flows |
| Evidence-grounded answers | Complete | labelled `[L#]` and `[R#]` prompts | prompt-label and citation-audit tests |
| Insufficient-evidence fallback | Complete | calibrated `0.48` gate in `src/faulttrace/qa.py` | answerable/unanswerable tests and HR-policy evaluation case |
| Offline inference | Complete after setup | no cloud inference SDK; local Foundry models and SQLite | dependency review and local-only architecture |
| Functional tests | Complete | 33 automated tests in `tests/` | `python -m unittest discover -s tests -v` |
| Answerable/unanswerable/empty/broken input | Complete | parser and QA guards | explicit automated tests for all four classes |
| Retrieval evaluation | Complete | `src/faulttrace/evaluation.py` | 6/6 cases passing with the included custom runbook indexed |
| Performance measurement | Complete | retrieval, generation, and end-to-end timers in `app.py` | values displayed after local generation |
| README and limitations | Complete | `README.md` | installation, architecture, evaluation, privacy, limitations |
| Five-minute presentation/demo | Complete | versioned demo script in `docs/`; presentation prepared as a separate submission artifact | visually rendered and bounds-checked deck |
| GitHub delivery | Ready locally | clean Git repository scope and `.gitignore` | remote publishing requires project-owner account access |

## Current verification snapshot

- Automated tests: **33/33 passing**
- RAG cases: **6/6 passing**
- Streamlit automated render: **0 exceptions**
- Supported retrieval scores: approximately **0.563–0.848**
- Unsupported HR-policy score: **0.279**, correctly rejected below **0.48**

## Honest offline boundary

Python dependencies and Foundry Local model files require an initial internet-connected setup. Once models are cached, log parsing, document extraction, embeddings, retrieval, generation, evaluation, and persistence run locally without an external inference API.
