"""Verify the stereo-delay SDK callback and headless Wwise authoring host.

Run on Windows from an x64 Visual Studio developer prompt after the Wwise build.
This test never opens an audio device or an interactive authoring window.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wwise-root',default=os.environ.get('WWISEROOT'))
    args=parser.parse_args()
    if os.name!='nt':parser.error('This host check requires Windows and MSVC.')
    if not args.wwise_root:parser.error('Set WWISEROOT or pass --wwise-root.')
    sdk=Path(args.wwise_root).resolve()
    out=ROOT/'build/StereoDelay/wwise-review'
    out.mkdir(parents=True,exist_ok=True)
    probe=out/'wwise_probe.exe'
    command=['cl','/nologo','/std:c++17','/O1','/EHsc','/MD','/DAK_OPTIMIZED',
        '/I'+str(ROOT/'build/StereoDelay/generated/wwise/SoundEnginePlugin'),
        '/I'+str(sdk/'SDK/include'),str(ROOT/'tests/wwise_probe.cpp'),
        '/Fe'+str(probe),'/Fo'+str(out/'wwise_probe.obj'),'/link',
        '/LIBPATH:'+str(sdk/'SDK/x64_vc170/Release/lib'),
        'StereoDelayFX.lib','AkSoundEngine.lib','AkMemoryMgr.lib','AkStreamMgr.lib']
    with (out/'sdk-callback.log').open('w') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run([str(probe)],check=True,stdout=log,stderr=subprocess.STDOUT)
    console=sdk/'Authoring/x64/Release/bin/WwiseConsole.exe'
    project=out/'AuthoringReview/AuthoringReview.wproj'
    if not project.exists():
        subprocess.run([str(console),'create-new-project',str(project),'--platform','Windows'],check=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port=listener.getsockname()[1]
    def call(uri,args=None,options=None):
        body=json.dumps({'uri':uri,'args':args or {},'options':options or {}}).encode()
        request=urllib.request.Request(f'http://127.0.0.1:{port}/waapi',data=body,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode()) from None
    with (out/'authoring-server.log').open('w') as log:
        server=subprocess.Popen([str(console),'waapi-server',str(project),
            '--http-port',str(port),'--wamp-port','0','--allowed-addr','127.0.0.1',
            '--watchdog-timeout','120'],stdout=log,stderr=subprocess.STDOUT)
        try:
            for attempt in range(60):
                if server.poll() is not None:raise RuntimeError('WwiseConsole exited; see authoring-server.log.')
                try:info=call('ak.wwise.core.getInfo');break
                except OSError:
                    if attempt==59:raise
                    time.sleep(.5)
            if info['processId']!=server.pid:raise RuntimeError('API server is not the process started by this test.')
            plugins=call('ak.wwise.core.plugin.getList')['return']
            matches=[p for p in plugins if p.get('name')=='StereoDelay']
            if len(matches)!=1:raise RuntimeError('Compiled authoring plugin was not registered.')
            expected={'left_ms':100.0,'right_ms':150.0,'feedback':.5,'wet':1.0}
            call('ak.wwise.core.object.set',{'objects':[{'object':'\\Effects\\Default Work Unit','children':[
                {'type':'Effect','classId':matches[0]['classId'],'name':'PdStereoDelayReview',**{'@'+k:v for k,v in expected.items()}}]}],
                'onNameConflict':'merge'})
            call('ak.wwise.core.project.save')
            tree=ET.parse(project.parent/'Effects/Default Work Unit.wwu')
            effect=tree.find(".//Effect[@Name='PdStereoDelayReview']")
            values={p.attrib['Name']:float(p.attrib['Value']) for p in effect.findall('./PropertyList/Property')}
            if values!=expected:raise RuntimeError('Saved plugin controls differ: '+str(values))
            result={'status':'passed','host':info['version']['displayName'],
                'plugin':matches[0],'saved_parameters':values,'callback_sample_rates':[44100,48000,96000],
                'callback_checks':['delay timing','feedback','reset','instance isolation','partial-buffer tail termination'],
                'limitations':'SDK callback and authoring checks; not full game-engine routing or level travel.'}
            (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2))
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
