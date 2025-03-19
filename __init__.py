'''
__init__ for nightingale library
'''

from .exceptions import *
from .communicate import Communicate
from .subtitle import Subtitle

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