from __future__ import annotations

from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from .db import ComicFile, Resource


class ResourceRepository:
    def __init__(self, session: Session):
        self.session = session

    def search(
        self,
        keyword: str,
        resource_type: str | None,
        limit: int,
        offset: int,
    ) -> Sequence[Resource]:
        query = self.session.query(Resource)
        like_pattern = f"%{keyword}%"
        query = query.filter(Resource.title.ilike(like_pattern))
        if resource_type and resource_type != "all":
            query = query.filter(Resource.type == resource_type)
        return (
            query.order_by(Resource.is_vip.desc(), Resource.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count_by_type(self, keyword: str) -> dict[str, int]:
        like_pattern = f"%{keyword}%"
        rows: Iterable[tuple[str, int]] = (
            self.session.query(Resource.type, func.count(Resource.id))
            .filter(Resource.title.ilike(like_pattern))
            .group_by(Resource.type)
            .all()
        )
        result = {resource_type: count for resource_type, count in rows}
        result["all"] = sum(result.values())
        return result

    def get(self, resource_id: str) -> Resource | None:
        return self.session.get(Resource, resource_id)

    def list_comic_files(
        self, resource_id: str, *, limit: int, offset: int
    ) -> Sequence[ComicFile]:
        return (
            self.session.query(ComicFile)
            .filter(ComicFile.resource_id == resource_id)
            .order_by(asc(ComicFile.order))
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count_comic_files(self, resource_id: str) -> int:
        return (
            self.session.query(func.count(ComicFile.id))
            .filter(ComicFile.resource_id == resource_id)
            .scalar()
            or 0
        )

