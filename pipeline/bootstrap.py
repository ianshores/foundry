"""Install a project-local compiler and a pinned DPF checkout. No system changes."""
import json
from pathlib import Path
import subprocess
import sys
import venv
ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT/'pipeline/toolchain.json').read_text())
def run(*args):
    subprocess.run(list(map(str, args)), check=True, cwd=ROOT)
def main():
    target = ROOT/'.toolchain/venv'
    if not target.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    python = target/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    run(python, '-m', 'pip', 'install', '--no-cache-dir', '--disable-pip-version-check', '-r', ROOT/'pipeline/requirements.lock')
    dpf = ROOT/'.toolchain/dpf'
    fresh = not dpf.exists()
    # Publish the checkout only when it is complete. A failed first run must not
    # look like a user-modified checkout on the next run.
    checkout = ROOT/'.toolchain/dpf.pending' if fresh else dpf
    if fresh and not checkout.exists():
        run('git', 'clone', '--no-checkout', PIN['dpf_repository'], checkout)
    # Refuse to reset an unexpected or locally modified checkout.
    origin = subprocess.check_output(['git','-C',str(checkout),'remote','get-url','origin'],text=True).strip()
    if origin != PIN['dpf_repository']:
        raise SystemExit('Unexpected DPF origin; move .toolchain/dpf aside before bootstrapping.')
    if not fresh and subprocess.check_output(['git','-C',str(dpf),'status','--porcelain'],text=True).strip():
        raise SystemExit('DPF has local changes; preserve them before bootstrapping.')
    run('git', '-C', checkout, 'fetch', 'origin', PIN['dpf_commit'])
    run('git', '-C', checkout, 'checkout', '--detach', PIN['dpf_commit'])
    run('git', '-C', checkout, 'submodule', 'update', '--init', '--recursive')
    if fresh:
        checkout.rename(dpf)
    print('Ready. Run: python3 pipeline/pdplugins.py doctor')
if __name__ == '__main__':
    main()
