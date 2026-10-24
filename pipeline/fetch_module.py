#!/usr/bin/env python3
"""Fetch a pinned optional DSP module with the caller's existing Git access."""
import argparse
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def main():
    modules=json.loads((ROOT/'pipeline/optional-modules.json').read_text())
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module',choices=modules)
    args=parser.parse_args();spec=modules[args.module];dest=ROOT/spec['path']
    if dest.exists():
        if subprocess.check_output(['git','-C',str(dest),'status','--porcelain'],text=True).strip():
            parser.error('Module checkout has local changes; preserve them before updating.')
        origin=subprocess.check_output(['git','-C',str(dest),'remote','get-url','origin'],text=True).strip()
        if origin!=spec['repository']:parser.error('Unexpected module origin; refusing to change it.')
    else:
        dest.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','--no-checkout',spec['repository'],str(dest)],check=True)
    subprocess.run(['git','-C',str(dest),'fetch','origin',spec['commit']],check=True)
    subprocess.run(['git','-C',str(dest),'checkout','--detach',spec['commit']],check=True)
    print('Ready:',args.module,spec['commit'])
if __name__=='__main__':main()
