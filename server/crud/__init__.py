from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import update, select, insert, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status


class CRUDBase:
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, conditions: tuple, options: Optional[list] = None):
        stmt = (
            select(self.model).
            where(*conditions)
        )
        if options:
            for option in options:
                stmt = stmt.options(option)
        results = await self.session.execute(stmt)
        instance = results.scalars().one_or_none()
        if instance is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found {self.model.__name__}.")
        return instance

    async def list(
        self,
        offset=0,
        limit=100,
        order_by: Optional[tuple] = tuple(),
        conditions: Optional[tuple] = tuple(),
        options: Optional[list] = None
    ):
        stmt = (
            select(self.model).
            offset(offset).
            limit(limit).
            where(*conditions).
            order_by(*order_by)
        )
        if options:
            for option in options:
                stmt = stmt.options(option)
        results = await self.session.execute(stmt)
        return results.scalars().all()

    async def create(self, **kwargs):
        instance = self.model(**kwargs)
        self.session.add(instance)
        return instance

    async def bulk_create(self, values=List[Dict[str, Any]]):
        stmt = (
            insert(self.model).
            values(values)
        )
        await self.session.execute(stmt)

    async def update(self, values: dict, conditions: tuple):
        stmt = (
            update(self.model).
            where(*conditions).
            values(**values).
            execution_options(synchronize_session="fetch")
        )
        result = await self.session.execute(stmt)
        return result
