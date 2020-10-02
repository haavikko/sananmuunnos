import collections
from enum import Enum
from io import StringIO
'''
Design considerations:


Notes on data structures:
* Considered storing the character data in a deque. In testing, deque uses
  8x more memory than a plain string.

Notes on streaming output:
* In the worst case, streaming output is not useful at all. For example, if input is
  "aaaaa bbbb", then 
case that the input string consists of two very long words
streaming output is not useful at all. 

Notes on streaming output:
* The output is produced piecemeal by a generator, so the full output string does not
  need to fit in memory.  
* This way, we can start producing the response to the client sooner, and the full
  response does not need to stay in memory.
* On the other hand, in a WSGI application, it is not desirable to generate the response
  one or a few characters at a time as that will result in bad performance in many
  environments.

Notes on streaming input:
Currently, the input is loaded fully in memory before performing JSON decoding, and the decoded
JSON string is also fully loaded in memory.
This project uses the standard library json module, and it does not support decoding JSON strings to/from
a stream (see py_scanstring and c_scanstring in json module sources). If support for really
large inputs is needed, a streaming JSON string parser is needed.
'''

__all__ = ['transform_words']

VOWEL_CHARS = 'aeiouyåäö'
SPACE_CHARS = ' '

class WordTransformException(Exception):
    pass

class TokenType(Enum):
    SPACE = 1
    WORD_FIRST_PART = 2
    WORD_SECOND_PART = 3

Token = collections.namedtuple('Token', ['token_type', 'string_value'])

class CharacterType(Enum):
    SPACE = 1
    VOWEL = 2
    CONSONANT = 3
    EOF = 4

class ParserState(Enum):
    INIT = 1
    READ_SPACE = 2
    READ_WORD_FIRST_PART = 3
    READ_WORD_SECOND_PART = 4
    END_OF_INPUT = 5

def get_character_type(char):
    if char is EOF:
        return CharacterType.EOF
    if char in SPACE_CHARS:
        return CharacterType.SPACE
    elif char in VOWEL_CHARS:
        return CharacterType.VOWEL
    else:
        return CharacterType.CONSONANT

EOF = object() # sentinel - marker of end of input in state machine

Transition = collections.namedtuple('Transition', ['next_state', 'callback'])

class ParserState:
    def __init__(self, token_type):
        self.token_type = token_type
        self.transitions = {}

    def __str__(self):
        return f'ParserState {self.token_type}'

    def process_state(self, current_char):
        '''
        Processing a state consists of these steps:
         * Determining the next state to transition to, based on input character
         * Executing a callback. The callback may

        :param current_char:
        :return: Two-element tuple, where
        * The first element is the next state the state machine should transition to
        * The second element is either None or a newly parsed complete Token
        '''
        transition = self.transitions[get_character_type(current_char)]
        return transition.next_state, transition.callback()

    def add_transition(self, char_type, next_state, callback):
        '''
        Define a state transition.

        :param char_type:
        :param next_state:
        :param callback:
        :return: None
        '''
        if callback is None:
            callback = lambda: None # by default, no action
        self.transitions[char_type] = Transition(next_state, callback)

