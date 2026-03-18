import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    base_dir = Path(getattr(sys, "_MEIPASS"))
    os.environ["TCL_LIBRARY"] = str(base_dir / "_tcl_data")
    os.environ["TK_LIBRARY"] = str(base_dir / "_tk_data")
