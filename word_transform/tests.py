import json

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, Client

from . import transform

class WordTransformTest(TestCase):

    def test_basic_transform(self):
        inputs_and_outputs = [
            ('"fooma barbu"', '"bama foorbu"'),
            ('"hello"', '"hello"'),
            ('"fooma barbu hello"', '"bama foorbu hello"'),
            ('"amama   bomomo foo"', '"bomama   amomo foo"'),
            ('"I\'d rather die here."', '"ra\'d Ither he diere."'),
            ('"vuoirkage mäölnö"', '"mäörkage vuoilnö"'),
            ('"a"', '"a"'),
            ('"a a"', '"a a"'),
            ('"b"', '"b"'),
            ('"b b"', '"b b"'),
            ('"a b"', '"b a"'),
            ('"aa bb"', '"bb aa"'),
            ('" aa bb"', '" bb aa"'),
            ('"  aa bb"', '"  bb aa"'),
            ('"  aa bb  "', '"  bb aa  "'),
            ('"aa bb cc"', '"bb aa cc"'),
            ('"  aa bb  cc  "', '"  bb aa  cc  "'),
        ]
        self._run_transforms(inputs_and_outputs)

    def test_lots_of_words(self):
        self.assertEqual(json.dumps('bama foorbu ' * 1000), # with a trailing space
                         transform.transform_words(json.dumps('fooma barbu '*1000)))

        self.assertEqual(json.dumps('bama foorbu ' * 1000 + ' abcdef'), # with a lone word at end
                         transform.transform_words(json.dumps('fooma barbu '* 1000 + ' abcdef')))

    def test_long_single_word(self):
        long_word = json.dumps('abcde' * 10000)
        self.assertEqual(long_word, transform.transform_words(long_word))

    def test_long_word_prefix(self):
        length = 10000
        long_prefix_1 = 'b' * length + 'ab'  # prefix is bbbbbb....a
        long_prefix_2 = 'a' * length + 'ba'  # prefix is aaaaaa....a

        trans_1 = 'a' * length + 'b'
        trans_2 = 'b' * length + 'aba'

        self.assertEqual(json.dumps(long_prefix_1 + ' ' + long_prefix_2),
                         transform.transform_words(json.dumps(trans_1 + ' ' + trans_2)))

    def test_long_word_suffix(self):
        length = 10000
        long_suffix_1 = 'A' + 'b' * length   # prefix is A
        long_suffix_2 = 'Yb' + 'a' * length  # prefix is Y
        trans_1 = 'Y' + 'b' * length
        trans_2 = 'Ab' + 'a' * length

        self.assertEqual(json.dumps(long_suffix_1 + ' ' + long_suffix_2),
                         transform.transform_words(json.dumps(trans_1 + ' ' + trans_2)))

    def test_strange_inputs(self):
        inputs_and_outputs = [
            ('" "', '" "'),
            ('"          "', '"          "'),
            (json.dumps('\n'), json.dumps('\n')),
            (json.dumps('\t'), json.dumps('\t')),
            (json.dumps('fooma bar\nbu hello'), json.dumps('bama foor\nbu hello')),
        ]
        self._run_transforms(inputs_and_outputs)

    def test_error_inputs(self):
        invalid_inputs = [
            '{}',                       # valid JSON, but not a JSON string
            '["aaa"]',                  # valid JSON, but not a JSON string
            '',                         # invalid JSON
            '"sdfwe wer',               # invalid JSON
            'abcde' * 10000,            # long invalid JSON
            '"aa"'.encode('utf-8'),     # bytes
            b'\x00\x01',                # bytes
            43,                         # wrong type
            None,                       # wrong type
            ['foo'],                    # wrong type
        ]
        for invalid_input in invalid_inputs:
            self.assertRaises(Exception, transform.transform_words, invalid_input)

    def _run_transforms(self, inputs_and_outputs):
        for json_string, expected_output in inputs_and_outputs:
            self.assertEqual(expected_output, transform.transform_words(json_string))


class WordTransformHttpTest(TestCase):

    def test_invalid_method(self):
        response = self.client.get('/word_transform/')
        self.assertEqual(response.status_code, 405)

    def test_empty_post(self):
        response = self.client.post('/word_transform/', content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_post(self):
        response = self.client.post('/word_transform/', 'foo', content_type="application/json")
        self.assertEqual(response.status_code, 400)

        response = self.client.post('/word_transform/', b'\x00', content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_valid_post(self):
        response = self.client.post('/word_transform/', b'"fooma barbu"', content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/json')
        self.assertEqual(response.content, b'"bama foorbu"')

    def test_non_ascii(self):
        response = self.client.post('/word_transform/',
                                    '"vuoirkage mäölnö"'.encode('utf-8'),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '"mäörkage vuoilnö"'.encode('utf-8'))

