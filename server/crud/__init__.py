from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import update, select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import BooleanClauseList, BinaryExpression
from starlette import status


class CRUDBase:
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, conditions: tuple, options: Optional[list] = None):
        stmt = select(self.model).where(*conditions)
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
        order_by: Optional[tuple] = None,
        join: Optional[List[tuple]] = None,
        outerjoin: Optional[List[tuple]] = None,
        conditions: Optional[tuple] = None,
        with_only_columns: Optional[tuple] = None,
        group_by: Optional[tuple] = None,
        having: Optional[BooleanClauseList | BinaryExpression] = None,
        options: Optional[list] = None
    ):
        stmt = select(self.model).offset(offset).limit(limit)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if conditions:
            stmt = stmt.where(*conditions)
        if group_by:
            stmt = stmt.group_by(*group_by)
        if having is not None:
            stmt = stmt.having(having)
        if join:
            for j in join:
                stmt = stmt.join(*j)
        if outerjoin:
            for j in outerjoin:
                stmt = stmt.outerjoin(*j)
        if options:
            for o in options:
                stmt = stmt.options(o)
        if with_only_columns:
            stmt = stmt.with_only_columns(*with_only_columns)
            return (row for row in await self.session.execute(stmt))

        results = await self.session.execute(stmt)
        return results.scalars().all()

    async def create(self, **kwargs):
        instance = self.model(**kwargs)
        self.session.add(instance)
        return instance

    async def bulk_create(self, values=List[Dict[str, Any]]):
        stmt = insert(self.model).values(values)
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

    async def bulk_update(self, values: List[Dict[str, Any]]):
        return await self.session.execute(update(self.model), values)

    async def delete(self, conditions: tuple):
        stmt = delete(self.model).where(*conditions)
        await self.session.execute(stmt)
