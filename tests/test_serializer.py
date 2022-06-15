import os.path
import re

from stack_data import FrameInfo
from stack_data.serializing import Serializer
from tests.utils import compare_to_file_json


class MyFormatter(Serializer):
    def should_include_frame(self, frame_info: FrameInfo) -> bool:
        return frame_info.filename.endswith(("formatter_example.py", "<string>", "cython_example.pyx"))

    def format_variable_value(self, value) -> str:
        result = super().format_variable_value(value)
        result = re.sub(r'0x\w+', '0xABC', result)
        return result

    def format_frame(self, frame) -> dict:
        result = super().format_frame(frame)
        result["filename"] = os.path.basename(result["filename"])
        return result


def test_example():
    from .samples.formatter_example import bar, format_frame, format_stack1

    result = dict(
        format_frame=(format_frame(MyFormatter())),
        format_stack=format_stack1(MyFormatter(show_variables=True)),
    )

    try:
        bar()
    except Exception:
        result.update(
            plain=MyFormatter(show_variables=True).format_exception(),
            pygmented=MyFormatter(show_variables=True, pygmented=True).format_exception(),
            pygmented_html=MyFormatter(show_variables=True, pygmented=True, html=True).format_exception(),
        )


    compare_to_file_json(result, "serialize")
