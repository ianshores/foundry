# SPDX-License-Identifier: MIT
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
ENGINE = Path(os.environ.get("CONVOY_ROOT", ROOT / "modules/convoy")).resolve()
def require_engine():
    if not (ENGINE / "include/convoy.hpp").is_file():
        raise RuntimeError("Convoy source missing. Run git submodule update --init --recursive or set CONVOY_ROOT.")
    if not (ENGINE / "vendor/dsp/include/dsp/fft.hpp").is_file():
        raise RuntimeError("Shared DSP FFT missing. Run git submodule update --init --recursive in Convoy.")
    return ENGINE
