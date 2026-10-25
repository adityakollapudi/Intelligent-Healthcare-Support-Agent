"""Trusted knowledge corpus (doc 05 §2.7–2.8).

Embeddings are stored as REAL[] and compared in the application (deviation D4-01: pgvector is not
installed on the development PostgreSQL). Moving to pgvector only changes `embedding`'s type and
the similarity query in app/rag/store.py.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    REAL,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Synthetic, Timestamps, UUIDPrimaryKey

AUDIENCES = ("MEMBER", "PROVIDER", "SUPPORT_INTERNAL")
DOCUMENT_TYPES = ("BENEFIT_GUIDE", "FAQ", "PROCESS_MANUAL", "PA_REQUIREMENTS", "CLAIMS_GUIDE", "SUPPORT_PROCEDURE")
INGESTION_STATUSES = ("PENDING_INGESTION", "INGESTED", "INGESTION_FAILED")
LIFECYCLE_STATUSES = ("ACTIVE", "SUPERSEDED", "RETIRED")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class KnowledgeDocument(UUIDPrimaryKey, Synthetic, Timestamps, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("document_key", "version"),
        CheckConstraint(f"document_type IN ({_in(DOCUMENT_TYPES)})", name="document_type_valid"),
        CheckConstraint(f"ingestion_status IN ({_in(INGESTION_STATUSES)})", name="ingestion_status_valid"),
        CheckConstraint(f"lifecycle_status IN ({_in(LIFECYCLE_STATUSES)})", name="lifecycle_status_valid"),
        CheckConstraint(
            f"cardinality(audience) > 0 AND audience <@ ARRAY[{_in(AUDIENCES)}]::text[]", name="audience_valid"
        ),
        # At most one ACTIVE version per logical document.
        Index(
            "uq_knowledge_documents_active_key",
            "document_key",
            unique=True,
            postgresql_where=text("lifecycle_status = 'ACTIVE'"),
        ),
        Index(None, "audience", postgresql_using="gin"),
        Index(None, "lifecycle_status", "ingestion_status"),
    )

    document_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(250))
    version: Mapped[str] = mapped_column(String(30))
    document_type: Mapped[str] = mapped_column(String(30))
    audience: Mapped[list[str]] = mapped_column(ARRAY(Text))
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    effective_date: Mapped[date | None]  # NULL when the source states none; never inferred
    source_filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(20))  # markdown | text | pdf
    content_sha256: Mapped[str] = mapped_column(String(64))
    ingestion_status: Mapped[str] = mapped_column(String(30), server_default=text("'PENDING_INGESTION'"))
    ingestion_error_code: Mapped[str | None] = mapped_column(String(50))
    lifecycle_status: Mapped[str] = mapped_column(String(20), server_default=text("'ACTIVE'"))
    superseded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"))
    page_count: Mapped[int | None]
    chunk_count: Mapped[int] = mapped_column(server_default=text("0"))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    # Chunker version + parameters; a change forces re-indexing even if the file is unchanged.
    chunking_config: Mapped[str | None] = mapped_column(String(80))
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(UUIDPrimaryKey, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        CheckConstraint("char_end > char_start", name="char_range_valid"),
        CheckConstraint("cardinality(embedding) = embedding_dim", name="embedding_dim_matches"),
        Index(None, "content_tsv", postgresql_using="gin"),
        Index(None, "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]
    section_heading: Mapped[str | None] = mapped_column(String(300))
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    char_start: Mapped[int]
    char_end: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    content_tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(ARRAY(REAL))
    embedding_dim: Mapped[int]
    embedding_model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
