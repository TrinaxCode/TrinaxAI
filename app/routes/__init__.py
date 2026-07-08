"""TrinaxAI route modules.

Each module will eventually contain an APIRouter with the endpoints
for its domain. During the incremental migration, endpoints still
live in rag_api.py and are registered on the FastAPI app there.

Migration order (recommended):
  1. health.py   — simplest, no dependencies
  2. stats.py    — local analytics
  3. collections.py — CRUD with persistence
  4. memory.py   — user memory CRUD
  5. sources.py  — knowledge browser
  6. system.py   — most complex, security-sensitive
  7. chat.py     — core RAG streaming, highest traffic
"""
