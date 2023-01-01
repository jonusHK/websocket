from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.api import ExceptionHandlerRoute
from server.crud.service import ChatRoomUserAssociationCRUD
from server.db.databases import get_async_session
from server.models import ChatRoomUserAssociation
from server.schemas.service import ChatRoomUserAssociationS

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.get(
    '/rooms/mapping/{user_profile_id}/{chat_room_id}',
    response_model=ChatRoomUserAssociationS
)
async def get_room_user_mapping(
    user_profile_id: int,
    chat_room_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    room_user_mapping: ChatRoomUserAssociation = await crud_room_user_mapping.get(
        conditions=(
            ChatRoomUserAssociation.user_profile_id == user_profile_id,
            ChatRoomUserAssociation.room_id == chat_room_id))

    return ChatRoomUserAssociationS.from_orm(room_user_mapping)
