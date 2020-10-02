import collections
from enum import Enum
from io import StringIO
import json

'''
Coding exercise for KuVa DPS. See description in transform_words()

Interpretation of the specification:
* Leading and trailing space in the input string is preserved
* Only the space character is interpreted as space, not other white space characters
* An input containing zero words is also valid, and is returned as is

Design considerations:

* At the first glance, the assignment could be done with some kind of nested loop.
  This would result in highly unmaintainable code.
* A state machine is a much better fit for the problem.
* I also considered using regular expressions, but decided against it.
  In a one-off personal project, I might have used RE's, but the purpose of the
  coding exercise is to produce readable and maintainable code.
  Regular expressions would make the code shorter, but harder to maintain.

Naming considerations:
* I considered using "tokenizer" or "lexer" but ended up with WordParser.
  "Parsing" is a good general term that fits well in this kind of string processing.   

Data structures:
* I also considered storing the decoded characters in a deque. In testing, deque used
  8x more memory than a plain string. so I decided to use the decoded json string as is.

Notes on streaming input:
* Initially, I thought about implementing the algorithm in a way that does not require
  reading the full input in memory, but decided against it.
* Currently, the input is loaded fully in memory before performing JSON decoding, and the decoded
  JSON string is also fully loaded in memory.
  This project uses the standard library json module, which does not support decoding JSON strings to/from
  a stream (see py_scanstring and c_scanstring in json module sources). If support for really
  large inputs is needed, a streaming JSON string parser is needed.

Notes on streaming output:
* The output is produced piecemeal by a generator, so the full output string does not
  need to fit in memory in many cases.
* In the worst case, streaming output does not help with memory footprint. For example, if input is
  "aaaaa bbbb", then the system must read until end of input before outputting anything to the client. 

I considered using Django StreamingHttpResponse.
* This way, we can start producing the response to the client sooner, and the full
  response does not need to stay in memory.
* On the other hand, in a WSGI application, it is not desirable to generate the response
  one or a few characters at a time as that will result in bad performance in many
  environments.

'''

__all__ = ['transform_words']

VOWEL_CHARS = 'aeiouyåäö'
SPACE_CHARS = ' '


class WordTransformException(Exception):
    pass

class WordTransformLogicError(Exception):
    '''
    Indicates that the algorithm encountered an internal error and could not process the data.
    '''
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


'''
class ParserState(Enum):
    INIT = 1
    READ_SPACE = 2
    READ_WORD_FIRST_PART = 3
    READ_WORD_SECOND_PART = 4
    END_OF_INPUT = 5
'''

def get_character_type(char):
    if char is EOF:
        return CharacterType.EOF
    assert (isinstance(char, str) and len(char) == 1)
    if char in SPACE_CHARS:
        return CharacterType.SPACE
    elif char in VOWEL_CHARS:
        return CharacterType.VOWEL
    else:
        return CharacterType.CONSONANT


EOF = object()  # sentinel - marker of end of input in state machine

Transition = collections.namedtuple('Transition', ['next_state', 'callback'])


class ParserState:
    def __init__(self, token_type):
        self.token_type = token_type
        self.transitions = {}

    def __str__(self):
        return f'ParserState {self.token_type}'

    def __repr__(self):
        return str(self)

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

    def add_transition(self, char_type, callback, next_state):
        '''
        Define a state transition.

        :param char_type: Type of character that triggers this transition
        :param callback: Action associated with this state (for example, do something with the current character and
        advance to the next characer)
        :param next_state: Next state of the state machine
        :return: None
        '''
        if callback is None:
            callback = lambda: None  # by default, no action
        self.transitions[char_type] = Transition(next_state, callback)


