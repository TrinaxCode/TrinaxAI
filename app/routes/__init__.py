"""Domain routers that compose the TrinaxAI HTTP API."""

from .agent import router as agent_router
from .app_state import router as app_state_router
from .attachments import router as attachments_router
from .chat import router as chat_router
from .collections import router as collections_router
from .documents import router as documents_router
from .health import router as health_router
from .memory import router as memory_router
from .pairing import router as pairing_router
from .research import router as research_router
from .sources import router as sources_router
from .stats import router as stats_router
from .system import router as system_router
from .voice import router as voice_router
from .watcher import router as watcher_router

ROUTERS = (
    voice_router,
    chat_router,
    agent_router,
    sources_router,
    research_router,
    watcher_router,
    memory_router,
    pairing_router,
    stats_router,
    health_router,
    app_state_router,
    attachments_router,
    documents_router,
    collections_router,
    system_router,
)

__all__ = ["ROUTERS"]
