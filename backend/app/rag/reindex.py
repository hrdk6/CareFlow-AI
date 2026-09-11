"""Re-embed and re-index every current document (e.g. after changing the embedding model or chunking).

    uv run python -m app.rag.reindex
"""
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import Document
from app.rag.ingestion import process_document


def main() -> None:
    with get_session_factory()() as db:
        ids = list(db.scalars(select(Document.id).where(Document.is_current.is_(True)).order_by(Document.id)))
    for doc_id in ids:
        print(doc_id, process_document(doc_id))


if __name__ == "__main__":
    main()
