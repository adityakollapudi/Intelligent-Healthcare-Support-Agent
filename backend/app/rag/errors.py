"""RAG failure types. A technical failure is never reported as "no information found"."""

from app.core.exceptions import AppError


class AIServiceUnavailableError(AppError):
    """Embedding model or LLM failed, timed out, was rate limited, or returned unusable output."""

    status_code = 503
    code = "AI_SERVICE_UNAVAILABLE"
    message = "The assistant is unavailable right now. Please try again shortly."

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason  # logged, never returned to the client


class IngestionError(Exception):
    """A single source document could not be ingested; `code` is stored on the document row."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
