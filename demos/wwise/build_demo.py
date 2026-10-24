"""Create an audible standalone Wwise project using the installed authoring plugin."""
import argparse,json,subprocess,time,urllib.request,urllib.error,socket,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from make_clicks import create
p=argparse.ArgumentParser();p.add_argument('--sdk',required=True);p.add_argument('--out',required=True);p.add_argument('--inspect',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args()
root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
create(root/'Samples')
project=root/'WwiseClickDemo/WwiseClickDemo.wproj'
console=Path(a.sdk)/'Authoring/x64/Release/bin/WwiseConsole.exe'
if not project.exists():subprocess.run([str(console),'create-new-project',str(project),'--platform','Windows'],check=True)
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
def call(uri,args=None,options=None):
    request=urllib.request.Request(f'http://127.0.0.1:{port}/waapi',json.dumps({'uri':uri,'args':args or {},'options':options or {}}).encode(),{'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
    except urllib.error.HTTPError as e:raise RuntimeError(uri+': '+e.read().decode()) from None
with (root/'wwise-demo-build.log').open('w') as log:
    server=subprocess.Popen([str(console),'waapi-server',str(project),'--http-port',str(port),'--wamp-port','0','--allowed-addr','127.0.0.1','--watchdog-timeout','180'],stdout=log,stderr=subprocess.STDOUT)
    try:
        for attempt in range(100):
            try:info=call('ak.wwise.core.getInfo');break
            except OSError:time.sleep(.3)
        assert info['processId']==server.pid
        if a.inspect:
            result={}
            for uri in ['ak.wwise.core.object.set','ak.wwise.core.audio.import','ak.wwise.core.object.getPropertyNames','ak.wwise.core.object.setReference']:
                result[uri]=call('ak.wwise.waapi.getSchema',{'uri':uri})
            result['busses']=call('ak.wwise.core.object.get',{'waql':'$ from type Bus'},{'return':['id','name','path']})
            result['import']=call('ak.wwise.core.audio.import',{'importOperation':'useExisting','imports':[{'audioFile':str(root/'Samples/ClickDemo.wav'),'objectPath':r'\Containers\Default Work Unit\<Sound>01_Clicks_PD_Send','event':r'\Events\Default Work Unit\Play_Click_Delay_Demo'}]})
            result['soundProps']=call('ak.wwise.core.object.getPropertyNames',{'object':r'\Containers\Default Work Unit\01_Clicks_PD_Send'})
            result['busProps']=call('ak.wwise.core.object.getPropertyNames',{'object':r'\Busses\Default Work Unit\Main Audio Bus'})
            call('ak.wwise.core.project.save')
            result['plugins']=call('ak.wwise.core.plugin.getList')
            (root/'waapi-schema.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result['busses']))
        else:
            plugins=call('ak.wwise.core.plugin.getList')['return']
            plugin=next(x for x in plugins if x.get('name')=='StereoDelay')
            effect=r'\Effects\Default Work Unit\PD_ClickDelay_700_1050'
            bus=r'\Busses\Default Work Unit\Main Audio Bus\PD_Delay_Return'
            sound=r'\Containers\Default Work Unit\01_Clicks_PD_Send'
            dry=r'\Containers\Default Work Unit\02_Dry_Clicks_Reference'
            call('ak.wwise.core.object.set',{'objects':[{'object':r'\Effects\Default Work Unit','children':[{
                'name':'PD_ClickDelay_700_1050','type':'Effect','classId':plugin['classId'],
                '@left_ms':700.0,'@right_ms':1050.0,'@feedback':.65,'@wet':1.0,
                'notes':'100% wet shared return. Adjust the four controls and audition 01_Clicks_PD_Send.'}]}],'onNameConflict':'merge'})
            call('ak.wwise.core.object.set',{'objects':[{'object':r'\Busses\Default Work Unit\Main Audio Bus','children':[{
                'type':'AuxBus','name':'PD_Delay_Return','@BusChannelConfig':12546,
                '@Effects':[{'type':'EffectSlot','name':'','@Effect':effect}],
                'notes':'Stereo auxiliary return. PD effect is wet-only; the sound also goes directly to Main Audio Bus.'}]}],'onNameConflict':'merge','listMode':'replaceAll'})
            imported=call('ak.wwise.core.audio.import',{'importOperation':'useExisting','imports':[
                {'audioFile':str(root/'Samples/ClickDemo.wav'),'objectPath':r'\Containers\Default Work Unit\<Sound>01_Clicks_PD_Send',
                'event':r'\Events\Default Work Unit\Play_Click_Delay_Demo'},
                {'audioFile':str(root/'Samples/ClickDemo.wav'),'objectPath':r'\Containers\Default Work Unit\<Sound>02_Dry_Clicks_Reference',
                'event':r'\Events\Default Work Unit\Play_Dry_Reference'}]})
            if any(x['severity'] in ['Error','Fatal Error'] for x in imported['log']):raise RuntimeError(str(imported['log']))
            call('ak.wwise.core.object.set',{'objects':[{'object':sound,'@OverrideUserAuxSends':True,'@UserAuxSend0':bus,'@UserAuxSendVolume0':0.0,
                'notes':'AUDITION THIS SOUND (space). A click every 4 seconds. Dry click + echoes at 700 ms left / 1050 ms right. Compare 02_Dry_Clicks_Reference.'}]})
            call('ak.wwise.core.project.save')
            result=call('ak.wwise.core.object.get',{'from':{'path':[sound,bus,effect]}},{'return':['id','name','type','path','notes']})
            (root/'wwise-demo-result.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result,indent=2))
            if a.verify:
                record=r'\Effects\Default Work Unit\TemporaryCapture'
                capture=str(root/'WwiseClickDelayCapture.wav')
                call('ak.wwise.core.object.set',{'objects':[{'object':r'\Effects\Default Work Unit','children':[{'type':'Effect','name':'TemporaryCapture','classId':8650755,'@AuthoringFilename':capture,'@DownmixToStereo':True}]}],'onNameConflict':'merge'})
                master=r'\Busses\Default Work Unit\Main Audio Bus'
                call('ak.wwise.core.object.set',{'objects':[{'object':master,'@Effects':[{'type':'EffectSlot','name':'','@Effect':record}]}],'listMode':'replaceAll'})
                try:
                    transport=call('ak.wwise.core.transport.create',{'object':sound})['transport']
                    call('ak.wwise.core.transport.executeAction',{'transport':transport,'action':'play'})
                    time.sleep(10)
                    call('ak.wwise.core.transport.executeAction',{'transport':transport,'action':'stop'})
                    time.sleep(2)
                    print('Host playback captured: '+capture)
                finally:
                    call('ak.wwise.core.object.set',{'objects':[{'object':master,'@Effects':[]}],'listMode':'replaceAll'})
                    call('ak.wwise.core.object.delete',{'object':record})
                    call('ak.wwise.core.project.save')

    finally:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.wait()
