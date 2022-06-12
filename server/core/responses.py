import typing

from starlette.responses import JSONResponse


class WebsocketJSONResponse(JSONResponse):
    def render(self, content: typing.Union[list, dict]) -> bytes:
        converted = {
            'response': 1,
            'data': content
        }
        if isinstance(content, list):
            converted.update({'total': len(content)})

        return super().render(converted)
