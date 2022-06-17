import os

import pyximport
from typeguard.importhook import install_import_hook

pyximport.install(language_level=3)

if not os.environ.get("STACK_DATA_SLOW_TESTS"):
    install_import_hook(["stack_data"])
