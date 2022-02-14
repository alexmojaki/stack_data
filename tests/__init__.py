import os

import pyximport
from typeguard.importhook import install_import_hook

pyximport.install()

if not os.environ.get("STACK_DATA_SLOW_TESTS"):
    install_import_hook(["stack_data"])
