import typing

from starlette.responses import JSONResponse

from server.core.enums import ResponseCode


class WebsocketJSONResponse(JSONResponse):
    def render(self, content: typing.Union[list, dict]) -> bytes:
        response = ResponseCode.OK.retrieve()
        response.update({'data': content})

        if isinstance(content, list):
            response.update({'total': len(content)})

        return super().render(response)
