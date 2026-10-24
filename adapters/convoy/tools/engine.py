# SPDX-License-Identifier: MIT
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
ENGINE = Path(os.environ.get("CONVOY_ROOT", ROOT / "modules/convoy")).resolve()
def require_engine():
    if not (ENGINE / "include/convoy.hpp").is_file():
        raise RuntimeError("Convoy source missing. Run git submodule update --init --recursive or set CONVOY_ROOT.")
    return ENGINE