class WordParser:
    def __init__(self, input_string):
        self.input_string = input_string
        self.current_char_idx = 0  # current position of the parser in the input_string
        self.current_state = self.initialize_state_machine()
        self.current_token_buffer = StringIO()  # the content of token currently being constructed

    def initialize_state_machine(self):
        '''
        Initialize the states and state transitions of the state machine.
        :return: initial state
        '''
        init = ParserState(TokenType.SPACE)  # if no input, treat it as a zero-length space
        read_space = ParserState(TokenType.SPACE)
        read_word_first_part = ParserState(TokenType.WORD_FIRST_PART)
        read_vowels = ParserState(TokenType.WORD_FIRST_PART)
        read_word_second_part = ParserState(TokenType.WORD_SECOND_PART)
        end_of_input = ParserState(None)  # no token generated

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

        # Consecutive spaces
        read_space.add_transition(CharacterType.SPACE, self.consume_char, read_space)
        read_space.add_transition(CharacterType.VOWEL, self.finish_token, read_word_first_part)
        read_space.add_transition(CharacterType.CONSONANT, self.finish_token, read_word_first_part)
        read_space.add_transition(CharacterType.EOF, self.finish_token, end_of_input)

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
                raise WordTransformLogicError(f'State machine is stuck at {self.current_state} '
                                              f'char_idx={prev_idx}({self.current_char})')

    @property
    def current_char(self):
        if self.current_char_idx >= len(self.input_string):
            return EOF
        return self.input_string[self.current_char_idx]

    def next_char(self):
        if self.current_char_idx >= len(self.input_string):
            import pdb; pdb.set_trace()
            raise WordTransformLogicError('Internal error - calling next_char when already at end of input')
        self.current_char_idx += 1
        return self.current_char
    '''
    def peek_char(self):
        if self.current_char_idx + 1 >= len(self.input_string):
            return EOF
        return self.input_string[self.current_char_idx + 1]
    '''
    def consume_char(self):
        self.current_token_buffer.write(self.current_char)
        self.next_char()

    def finish_token(self):
        self.current_state.finished_token = Token(self.current_state.token_type,
                                                  self.current_token_buffer.getvalue())
        self.current_token_buffer = StringIO()  # creating new StringIO is faster than truncating


def transform_words(json_string):
    '''
    Transform a JSON string string with the following rules:

    For each pair of words, swap the beginnings of the words, up to and including the first vowel
    (and any consecutive vowels) of the word.

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
    >>> transform_words('"I\'d rather die here."')
    '"ra\'d Ither he diere."'

    Vowels include those in the Finnish alphabet (a, e, i, o, u, y, å, ä, ö),

    >>> transform_words('"vuoirkage mäölnö")
    '"mäörkage vuoilnö"'

    Any character that is not space or a vowel is treated as a consonant.

    :param json_string: quoted string that pertain to JSON formatting
    :return: The returned value is a quoted string that pertain to JSON formatting
    '''

    return json.dumps(''.join(transform_words_generator(json_string)))


def transform_words_generator(json_string):
    '''
    Like transform_words, but a generator that returns the output fragments as it is constructed

    See docs in transform_words.

    :param json_string: str containing json encoded string
    :return: iterator that returns strings
    '''
    if not isinstance(json_string, str):
        # although json.loads allows bytes input, restrict input to str
        raise WordTransformException('Input required as str, got a {} instead'.format(type(json_string)))

    try:
        decoded_input = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise WordTransformException('JSON encoded string required') from e

    if not isinstance(decoded_input, str):
        raise WordTransformException('JSON encoded string required, got a {} instead'.format(type(decoded_input)))

    pending_tokens = []
    for token in WordParser(decoded_input).generate_tokens():
        '''
        Logic:
        * Process tokens generated by the WordParser
        * yield token content as-is until a WORD_FIRST_PART token is encountered
        * After WORD_FIRST_PART is found, start buffering the tokens in pending_tokens.
        * When the matching WORD_FIRST_PART is encountered, swap the WORD_FIRST_PART tokens
          (which are always at the first and last item in buffer)
        * Repeat until end of input. If tokens remains in buffer, flush it at end. 
        '''
        if token.token_type == TokenType.WORD_FIRST_PART:
            pending_tokens.add(token)
            if len(pending_tokens) > 1:
                pending_tokens[0], pending_tokens[-1] = pending_tokens[-1], pending_tokens[0]
            else:
                for tok in pending_tokens:
                    yield tok.string_value
                pending_tokens = []
        elif len(pending_tokens) == 0:
            yield token.string_value
        else:
            pending_tokens.append(token)
        # flush any remaining input, such as any odd word, space or WORD_SECOND_PART.
        for tok in pending_tokens:
            yield tok.string_value

if __name__ == "__main__":
    import doctest
    try:
        doctest.testmod()
    except Exception:
        import pdb; pdb.post_mortem()
        raise

