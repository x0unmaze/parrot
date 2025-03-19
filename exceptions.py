'''
Exceptions for the Nightingale project.
'''


class UnknownResponse(Exception):
    '''Raised when an unknown response is received from the server.'''


class UnknownMetadataResponse(UnknownResponse):
    '''Raised when an unknown metadata is received from the server.'''


class UnexpectedResponse(Exception):
    '''Raised when an unexpected response is received from the server.'''


class MissingAudioData(UnexpectedResponse):
    '''Raised when received a binary message, but it is missing the audio data.'''


class NoAudioReceived(Exception):
    '''Raised when no audio is received from the server.'''


class WebSocketError(Exception):
    '''Raised when a WebSocket error occurs.'''
