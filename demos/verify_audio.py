"""Check real host recordings, including echoes after actual streamed-level unload."""
import argparse,json,re,struct,wave,array,sys,math
from pathlib import Path

def read(path):
    with wave.open(str(path),'rb') as w:
        assert w.getnchannels()==2 and w.getsampwidth()==2
        rate=w.getframerate();raw=w.readframes(w.getnframes())
    values=array.array('h');values.frombytes(raw)
    if sys.byteorder!='little':values.byteswap()
    return rate,values

def peak(data,rate,channel,start,end):
    return max((abs(v)/32768 for v in data[max(0,int(start*rate))*2+channel:min(len(data),int(end*rate)*2):2]),default=0)

def transients(data,rate,channel,threshold=.006):
    result=[];last=-10
    for i in range(0,len(data)//2,240):
        t=i/rate
        p=peak(data,rate,channel,t,t+.005)
        if p>threshold and t-last>.08:result.append((t,p));last=t
    return result

def verify_wwise(path):
    rate,data=read(path);events=[transients(data,rate,c) for c in range(2)]
    for c,delay in enumerate([.7,1.05]):
        initial=events[c][0][0]
        levels=[peak(data,rate,c,initial+n*delay-.015,initial+n*delay+.08) for n in range(1,4)]
        assert min(levels)>.03,('missing Wwise echo',c,levels)
        assert abs(levels[1]/levels[0]-.65)<.04,('feedback mismatch',c,levels)
    return {'status':'passed','capture':str(path),'sample_rate':rate,'checks':['Wwise authoring transport through actual auxiliary return','700ms left / 1050ms right','feedback amplitude ratio 0.65'],'transients':events}

def dominant_frequency(data,rate,start,end):
    lo=max(0,int(start*rate));hi=min(len(data)//2,int(end*rate))
    at=max(range(lo,hi),key=lambda i:abs(data[2*i]))
    at=max(0,at-int(.002*rate))
    samples=data[2*at:2*(at+2048):2]
    powers=[]
    for frequency in range(400,4001,25):
        coefficient=2*math.cos(2*math.pi*frequency/rate)
        s1=s2=0.
        for sample in samples:
            current=sample+coefficient*s1-s2;s2=s1;s1=current
        powers.append((s1*s1+s2*s2-coefficient*s1*s2,frequency))
    return max(powers)[1]

def verify_unreal(path,timeline):
    rate,data=read(path);text=Path(timeline).read_text(encoding='utf-8-sig')
    start=float(re.search(r'([\d.]+) RECORD_RETURN_STARTED',text)[1])
    clicks=[float(x) for x in re.findall(r'([\d.]+) CLICK source-owned-by-',text)]
    unloads=[float(x) for x in re.findall(r'([\d.]+) LEVEL_UNLOADED .*emitter_destroyed=1',text)]
    next_levels=[float(x) for x in re.findall(r'([\d.]+) NEXT_LEVEL_VISIBLE',text)]
    assert clicks and unloads and next_levels,'Missing real streaming/source lifetime evidence'
    if 'PLACED_ROOM_SOURCE' in text:
        assert 'owner_level=Room_A controller_level=PersistentDemo' in text
        assert set(re.findall(r'CLICK source-owned-by-(Room_[AB])',text))=={'Room_A','Room_B'}
        assert 'pitch=0.500' in text and 'pitch=2.000' in text
        assert 'LOOPING_SOURCE_UNLOADED_WHILE_PLAYING' in text
    assert next_levels[0]>unloads[0]>clicks[0]
    assert len(set(re.findall(r'return=([0-9A-Fa-f]+)',text)))==1,'Return object changed across transitions'
    events=[transients(data,rate,c) for c in range(2)]
    assert all(events),'Silent return recording'
    for c,delay in enumerate([.7,1.05]):
        first=events[c][0][0]
        # Play() is a game-thread request; pitched source decoding adds startup buffering.
        # Check the exact repeat spacing below and require all echoes after source destruction.
        startup_bound=.35 if 'PLACED_ROOM_SOURCE' in text else .20
        assert abs(first-(clicks[0]-start+delay))<startup_bound,('first echo timing',c,first,clicks[0],start)
        assert first+start>unloads[0],'First echo should occur after source level destruction'
        echoes=[peak(data,rate,c,first+n*delay-.025,first+n*delay+.08) for n in range(4)]
        assert min(echoes)>.025,('Tail truncated at unload',c,echoes)
        assert abs(echoes[1]/echoes[0]-.72)<.07,('Feedback changed across streaming',c,echoes)
    pitch_check={}
    if 'PLACED_ROOM_SOURCE' in text:
        frequencies=[dominant_frequency(data,rate,t-start+.7-.04,t-start+.7+.30) for t in clicks[:2]]
        assert 3.4<frequencies[1]/frequencies[0]<4.6,('Room pitches are not two octaves apart',frequencies)
        pitch_check={'room_a_hz':frequencies[0],'room_b_hz':frequencies[1],'octaves':math.log2(frequencies[1]/frequencies[0])}
    return {'status':'passed','capture':str(path),'sample_rate':rate,'room_pitch_check':pitch_check,'checks':['actual Room_A / Room_B streaming','emitter destroyed before first echo','same GameInstance-held return across transitions','wet-only return echoes continue after unload and next room loads','700ms left / 1050ms right / feedback 0.72'],'click_times':clicks,'unload_times':unloads,'next_level_visible_times':next_levels,'transients':events}
def verify_meta(path):
    rate,data=read(path);events=[transients(data,rate,c) for c in range(2)]
    for c,delay in enumerate([.7,1.05]):
        assert abs(events[c][0][0]-.1)<.03,'Missing initial MetaSound click'
        for n in range(1,4):
            assert peak(data,rate,c,.1+n*delay-.015,.1+n*delay+.065)>.03,('Missing MetaSound echo',c,n)
        assert peak(data,rate,c,4.09,4.17)>.05,'Click loop did not repeat'
    return {'status':'passed','capture':str(path),'sample_rate':rate,'checks':['actual MetaSound Wave Player through compiled PD node','700ms left / 1050ms right','clicks repeat every four seconds'],'transients':events}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wwise');p.add_argument('--unreal');p.add_argument('--timeline');p.add_argument('--meta');p.add_argument('--out',required=True);a=p.parse_args()
    result={}
    if a.wwise:result['wwise']=verify_wwise(a.wwise)
    if a.unreal:result['unreal']=verify_unreal(a.unreal,a.timeline)
    if a.meta:result['metasound']=verify_meta(a.meta)
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:{x:y for x,y in v.items() if x!='transients'} for k,v in result.items()},indent=2))
