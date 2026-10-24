"""Load the packaged stereo delay and build review assets in a private UE project."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ue-root',default=os.environ.get('UE_ROOT'))
    args=parser.parse_args()
    if os.name!='nt':parser.error('This review host currently targets Windows.')
    if not args.ue_root:parser.error('Set UE_ROOT or pass --ue-root.')
    engine=Path(args.ue_root).resolve()
    editor=engine/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
    build=ROOT/'build/StereoDelay'
    package=build/'packages/PdStereoDelay'
    if not (package/'PdStereoDelay.uplugin').is_file():parser.error('Build the Unreal target first.')
    # Each run owns a fresh project, preserving previous review edits and sessions.
    root=Path(tempfile.mkdtemp(prefix='unreal-review-',dir=build))/'DelayReview'
    root.mkdir()
    shutil.copytree(package,root/'Plugins/PdStereoDelay',ignore=shutil.ignore_patterns('HostProject','Intermediate'))
    project=root/'DelayReview.uproject'
    project.write_text(json.dumps({'FileVersion':3,'Category':'Audio',
        'Description':'PD stereo delay review',
        'Plugins':[{'Name':p,'Enabled':True} for p in ['PdStereoDelay','Metasound','PythonScriptPlugin','EditorScriptingUtilities']]},indent=2)+'\n')
    command=[str(editor),str(project),'-run=pythonscript','-script='+str(ROOT/'tests/unreal_editor_check.py'),
        '-unattended','-nop4','-nosplash','-NullRHI','-nosound','-NoShaderCompile','-stdout','-FullStdOutLogOutput']
    log_path=root/'headless-check.log'
    with log_path.open('w') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    result=json.loads((root/'review-result.json').read_text())
    if result.get('status')!='passed':raise RuntimeError('Unreal graph/preset verification did not pass.')
    result.update({'project':str(project),'log':str(log_path)})
    output=build/'unreal-review-result.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
