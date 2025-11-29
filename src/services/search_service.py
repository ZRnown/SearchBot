from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories import ResourceRepository
from ..renderers import ResourceView


@dataclass
class SearchResult:
    counts: dict[str, int]
    rows: list[ResourceView]
    total_pages: int


class SearchService:
    def __init__(self, session: Session):
        self.repo = ResourceRepository(session)

    def run(self, *, keyword: str, category: str, page: int) -> SearchResult:
        page = max(page, 1)
        limit = settings.bot.page_size
        offset = (page - 1) * limit
        rows = self.repo.search(
            keyword=keyword,
            resource_type=category,
            limit=limit,
            offset=offset,
        )
        counts = self.repo.count_by_type(keyword)
        key = category if category in ("novel", "audio", "comic") else "all"
        total_rows = counts.get(key, 0)
        total_pages = max((total_rows + limit - 1) // limit, 1)
        view_rows = [
            ResourceView(
                id=row.id,
                title=row.title,
                type=row.type,
                is_vip=row.is_vip,
                jump_url=row.jump_url,
                preview_msg_id=row.preview_message_id,
                preview_url=row.preview_url,
            )
            for row in rows
        ]
        return SearchResult(counts=counts, rows=view_rows, total_pages=total_pages)

