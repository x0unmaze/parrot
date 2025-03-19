from typing import Dict, List, Tuple
from .utils import format_cue


class Subtitle:
    '''
    Subtitle
    '''

    def __init__(self):
        self.sentences: List[Dict[Tuple[float, float], str]] = []
        self.words: List[Dict[Tuple[float, float], str]] = []

    def sentence(self, timestamp: Tuple[float, float], text: str):
        self.sentences.append({'timestamp': timestamp, 'text': text})

    def word(self, timestamp: Tuple[float, float], text: str):
        self.words.append({'timestamp': timestamp, 'text': text})

    def generate_word_subtitle(self, words_in_cue: int = 1) -> str:
        cues: List[str] = []
        index: int = 0
        start: float = 0
        words: List[str] = []

        for i in range(len(self.words)):
            segment = self.words[i]
            value = segment['text'].strip()
            time_start, time_end = segment['timestamp']
            words.append(value)
            if len(words) == 1:
                start = time_start
            if len(words) == words_in_cue or value in ('.', ',', '?') or len(self.words) == i + 1:
                index += 1
                cue = format_cue(index, start, time_end, ' '.join(words))
                cues.append(cue)
                words = []
        return ''.join(cues)

    def generate_sentence_subtitle(self) -> str:
        cues = []
        for i in range(len(self.sentences)):
            segment = self.sentences[i]
            value = segment['text']
            time_start, time_end = segment['timestamp']
            cues.append(format_cue(i, time_start, time_end, value))
        return ''.join(cues)
