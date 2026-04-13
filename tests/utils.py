import os
import re
from html import unescape

import pygments
from littleutils import string_to_file, file_to_string, json_to_file, file_to_json


def parse_version(version: str):
    return tuple(int(x) for x in version.split("."))


old_pygments = parse_version(pygments.__version__) < (2, 19, 0)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
PYGMENTS_SPAN_RE = re.compile(r"</?span\b[^>]*>")


def normalize_pygmented_text(text: str) -> str:
    text = ANSI_ESCAPE_RE.sub("", text)
    if "<span" in text:
        text = PYGMENTS_SPAN_RE.sub("", text)
        text = unescape(text)
    return text


def normalize_pygmented_data(data):
    if isinstance(data, str):
        return normalize_pygmented_text(data)
    if isinstance(data, list):
        return [normalize_pygmented_data(item) for item in data]
    if isinstance(data, dict):
        return {key: normalize_pygmented_data(value) for key, value in data.items()}
    return data


def compare_to_file(text, name):
    if old_pygments and "pygment" in name:
        return
    filename = os.path.join(
        os.path.dirname(__file__),
        'golden_files',
        name + '.txt',
    )
    if os.environ.get('FIX_STACK_DATA_TESTS'):
        string_to_file(text, filename)
    else:
        expected_output = file_to_string(filename)
        if "pygment" in name:
            text = normalize_pygmented_text(text)
            expected_output = normalize_pygmented_text(expected_output)
        assert text == expected_output


def compare_to_file_json(data, name, *, pygmented):
    if old_pygments and pygmented:
        return
    filename = os.path.join(
        os.path.dirname(__file__),
        'golden_files',
        name + '.json',
    )
    if os.environ.get('FIX_STACK_DATA_TESTS'):
        json_to_file(data, filename, indent=4)
    else:
        expected_output = file_to_json(filename)
        if pygmented:
            data = normalize_pygmented_data(data)
            expected_output = normalize_pygmented_data(expected_output)
        assert data == expected_output
