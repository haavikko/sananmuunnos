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
            #('', ''),
            #('', ''),
            #('', ''),
        ]
        self._run_transforms(inputs_and_outputs)

    def test_lots_of_words(self):
        self.assertEqual(json.dumps('bama foorbu ' * 1000), # with a trailing space
                         transform.transform_words(json.dumps('fooma barbu '*1000)))

    def test_long_single_word(self):
        long_word = json.dumps('abcde' * 10000)
        self.assertEqual(long_word, transform.transform_words(long_word))

    def test_long_prefix(self):
        long_prefix_1 = 'a'*10000 + 'b'
        long_prefix_2 = 'b' * 10000 + 'a'

    def test_long_suffix(self):
        long_suffix_1 = 'a' + 'b' * 10000
        long_suffix_2 = 'ba' * 10000 + 'b'

        inputs_and_outputs = [
            ('"fooma barbu hello"', '"bama foorbu hello"'),
            (' ', ' '),
            ('', ''),
            ('', ''),
            ('', ''),
        ]
        self._run_transforms(inputs_and_outputs)

    def test_strange_inputs(self):
        inputs_and_outputs = [
            ('" "', '" "'),
            ('"          "', '"          "'),
            (json.dumps('\n'), json.dumps('\n')),
            (json.dumps('\t'), json.dumps('\t')),
            ('', ''),
            ('', ''),
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


class TransformHttpTest(TestCase):
    def test_get(self):
        response = self.client.get('/word_transform/')
        self.assertEqual(response.status_code, 405)

    def test_empty_post(self):
        response = self.client.post('/word_transform/', content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_invalid_post(self):
        response = self.client.post('/word_transform/', 'foo', content_type="application/json")
        self.assertEqual(response.status_code, 500)

        response = self.client.post('/word_transform/', 'foo', content_type="application/json")
        self.assertEqual(response.status_code, 500)

    def test_invalid_post(self):
        response = self.client.post('/word_transform/', 'foo', content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_empty_post(self):
        response = self.client.post('/word_transform/', content_type="application/json")
        self.assertEqual(response.status_code, 200)
