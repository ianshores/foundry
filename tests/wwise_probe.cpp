// Exercise the real generated Wwise callback against the matching SDK.
// No audio device, game project, or interactive authoring session is required.
#include "StereoDelayFX.h"
#include "StereoDelayFXParams.h"
#include <AK/SoundEngine/Common/IAkPluginMemAlloc.h>
#include <AK/SoundEngine/Common/AkSoundEngine.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <malloc.h>
#include <vector>

AK::IAkPlugin* CreateStereoDelayFX(AK::IAkPluginMemAlloc*);
AK::IAkPluginParam* CreateStereoDelayFXParams(AK::IAkPluginMemAlloc*);

struct Allocator final : AK::IAkPluginMemAlloc {
    void* Malloc(size_t n,const char*,AkUInt32) override {return _aligned_malloc(n,16);}
    void Free(void* p) override {_aligned_free(p);}
    void* Malign(size_t n,size_t a,const char*,AkUInt32) override {return _aligned_malloc(n,a);}
    void* Realloc(void* p,size_t n,const char*,AkUInt32) override {return _aligned_realloc(p,n,16);}
    void* ReallocAligned(void* p,size_t n,size_t a,const char*,AkUInt32) override {return _aligned_realloc(p,n,a);}
};
static void check(bool value,const char* message) {
    if(!value) {std::fprintf(stderr,"FAIL: %s\n",message);std::exit(1);}
}
struct Effect {
    Allocator allocator;
    StereoDelayFX* effect;
    StereoDelayFXParams* params;
    static constexpr int block=128;
    float storage[block*2]{};
    AkChannelConfig channels;
    AkAudioBuffer buffer;
    explicit Effect(unsigned rate) {
        channels.SetStandard(AK_SPEAKER_SETUP_STEREO);
        effect=static_cast<StereoDelayFX*>(CreateStereoDelayFX(&allocator));
        params=static_cast<StereoDelayFXParams*>(CreateStereoDelayFXParams(&allocator));
        check(params->Init(&allocator,nullptr,0)==AK_Success,"parameter initialization");
        AkAudioFormat format;
        format.SetAll(rate,channels,32,8,AK_FLOAT,AK_NONINTERLEAVED);
        check(effect->Init(&allocator,nullptr,params,format)==AK_Success,"stereo effect initialization");
        for(auto pair:std::vector<std::pair<int,float>>{{0,.5f},{1,100.f},{2,150.f},{3,1.f}})
            check(params->SetParam(pair.first,&pair.second,sizeof(float))==AK_Success,"parameter update");
        buffer.AttachContiguousDeinterleavedData(storage,block,block,channels);
    }
    ~Effect() {effect->Term(&allocator);params->Term(&allocator);}
    void step(int valid=block,bool ended=false,bool impulse=false) {
        std::fill(std::begin(storage),std::end(storage),0.f);
        if(impulse)storage[0]=storage[block]=.5f;
        buffer.uValidFrames=static_cast<AkUInt16>(valid);
        buffer.eState=ended?AK_NoMoreData:AK_DataReady;
        effect->Execute(&buffer);
    }
};
static float peak(const std::vector<float>& a,unsigned rate,float seconds) {
    const int frame=static_cast<int>(rate*seconds);
    float value=0;
    for(int i=frame-4;i<=frame+4;++i)value=(std::max)(value,std::abs(a.at(i)));
    return value;
}
int main() {
    for(unsigned rate:{44100u,48000u,96000u}) {
        Effect fx(rate),silent(rate);
        for(unsigned n=0;n<rate/10;n+=Effect::block) {fx.step();silent.step();}
        std::vector<float> left,right;
        for(unsigned n=0;n<rate/2;n+=Effect::block) {
            fx.step(Effect::block,false,n==0);
            silent.step();
            for(float value:silent.storage)check(value==0.f,"instance isolation");
            left.insert(left.end(),fx.storage,fx.storage+Effect::block);
            right.insert(right.end(),fx.storage+Effect::block,fx.storage+2*Effect::block);
        }
        check(std::abs(peak(left,rate,.1f)-.5f)<.001f,"left delay timing/gain");
        check(std::abs(peak(right,rate,.15f)-.5f)<.001f,"right delay timing/gain");
        check(std::abs(peak(left,rate,.2f)-.25f)<.001f,"feedback gain");
        check(fx.effect->Reset()==AK_Success,"effect reset");
        for(unsigned n=0;n<rate/3;n+=Effect::block) {
            fx.step();
            for(float value:fx.storage)check(std::abs(value)<1e-7f,"reset clears delay memory");
        }
        fx.step(17,true,true);
        check(fx.buffer.eState==AK_DataReady,"tail remains active after input ends");
        unsigned tailFrames=fx.buffer.uValidFrames;
        unsigned calls=0;
        while(fx.buffer.eState!=AK_NoMoreData) {
            fx.step(0,true);
            tailFrames+=fx.buffer.uValidFrames;
            check(++calls<rate*141u/Effect::block+2,"tail terminates within limit");
        }
        check(tailFrames==17u+rate*140u,"tail preserves partial-buffer duration");
        std::printf("Wwise SDK callback %u Hz: timing, feedback, reset, isolation and tail passed\n",rate);
    }
}
