from fastapi import APIRouter

from server.api import ExceptionHandlerRoute

router = APIRouter(route_class=ExceptionHandlerRoute)
