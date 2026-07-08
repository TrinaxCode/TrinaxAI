"""Chat routes — POST /v1/chat/completions

Currently defined in rag_api.py. Will be migrated here incrementally.
See app/services/rag_service.py for extracted RAG engine logic.
"""

# Route registration happens in rag_api.py for now.
# When migrated, this module will contain:
#   from fastapi import APIRouter
#   router = APIRouter()
#   @router.post("/v1/chat/completions")
#   async def chat(...): ...
