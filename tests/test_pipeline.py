"""Regression tests for the pipeline and first compiled stereo delay."""
import ctypes as C
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import pdplugins as pipeline

class ManifestTests(unittest.TestCase):
    def test_manifest_contract(self):
        m=pipeline.load('stereo-delay')
        self.assertEqual(m['channels'],2)
        self.assertIn('adc~ 1 2',pipeline.wrapper(m))
        self.assertIn('r left_ms @hv_param',pipeline.wrapper(m))
    def test_init_creates_independent_project(self):
        with tempfile.TemporaryDirectory() as d:
            old=pipeline.ROOT
            try:
                pipeline.ROOT=Path(d)
                source=Path(d)/'external-module/effect.pd';source.parent.mkdir();source.write_text('#N canvas 0 0 400 300 10;\n')
                pipeline.init_project('AnotherEffect',source)
                p=Path(d)/'projects/anothereffect/plugin.json'
                m=pipeline.load(str(p))
                self.assertEqual(m['parameters'][0]['name'],'gain')
                self.assertEqual(m['_patch'],source)
                self.assertFalse((p.parent/'effect.pd').exists())
                with self.assertRaises(ValueError):pipeline.init_project('AnotherEffect',source)
            finally:pipeline.ROOT=old
    def test_invalid_parameter_rejected(self):
        m=json.loads((ROOT/'projects/stereo-delay/plugin.json').read_text());m['parameters'][0]['default']=float('nan')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plugin.json';p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):pipeline.load(str(p))
    def test_unsupported_layout_rejected(self):
        m=json.loads((ROOT/'projects/stereo-delay/plugin.json').read_text());m['channels']=6
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plugin.json';p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):pipeline.load(str(p))

class CompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=ROOT/'build/StereoDelay';cls.gen=cls.out/'generated';cls.check=cls.out/'checks';cls.check.mkdir(parents=True,exist_ok=True)
        if not cls.gen.exists():raise unittest.SkipTest('Export stereo-delay first.')
        pub=cls.out/'unreal/PdStereoDelay/Source/PdStereoDelay/Public'
        probe=cls.check/'probe.cpp'
        probe.write_text('''#include "PdStereoDelayDsp.hpp"
#ifdef _WIN32
#define PROBE_API __declspec(dllexport)
#else
#define PROBE_API
#endif
extern "C" {
PROBE_API void* create(double rate) { auto* d=new FPdStereoDelayDsp; if (!d->Init(rate)) { delete d; return nullptr; } return d; }
PROBE_API void destroy(void* d) { delete static_cast<FPdStereoDelayDsp*>(d); }
PROBE_API void set(void* d,int i,float v) { static_cast<FPdStereoDelayDsp*>(d)->Set(i,v); }
PROBE_API void process(void* d,const float* l,const float* r,float* ol,float* or_,int n) { static_cast<FPdStereoDelayDsp*>(d)->Process(l,r,ol,or_,n); }
PROBE_API void interleaved(void* d,const float* in,float* out,int n) { static_cast<FPdStereoDelayDsp*>(d)->ProcessInterleaved(in,out,n); }
}
''')
        objects=[]
        for src in sorted((cls.gen/'c').iterdir()):
            if src.suffix not in ('.c','.cpp'):continue
            obj=cls.check/(src.name+('.obj' if os.name=='nt' else '.o'));compiler='cc' if src.suffix=='.c' else 'c++'
            command=(['cl','/nologo','/c','/O1','/EHsc','/MD','/DHV_SIMD_NONE=1',str(src),'/Fo'+str(obj)] if os.name=='nt' else [compiler,'-c','-O1','-fPIC','-DHV_SIMD_NONE=1',str(src),'-o',str(obj)])
            subprocess.run(command,check=True,capture_output=True)
            objects.append(str(obj))
        library=cls.check/('probe.dll' if os.name=='nt' else 'libprobe.so')
        command=(['cl','/nologo','/std:c++17','/O1','/EHsc','/MD','/LD','/DHV_SIMD_NONE=1','/I'+str(pub),'/I'+str(cls.gen/'c'),str(probe),*objects,'/Fe'+str(library),'/Fo'+str(cls.check/'probe.obj')] if os.name=='nt' else ['c++','-std=c++17','-O1','-fPIC','-shared','-DHV_SIMD_NONE=1','-I'+str(pub),'-I'+str(cls.gen/'c'),str(probe),*objects,'-o',str(library)])
        subprocess.run(command,check=True)
        cls.lib=C.CDLL(str(library));fp=C.POINTER(C.c_float)
        cls.lib.create.argtypes=[C.c_double];cls.lib.create.restype=C.c_void_p
        cls.lib.destroy.argtypes=[C.c_void_p];cls.lib.set.argtypes=[C.c_void_p,C.c_int,C.c_float]
        cls.lib.process.argtypes=[C.c_void_p,fp,fp,fp,fp,C.c_int]
        cls.lib.interleaved.argtypes=[C.c_void_p,fp,fp,C.c_int]
    def render(self,block,rate=48000,interleaved=False):
        d=self.lib.create(rate);self.assertTrue(d)
        for i,v in enumerate([100,150,.5,1]):self.lib.set(d,i,v)
        def step(l,r):
            n=len(l);t=C.c_float*n;ol=t();or_=t()
            if interleaved:
                it=C.c_float*(2*n);inp=it(*[v for pair in zip(l,r) for v in pair]);out=it()
                self.lib.interleaved(d,inp,out,n);return list(out)[::2],list(out)[1::2]
            self.lib.process(d,t(*l),t(*r),ol,or_,n);return list(ol),list(or_)
        step([0.]*int(rate*.1),[0.]*int(rate*.1))
        left=[];right=[];total=int(rate*.6)
        for base in range(0,total,block):
            n=min(block,total-base);inp=[0.]*n
            if base==0:inp[0]=.5
            l,r=step(inp,inp);left+=l;right+=r
        self.lib.destroy(d);return left,right
    def test_delay_timing_and_feedback(self):
        for rate in (44100,48000,96000):
            l,r=self.render(127,rate)
            def peak(a,t):return max(abs(x) for x in a[int(t*rate)-5:int(t*rate)+6])
            self.assertAlmostEqual(peak(l,.1),.5,places=3)
            self.assertAlmostEqual(peak(r,.15),.5,places=3)
            self.assertAlmostEqual(peak(l,.2),.25,places=3)
            self.assertAlmostEqual(peak(l,.3),.125,places=3)
            self.assertLess(max(abs(x) for x in l[:int(rate*.09)]),1e-6)
    def test_odd_block_sizes_and_layouts_match(self):
        a=self.render(127);b=self.render(1024);c=self.render(257,interleaved=True)
        for x,y,z in zip(a,b,c):
            self.assertLess(max(abs(i-j) for i,j in zip(x,y)),1e-6)
            self.assertLess(max(abs(i-j) for i,j in zip(x,z)),1e-6)
    def test_wise_tail_counter(self):
        source=self.check/'tail.cpp'
        source.write_text('''#include "PdTailCounter.hpp"
#include <cassert>
int main() { FPdTailCounter t;
auto a=t.Advance(false,128,128,200); assert(a.Valid==128&&a.More);
a=t.Advance(true,64,128,200); assert(a.Valid==128&&a.More);
a=t.Advance(true,0,128,200); assert(a.Valid==128&&a.More);
a=t.Advance(true,0,128,200); assert(a.Valid==8&&!a.More);
a=t.Advance(true,0,128,200); assert(a.Valid==0&&!a.More);
t.Reset();a=t.Advance(true,0,128,0);assert(a.Valid==0&&!a.More);
}''')
        binary=self.check/('tail.exe' if os.name=='nt' else 'tail')
        command=(['cl','/nologo','/std:c++17','/EHsc','/I'+str(self.gen/'wwise/SoundEnginePlugin'),str(source),'/Fe'+str(binary),'/Fo'+str(self.check/'tail.obj')] if os.name=='nt' else ['c++','-std=c++17','-I'+str(self.gen/'wwise/SoundEnginePlugin'),str(source),'-o',str(binary)])
        subprocess.run(command,check=True)
        subprocess.run([str(binary)],check=True)
    def test_vst3_factory_loads(self):
        binary=self.gen/'bin/StereoDelay.vst3/Contents/x86_64-linux/StereoDelay.so'
        if not binary.exists():self.skipTest('Linux VST3 build not present.')
        lib=C.CDLL(str(binary));lib.GetPluginFactory.restype=C.c_void_p
        self.assertTrue(lib.GetPluginFactory())
    @unittest.skipUnless(sys.platform=='linux','Linux CLAP probe')
    def test_actual_clap_plugin(self):
        binary=self.gen/'bin/StereoDelay.clap'
        if not binary.exists():self.skipTest('Build REAPER target first.')
        probe=self.check/'clap_probe'
        subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'.toolchain/dpf/distrho/src'),str(ROOT/'tests/clap_probe.cpp'),'-ldl','-o',str(probe)],check=True)
        subprocess.run([str(probe),str(binary)],check=True)

if __name__=='__main__':unittest.main(verbosity=2)
