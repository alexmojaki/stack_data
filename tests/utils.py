import os

from littleutils import string_to_file, file_to_string


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
