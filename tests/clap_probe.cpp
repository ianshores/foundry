// Minimal Linux CLAP host: load, instantiate, activate and render stereo audio.
#include <clap/entry.h>
#include <clap/plugin-factory.h>
#include <clap/plugin.h>
#include <clap/host.h>
#include <clap/process.h>
#include <dlfcn.h>
#include <cmath>
#include <cstdio>
#include <vector>
#include <algorithm>
#include <chrono>
#include <xmmintrin.h>
static const void* Extension(const clap_host_t*, const char*) { return nullptr; }
static void Request(const clap_host_t*) {}
static uint32_t Size(const clap_input_events_t*) { return 0; }
static const clap_event_header_t* Event(const clap_input_events_t*,uint32_t) { return nullptr; }
static bool Push(const clap_output_events_t*,const clap_event_header_t*) { return true; }
int main(int argc,char** argv) {
    if(argc<2||argc>3)return 2;
    void* Lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!Lib){std::fprintf(stderr,"%s\n",dlerror());return 3;}
    const auto* Entry=(const clap_plugin_entry_t*)dlsym(Lib,"clap_entry");
    if(!Entry||!Entry->init(argv[1]))return 4;
    const auto* Factory=(const clap_plugin_factory_t*)Entry->get_factory(CLAP_PLUGIN_FACTORY_ID);
    if(!Factory||Factory->get_plugin_count(Factory)!=1)return 5;
    const auto* Desc=Factory->get_plugin_descriptor(Factory,0);
    clap_host_t Host={CLAP_VERSION,nullptr,"PdPipelineProbe","PD Patches","","1",Extension,Request,Request,Request};
    const auto* Plugin=Factory->create_plugin(Factory,&Host,Desc->id);
    if(!Plugin||!Plugin->init(Plugin)||!Plugin->activate(Plugin,48000,128,128)||!Plugin->start_processing(Plugin))return 6;
    float L[128]{},R[128]{},OL[128]{},OR[128]{};
    float* In[]={L,R};float* Out[]={OL,OR};
    clap_audio_buffer_t Input{};Input.data32=In;Input.channel_count=2;
    clap_audio_buffer_t Output{};Output.data32=Out;Output.channel_count=2;
    clap_input_events_t Events{nullptr,Size,Event};clap_output_events_t OutputEvents{nullptr,Push};
    clap_process_t Process{};Process.frames_count=128;Process.audio_inputs=&Input;Process.audio_outputs=&Output;
    Process.audio_inputs_count=1;Process.audio_outputs_count=1;Process.in_events=&Events;Process.out_events=&OutputEvents;
    std::vector<float> Left,Right;
    for(int Block=-64;Block<400;++Block){
        std::fill_n(L,128,0.f);std::fill_n(R,128,0.f);
        if(Block==0){L[0]=1.f;R[0]=1.f;}
        Process.steady_time=(Block+64)*128;
        if(Plugin->process(Plugin,&Process)==CLAP_PROCESS_ERROR)return 7;
        if(Block>=0){Left.insert(Left.end(),OL,OL+128);Right.insert(Right.end(),OR,OR+128);}
    }
    auto Peak=[](const std::vector<float>& A,int At){float V=0;for(int I=std::max(0,At-5);I<=At+5;++I)V=std::max(V,std::abs(A[I]));return V;};
    std::printf("CLAP %s: dry %.4f, left echo %.4f, right echo %.4f\n",Desc->id,Left[0],Peak(Left,12000),Peak(Right,18000));
    bool Good=std::abs(Left[0]-.7f)<.01f&&Peak(Left,12000)>.25f&&Peak(Right,18000)>.25f;
    if (argc==3) {
        // Fill buffers before starting the clock: measure plugin audio work only.
        auto Measure=[&](float Value) {
            std::fill_n(L,128,Value);std::fill_n(R,128,Value);
            const unsigned Original=_mm_getcsr();
            const unsigned HostFlags=Original & ~0x8040u;
            _mm_setcsr(HostFlags);
            for(int I=0;I<1000;++I)Plugin->process(Plugin,&Process);
            const auto Start=std::chrono::steady_clock::now();
            for(int I=0;I<20000;++I)Plugin->process(Plugin,&Process);
            const auto Duration=std::chrono::steady_clock::now()-Start;
            if ((_mm_getcsr() & 0xffc0u)!=(HostFlags & 0xffc0u)) Good=false;
            _mm_setcsr(Original);
            return std::chrono::duration<double>(Duration).count();
        };
        double Normal=Measure(.01f),Tiny=Measure(1.e-39f);
        std::printf("Audio-only benchmark: normal %.6fs, tiny %.6fs, ratio %.3f; host floating-point mode preserved\n",Normal,Tiny,Tiny/Normal);
    }
    Plugin->stop_processing(Plugin);Plugin->deactivate(Plugin);Plugin->destroy(Plugin);Entry->deinit();dlclose(Lib);
    return Good?0:8;
}
