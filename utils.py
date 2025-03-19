import json
import math
import re
import ssl
import time
import uuid

from unidecode import unidecode
from typing import Any, Optional
import aiohttp
import certifi

from communicate import Communicate
from subtitle import Subtitle

from .constants import VOICE_LIST


def connect_id() -> str:
    '''
    Returns a UUID without dashes.

    Returns:
        str: A UUID without dashes.
    '''
    return str(uuid.uuid4()).replace('-', '')


def date_to_string() -> str:
    """
    Return Javascript-style date string.

    Returns:
        str: Javascript-style date string.
    """
    # %Z is not what we want, but it's the only way to get the timezone
    # without having to use a library. We'll just use UTC and hope for the best.
    # For example, right now %Z would return EEST when we need it to return
    # Eastern European Summer Time.
    return time.strftime(
        "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)", time.gmtime()
    )


def get_shortname(content: str, max: int = 26) -> str:
    '''
    Returns a short name for the given content, suitable for use as a slug.

    Args:
        content: The content to generate a short name from.
        max: The maximum length of the short name.

    Returns:
        The short name.
    '''
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", unidecode(content[0:max]))
    name = slug.lower()
    return name[:name.rfind('_')] if '_' in name else name


def is_voice_format(voice: str) -> bool:
    return re.match(r"^([a-z]{2,})-([A-Z]{2,})-(.+Neural)$", voice)


def is_rate_format(rate: str) -> bool:
    return re.match(r"^[+-]\d+%$", rate)


def is_volume_format(volume: str) -> bool:
    return re.match(r"^[+-]\d+%$", volume)


def is_pitch_format(pitch: str) -> bool:
    return re.match(r"^[+-]\d+Hz$", pitch)


def format_timestamp(unit: float) -> str:
    '''
    format_timestamp returns the timecode of the subtitle.

    The timecode is in the format of 00:00:00.000.

    Returns:
        str: The timecode of the subtitle.
    '''
    hour = math.floor(unit / 10**7 / 3600)
    minute = math.floor((unit / 10**7 / 60) % 60)
    seconds = (unit / 10**7) % 60
    return f"{hour:02d}:{minute:02d}:{seconds:06.3f}"


def format_cue(index: int, start: float, end: float, text: str) -> str:
    '''
    formatter returns the timecode and the text of the subtitle.
    '''
    return (
        f'{str(index)}\n'
        f'{format_timestamp(start)} --> {format_timestamp(end)}\n'
        f'{text.strip()}\n\n'
    )


async def list_voices(proxy: Optional[str] = None, locale: Optional[str] = None, limit: Optional[int] = None) -> Any:
    '''
    List all available voices and their attributes.

    This pulls data from the URL used by Microsoft Edge to return a list of
    all available voices.

    Returns:
        dict: A dictionary of voice attributes.
    '''
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(
            VOICE_LIST,
            headers={
                "Authority": "speech.platform.bing.com",
                "Sec-CH-UA": '" Not;A Brand";v="99", "Microsoft Edge";v="91", "Chromium";v="91"',
                "Sec-CH-UA-Mobile": "?0",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36 Edg/91.0.864.41",
                "Accept": "*/*",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
            },
            proxy=proxy,
            ssl=ssl_ctx,
        ) as url:
            data = json.loads(await url.text())
    if locale:
        data = [voice for voice in data if locale in voice.get("Locale")]
    if limit:
        data = data[:limit]
    return data


async def text_to_speech(text, voice: str = None, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz"):
    if not voice:
        voice = 'Microsoft Server Speech Text to Speech Voice (en-US, AriaNeural)'
    communicate = Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        word_boundary=True,
        sentence_boundary=True,
    )
    audio_chunks = []
    subtitle = Subtitle()
    async for item in communicate.stream():
        if item["type"] == "audio":
            audio_chunks.append(item["data"])
        if item['type'] == 'WordBoundary':
            subtitle.word(item['timestamp'], item['text'])
        if item['type'] == 'SentenceBoundary':
            subtitle.sentence(item['timestamp'], item['text'])

    audio_data = b"".join(audio_chunks)
    word_subtitle_content = subtitle.generate_word_subtitle()
    sentence_subtitle_content = subtitle.generate_sentence_subtitle()

    return audio_data, word_subtitle_content, sentence_subtitle_content
