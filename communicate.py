'''
Communicate
'''


import re
import ssl
import json
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Optional,
    Tuple,
    Union,
)

import aiohttp
import certifi
from .utils import (
    connect_id,
    date_to_string,
    is_voice_format,
)

from .constants import WSS_URL
from .exceptions import (
    MissingAudioData,
    NoAudioReceived,
    UnexpectedResponse,
    UnknownMetadataResponse,
    UnknownResponse,
    WebSocketError,
)


def get_headers_and_data(data: Union[str, bytes]) -> Tuple[Dict[bytes, bytes], bytes]:
    '''
    Returns the headers and data from the given data.

    Args:
        data (str or bytes): The data to be parsed.

    Returns:
        tuple: The headers and data to be used in the request.
    '''
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, bytes):
        raise TypeError("data must be str or bytes")

    headers = {}
    for line in data[: data.find(b"\r\n\r\n")].split(b"\r\n"):
        key, value = line.split(b":", 1)
        headers[key] = value

    return headers, data[data.find(b"\r\n\r\n") + 4:]


def mkssml(text: Union[str, bytes], voice: str, rate: str, volume: str, pitch: str) -> str:
    '''
    Creates a SSML string from the given parameters.

    Returns:
        str: The SSML string.
    '''
    if isinstance(text, bytes):
        text = text.decode("utf-8")

    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='{voice}'>"
        f"<prosody pitch='{pitch}' rate='{rate}' volume='{volume}'>{text}</prosody>"
        f"</voice></speak>"
    )
    return ssml


def ssml_headers_and_data(request_id: str, timestamp: str, ssml: str) -> str:
    """
    Returns the headers and data to be used in the request.

    Returns:
        str: The headers and data to be used in the request.
    """

    return (
        f"X-RequestId:{request_id}\r\n"
        f"X-Timestamp:{timestamp}Z\r\n"
        "Content-Type:application/ssml+xml\r\n"
        "Path:ssml\r\n\r\n"
        f"{ssml}"
    )


class Communicate:
    '''
    Class for communicating with the service.
    '''

    def __init__(
        self,
        text: str,
        voice: str = "Microsoft Server Speech Text to Speech Voice (en-US, AriaNeural)",
        *,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        proxy: Optional[str] = None,
        sentence_boundary: bool = False,
        word_boundary: bool = False,
    ):
        """
        Initializes the Communicate class.

        Raises:
            ValueError: If the voice is not valid.
        """
        self.text: str = text
        self.voice: str = voice
        self.word_boundary = word_boundary
        self.sentence_boundary = sentence_boundary

        match = is_voice_format(voice)
        if match is not None:
            lang = match.group(1)
            region = match.group(2)
            name = match.group(3)
            if name.find("-") != -1:
                region = region + "-" + name[: name.find("-")]
                name = name[name.find("-") + 1:]
            self.voice = (
                "Microsoft Server Speech Text to Speech Voice"
                + f" ({lang}-{region}, {name})"
            )

        if (
            re.match(
                r"^Microsoft Server Speech Text to Speech Voice \(.+,.+\)$",
                self.voice,
            )
            is None
        ):
            raise ValueError(f"Invalid voice '{voice}'.")

        if re.match(r"^[+-]\d+%$", rate) is None:
            raise ValueError(f"Invalid rate '{rate}'.")
        self.rate: str = rate

        if re.match(r"^[+-]\d+%$", volume) is None:
            raise ValueError(f"Invalid volume '{volume}'.")
        self.volume: str = volume

        if re.match(r"^[+-]\d+Hz$", pitch) is None:
            raise ValueError(f"Invalid pitch '{pitch}'.")
        self.pitch: str = pitch

        if proxy is not None and not isinstance(proxy, str):
            raise TypeError("proxy must be str")
        self.proxy: Optional[str] = proxy

    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        '''Streams audio and metadata from the service.'''

        headers = {
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/91.0.4472.77 Safari/537.36 Edg/91.0.864.41"
            ),
        }

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        audio_was_received = False
        async with aiohttp.ClientSession(trust_env=True) as session, session.ws_connect(
            f"{WSS_URL}&ConnectionId={connect_id()}",
            compress=15,
            autoclose=True,
            autoping=True,
            proxy=self.proxy,
            headers=headers,
            ssl=ssl_ctx,
        ) as websocket:
            # Each message needs to have the proper date.
            date = date_to_string()

            metadata_options = {
                "sentenceBoundaryEnabled": str(self.sentence_boundary),
                "wordBoundaryEnabled": str(self.word_boundary),
            }

            speech_config = {
                "context": {
                    "synthesis": {
                        "audio": {
                            "metadataoptions": metadata_options,
                            "outputFormat": "audio-24khz-48kbitrate-mono-mp3"
                        }
                    }
                }
            }

            await websocket.send_str(
                f"X-Timestamp:{date}\r\n"
                "Content-Type:application/json; charset=utf-8\r\n"
                "Path:speech.config\r\n\r\n"
                f'{json.dumps(speech_config)}\r\n'
            )

            await websocket.send_str(ssml_headers_and_data(
                connect_id(),
                date,
                mkssml(self.text, self.voice, self.rate,
                       self.volume, self.pitch),
            ))

            async for received in websocket:
                if received.type == aiohttp.WSMsgType.TEXT:
                    encoded_data: bytes = received.data.encode("utf-8")
                    parameters, data = get_headers_and_data(encoded_data)
                    path = parameters.get(b"Path")
                    if path == b"turn.end":
                        break
                    elif path in (b'response', b'turn.start'):
                        continue
                    elif path == b"audio.metadata":
                        for item in json.loads(data)["Metadata"]:
                            meta_type = item["Type"]
                            if meta_type == "SessionEnd":
                                continue
                            elif meta_type in ('WordBoundary', 'SentenceBoundary'):
                                offset = item['Data']['Offset']
                                duration = item['Data']['Duration']
                                text = item['Data']['text']['Text']
                                yield {
                                    "type": meta_type,
                                    "timestamp": (offset, offset + duration),
                                    "text": text,
                                }
                            else:
                                raise UnknownMetadataResponse(meta_type)
                    else:
                        raise UnknownResponse(received.data)
                elif received.type == aiohttp.WSMsgType.BINARY:
                    if len(received.data) < 2:
                        raise UnexpectedResponse(
                            "We received a binary message, but it is missing the header length."
                        )

                    # See: https://github.com/microsoft/cognitive-services-speech-sdk-js/blob/d071d11/src/common.speech/WebsocketMessageFormatter.ts#L46
                    header_length = int.from_bytes(received.data[:2], "big")
                    if len(received.data) < header_length + 2:
                        raise MissingAudioData()

                    yield {
                        "type": "audio",
                        "data": received.data[header_length + 2:],
                    }
                    audio_was_received = True
                elif received.type == aiohttp.WSMsgType.ERROR:
                    raise WebSocketError(
                        received.data if received.data else "Unknown error"
                    )

            if not audio_was_received:
                raise NoAudioReceived("Please verify that your parameters are correct.")
