from server.crud import CRUDBase
from server.models import ChatRoom, ChatRoomUserAssociation, ChatHistory


class ChatRoomCRUD(CRUDBase):
    model = ChatRoom


class ChatRoomUserAssociationCRUD(CRUDBase):
    model = ChatRoomUserAssociation


class ChatHistoryCRUD(CRUDBase):
    model = ChatHistory
