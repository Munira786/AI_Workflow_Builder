"""Keyset (cursor) pagination for "newest first" lists.

The cursor encodes the sort value and id of the last item returned. The next page continues
strictly after it, so rows inserted meanwhile never cause duplicates or gaps, and deep pages
cost the same as the first (unlike OFFSET).
"""

import base64
import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute, Session

MAX_PAGE_SIZE = 100


def encode_cursor(sort_value: datetime, item_id: str) -> str:
    raw = json.dumps([sort_value.isoformat(), item_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        sort_text, item_id = json.loads(base64.urlsafe_b64decode(padded))
        sort_value = datetime.fromisoformat(sort_text)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid cursor") from exc
    if sort_value.tzinfo is None:
        sort_value = sort_value.replace(tzinfo=UTC)
    return sort_value, str(item_id)


def paginate(
    db: Session,
    query: Select,
    sort_column: InstrumentedAttribute,
    id_column: InstrumentedAttribute,
    limit: int,
    cursor: str | None,
) -> tuple[list, str | None]:
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    if cursor:
        sort_value, item_id = decode_cursor(cursor)
        query = query.where(
            or_(
                sort_column < sort_value,
                and_(sort_column == sort_value, id_column < item_id),
            )
        )
    rows = list(db.scalars(query.order_by(sort_column.desc(), id_column.desc()).limit(limit + 1)))
    if len(rows) <= limit:
        return rows, None
    rows = rows[:limit]
    last = rows[-1]
    return rows, encode_cursor(getattr(last, sort_column.key), getattr(last, id_column.key))
