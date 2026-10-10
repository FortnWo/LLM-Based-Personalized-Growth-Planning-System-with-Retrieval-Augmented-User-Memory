"""Rebuild the optional Qdrant index from MySQL memory facts."""

from __future__ import annotations

import argparse
import json

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.memory_embedding import MemoryEmbedding
from app.models.ukl_slice import UklSlice
from app.services import vector_store


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    db = SessionLocal()
    try:
        query = (
            db.query(MemoryEmbedding, UklSlice)
            .join(UklSlice, UklSlice.id == MemoryEmbedding.slice_id)
            .filter(MemoryEmbedding.model == settings.EMBEDDING_MODEL)
            .order_by(MemoryEmbedding.id.asc())
        )
        if args.user_id is not None:
            query = query.filter(MemoryEmbedding.user_id == args.user_id)
        if args.limit is not None:
            query = query.limit(max(args.limit, 0))
        rows = query.all()

        if args.dry_run:
            print(f"would index {len(rows)} memory facts")
            return 0
        if not vector_store.is_enabled():
            raise RuntimeError("Enable VECTOR_STORE_ENABLED and set VECTOR_STORE_BACKEND=qdrant first")
        if args.rebuild:
            vector_store.recreate_collection(vector_size=settings.EMBEDDING_DIMENSIONS)
        else:
            vector_store.ensure_collection(vector_size=settings.EMBEDDING_DIMENSIONS)

        indexed = 0
        for embedding_row, slice_row in rows:
            vector = json.loads(embedding_row.embedding_json)
            if not isinstance(vector, list) or not vector:
                continue
            payload = json.loads(slice_row.payload or "{}")
            vector_store.upsert_memory_fact(
                slice_id=slice_row.id,
                embedding=[float(value) for value in vector],
                payload={
                    "user_id": embedding_row.user_id,
                    "slice_id": slice_row.id,
                    "model": embedding_row.model,
                    "dimensions": embedding_row.dimensions,
                    "fact": str(payload.get("fact") or ""),
                    "salience": float(payload.get("salience") or 0.0),
                    "session_id": payload.get("session_id"),
                    "message_id": payload.get("message_id"),
                },
            )
            indexed += 1
        print(f"indexed {indexed} memory facts")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())