"""Create small, deterministic review sounds; no external sample assets needed."""
from pathlib import Path
import math, random, struct, wave

def create(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rate=48000
    rng=random.Random(23417)
    click=[.45*math.exp(-i/(rate*.009))*(.65*math.sin(2*math.pi*1700*i/rate)+.35*rng.uniform(-1,1))*min(1,i/24) for i in range(int(rate*.065))]
    for name,duration,times in [('Click',.1,[.005]),('ClickLoop',4,[.1]),('RoomClickLoop',4,[.005]),('ClickDemo',28,[1,5,9,13,17,21])]:
        data=[0.]*(int(rate*duration))
        for when in times:
            start=int(when*rate)
            data[start:start+len(click)]=click
        with wave.open(str(folder/(name+'.wav')),'wb') as output:
            output.setparams((2,2,rate,0,'NONE','not compressed'))
            output.writeframes(b''.join(struct.pack('<hh',round(x*32767),round(x*32767)) for x in data))
if __name__=='__main__':
    import sys
    create(sys.argv[1])