class Parser:
    def __init__(self, input_string):
        self.input_string = input_string
        self.current_char_idx = 0 # current position of the parser in the input_string
        self.current_state = self.initialize_state_machine()
        self.current_token_buffer = StringIO() # the content of token currently being constructed

    def initialize_state_machine(self):
        '''
        Initialize the states and state transitions of the state machine.
        :return: initial state
        '''
        init = ParserState(TokenType.SPACE) # if no input, treat it as a zero-length space
        read_space = ParserState(TokenType.SPACE)
        read_word_first_part = ParserState(TokenType.WORD_FIRST_PART)
        read_vowels = ParserState(TokenType.WORD_FIRST_PART)
        read_word_second_part = ParserState(TokenType.WORD_SECOND_PART)
        end_of_input = ParserState(None) # no token generated

        # Processing the initial state does not consume any characters, just select the next state
        # based on the first character in string
        init.add_transition(CharacterType.SPACE, None, read_space)
        init.add_transition(CharacterType.VOWEL, None, read_word_first_part)
        init.add_transition(CharacterType.CONSONANT, None, read_word_first_part)
        init.add_transition(CharacterType.EOF, self.finish_token, end_of_input)

        # Start reading from start of the word
        read_word_first_part.add_transition(CharacterType.SPACE, self.finish_token, read_space)
        read_word_first_part.add_transition(CharacterType.VOWEL, self.consume_char, read_vowels)
        read_word_first_part.add_transition(CharacterType.CONSONANT, self.consume_char, read_word_first_part)
        read_word_first_part.add_transition(CharacterType.EOF, self.finish_token, end_of_input)

        # Read consecutive vowels
        read_vowels.add_transition(CharacterType.SPACE, self.finish_token, read_space)
        read_vowels.add_transition(CharacterType.VOWEL, self.consume_char, read_vowels)
        read_vowels.add_transition(CharacterType.CONSONANT, self.finish_token, read_word_second_part)
        read_vowels.add_transition(CharacterType.EOF, self.finish_token, end_of_input)

        # Read the rest of the word. Word is terminated by space or EOF.
        read_word_second_part.add_transition(CharacterType.SPACE, self.finish_token, read_space)
        read_word_second_part.add_transition(CharacterType.VOWEL, self.consume_char, read_word_second_part)
        read_word_second_part.add_transition(CharacterType.CONSONANT, self.consume_char, read_word_second_part)
        read_word_second_part.add_transition(CharacterType.EOF, self.finish_token, end_of_input)

        return init

    def generate_tokens(self):

        self.current_state = self.initialize_state_machine()

        while self.current_char is not EOF:
            prev_state = self.current_state
            prev_idx = self.current_char_idx
            self.current_state, finished_token = self.current_state.process_state(self.current_char)
            if finished_token:
                yield finished_token

            if self.current_state is prev_state and prev_idx == self.current_char_idx:
                raise WordTransformException(f'State machine is stuck at {self.current_state} '
                                             f'char_idx={prev_idx}({self.current_char})')

    @property
    def current_char(self):
        return self.input_string[self.current_char_idx]

    def next_char(self):
        if self.current_char_idx >= len(self.input_string):
            return EOF
        self.current_char_idx += 1
        return self.current_char

    def peek_char(self):
        if self.current_char_idx + 1 >= len(self.input_string):
            return EOF
        return self.input_string[self.current_char_idx + 1]

    def consume_char(self):
        self.current_token_buffer.write(self.current_char)
        self.next_char()

    def finish_token(self):
        self.current_state.finished_token = Token(self.current_state.token_type,
                                                  self.current_token_buffer.getvalue())
        self.current_token_buffer = StringIO() # creating new StringIO is faster than truncating









def transform_words(json_string):
    '''
    Transform a JSON string string with the following rules:

    For each pair of words, swap the beginnings of the words, up to and including the first vowel (and any consecutive vowels) of the word.
    >> transform_words('"fooma barbu"')
    '"bama foorbu"'

    If there is an odd word at the end of the string, it is left as is.

    >>> transform_words('"hello"')
    '"hello"'

    >>> transform_words('"foo bar baz"')
    '"ba foor baz"'

    Words are separated by spaces; exact spacing is preserved
    >>> transform_words('"amama   bomomo foo"')
    "bomama   amomo foo"

    Punctuation is treated as part of words.
    >>> transform_words('"I'd rather die here."')
    '"ra'd Ither he diere."'

    Vowels include those in the Finnish alphabet (a, e, i, o, u, y, å, ä, ö),

    >>> transform_words('"vuoirkage mäölnö")
    '"mäörkage vuoilnö"'

    Any character that is not space or a vowel is treated as a consonant.

    * Leading space in the input string is also preserved
    * Only the space character is interpreted as space, not other white space characters
    * Input string must be wrapped in quotes
    * Input does not need to contain a single word to be valid

    :param json_string: quoted string that pertain to JSON formatting
    :return:  The returned value is a quoted string that pertain to JSON formatting
    '''

    decoded_input = json.loads(json_string)


    pending_tokens = []
    for token in token_generator():
        if token.token_type == TokenType.WORD_FIRST_PART:
            assert(len(pending_tokens == 0))
            pending_tokens.add(token)
        elif token.token_type == TokenType.WORD_SECOND_PART:
            assert (len(pending_tokens > 0))
            pending_tokens.add(token)
            fixme - second word
            pending_tokens[0], pending_tokens[-1] = pending_tokens[-1], pending_tokens[0]
        elif len(pending_tokens) == 0:
            yield token.string_value
