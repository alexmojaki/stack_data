import os

from littleutils import string_to_file, file_to_string, json_to_file, file_to_json


def compare_to_file(text, name):
    filename = os.path.join(
        os.path.dirname(__file__),
        'golden_files',
        name + '.txt',
    )
    if os.environ.get('FIX_STACK_DATA_TESTS'):
        string_to_file(text, filename)
    else:
        expected_output = file_to_string(filename)
        assert text == expected_output


def compare_to_file_json(data, name):
    filename = os.path.join(
        os.path.dirname(__file__),
        'golden_files',
        name + '.json',
    )
    if os.environ.get('FIX_STACK_DATA_TESTS'):
        json_to_file(data, filename, indent=4)
    else:
        expected_output = file_to_json(filename)
        assert data == expected_output
