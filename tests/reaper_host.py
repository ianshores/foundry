"""Review the delay in a portable REAPER instance on a private virtual display.
Never connects to the user's desktop or uses their REAPER preferences.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import wave
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reaper',required=True,type=Path)
    parser.add_argument('--xvfb',required=True,type=Path)
    args=parser.parse_args()
    for exe in (args.reaper,args.xvfb):
        if not exe.is_file():parser.error('Executable not found: '+str(exe))
    out=ROOT/'build/StereoDelay/reaper-review';out.mkdir(parents=True,exist_ok=True)
    profile=out/'profile';profile.mkdir(exist_ok=True)
    plugins=ROOT/'build/StereoDelay/generated/bin'
    (profile/'reaper.ini').write_text('[REAPER]\nvstpath='+str(plugins)+'\nvstpath64='+str(plugins)+'\naudiomode=0\n')
    with wave.open(str(out/'impulse.wav'),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000)
        data=bytearray(48000*4);struct.pack_into('<hh',data,4800*4,16384,16384);w.writeframes(data)
    for kind in ('CLAP','VST3'):(out/f'reaper-{kind}.wav').unlink(missing_ok=True)
    env=os.environ.copy();env.pop('WAYLAND_DISPLAY',None)
    env.update({'LIBGL_ALWAYS_SOFTWARE':'1','__EGL_VENDOR_LIBRARY_FILENAMES':'/usr/share/glvnd/egl_vendor.d/50_mesa.json','GDK_BACKEND':'x11','CLAP_PATH':str(plugins),'PD_REVIEW_ROOT':str(out)})
    server=None
    with (out/'virtual-display.log').open('w') as xlog:
        try:
            for number in range(97,127):
                if Path(f'/tmp/.X{number}-lock').exists():continue
                server=subprocess.Popen([str(args.xvfb.resolve()),f':{number}','-screen','0','1280x900x24','-nolisten','tcp','-ac','-extension','GLX'],env=env,stdout=xlog,stderr=subprocess.STDOUT)
                time.sleep(.4)
                if server.poll() is None:
                    env['DISPLAY']=f':{number}';break
            else:raise RuntimeError('Could not create a private virtual display. Desktop fallback is disabled.')
            with (out/'reaper.log').open('w') as log:
                subprocess.run([str(args.reaper.resolve()),'-newinst','-nosplash','-cfgfile',str(profile/'reaper.ini'),'-ignoreerrors',str(ROOT/'tests/reaper_render.lua')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=75)
        finally:
            if server and server.poll() is None:
                server.terminate();server.wait(timeout=5)
    results=[]
    for kind in ('CLAP','VST3'):
        p=out/f'reaper-{kind}.wav'
        with wave.open(str(p),'rb') as w:
            channels=w.getnchannels();rate=w.getframerate();width=w.getsampwidth();frames=w.getnframes();raw=w.readframes(frames)
        def value(frame,c):
            at=(frame*channels+c)*width
            return int.from_bytes(raw[at:at+width],'little',signed=True)/(2**(width*8-1))
        def peak(t,c):return max(abs(value(i,c)) for i in range(round(rate*t)-5,round(rate*t)+6))
        row={'format':kind,'rate':rate,'channels':channels,'seconds':frames/rate,'dry':peak(.1,0),'left_echo':peak(.2,0),'right_echo':peak(.25,1),'feedback_echo':peak(.3,0)}
        assert channels==2 and rate==48000 and frames>=96000,row
        assert row['dry']<.001 and abs(row['left_echo']-.5)<.005 and abs(row['right_echo']-.5)<.005 and abs(row['feedback_echo']-.25)<.005,row
        results.append(row);print(json.dumps(row))
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print('Both plugin formats rendered the expected delay in REAPER, without desktop windows.')
if __name__=='__main__':main()
