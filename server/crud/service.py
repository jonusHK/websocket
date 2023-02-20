from server.crud import CRUDBase
from server.models import ChatRoom, ChatRoomUserAssociation, ChatHistory, ChatHistoryFile, ChatHistoryUserAssociation


class ChatRoomCRUD(CRUDBase):
    model = ChatRoom


class ChatRoomUserAssociationCRUD(CRUDBase):
    model = ChatRoomUserAssociation


class ChatHistoryCRUD(CRUDBase):
    model = ChatHistory


class ChatHistoryFileCRUD(CRUDBase):
    model = ChatHistoryFile


class ChatHistoryUserAssociationCRUD(CRUDBase):
    model = ChatHistoryUserAssociation
