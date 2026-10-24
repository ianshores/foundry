#!/usr/bin/env python3
"""Foundry: build and deploy independently versioned DSP modules."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT/'pipeline/toolchain.json').read_text())
TARGETS = ('reaper', 'wwise', 'unreal-submix', 'metasound')

def fail(message):
    raise ValueError(message)

def run(args, cwd=None):
    args = list(map(str, args))
    print('+', subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, cwd=cwd or ROOT, check=True)

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def json_write(path, data):
    write(path, json.dumps(data, indent=2)+'\n')

def compiler_python():
    override = os.environ.get('PDPLUGINS_PYTHON')
    p = Path(override) if override else ROOT/'.toolchain/venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not p.is_file():
        fail('Compiler missing. Run python3 pipeline/bootstrap.py first.')
    return p

def load(project):
    manifest = Path(project)
    if not manifest.is_file():
        manifest = ROOT/'projects'/project/'plugin.json'
    manifest = manifest.resolve()
    data = json.loads(manifest.read_text())
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,39}', data.get('name', '')):
        fail('name must be an ASCII C++ identifier without underscores (1–40 characters).')
    if data.get('channels') != 2:
        fail('This pipeline currently requires stereo effects: channels must be 2.')
    if bool(data.get('patch')) == bool(data.get('abstraction')):
        fail('Set exactly one of patch or abstraction.')
    if 'abstraction' in data and not re.fullmatch(r'[A-Za-z0-9_./~-]+',data['abstraction']):
        fail('Unsupported abstraction name.')
    params=data.get('parameters',[])
    if not params: fail('Declare at least one float parameter.')
    reserved=set('alignas alignof and asm auto bool break case catch char class concept const consteval constexpr constinit continue co_await co_return co_yield decltype default delete do double else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept not nullptr operator or private protected public register reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor'.split())
    names=[]
    for p in params:
        if not re.fullmatch(r'[a-z][a-z0-9_]*',p.get('name','')): fail('Invalid parameter name.')
        if not re.fullmatch(r'[a-z][a-z0-9_]*',p.get('selector',p['name'])): fail('Invalid parameter selector.')
        if any(not isinstance(p.get(k),(int,float)) or isinstance(p[k],bool) or not math.isfinite(p[k]) for k in ('min','max','default')):
            fail('Parameter limits/defaults must be finite numbers.')
        if not p['min'] <= p['default'] <= p['max'] or p['min']==p['max']: fail('Invalid parameter range.')
        if p['name'] in reserved:fail('Parameter name is a reserved C++ keyword: '+p['name'])
        names.append(p['name'])
    if len(names)!=len(set(names)): fail('Parameter names must be unique.')
    for field in ('brand_id','unique_id'):
        if not re.fullmatch(r'[A-Za-z0-9]{4}',data.get(field,'')): fail(field+' must have four alphanumeric characters.')
    plugin_id=data.get('wwise_plugin_id')
    if not isinstance(plugin_id,int) or not 1<=plugin_id<=65535: fail('wwise_plugin_id must be 1..65535.')
    if not re.fullmatch(r'\d+\.\d+\.\d+',data.get('version','')): fail('version must be major.minor.patch.')
    tail=data.get('max_tail_seconds',10)
    if not isinstance(tail,(int,float)) or not math.isfinite(tail) or not 0<=tail<=600:fail('max_tail_seconds must be 0..600.')
    if data.get('adapter') not in (None,'convoy'): fail('Unknown module adapter.')
    data['_manifest']=manifest
    data['_paths']=[(manifest.parent/p).resolve() for p in data.get('search_paths',[])]
    if any(not p.is_dir() for p in data['_paths']): fail('A search path does not exist.')
    if 'patch' in data:
        data['_patch']=(manifest.parent/data['patch']).resolve()
        if not data['_patch'].is_file(): fail('Patch not found.')
    return data

def wrapper(m):
    # Audio first, one selector-message inlet last: reusable abstraction contract.
    lines=['#N canvas 30 30 1000 700 12;', '#X obj 30 30 adc~ 1 2;',f'#X obj 30 350 {m["abstraction"]};','#X obj 30 620 dac~ 1 2;']
    connects=['#X connect 0 0 1 0;','#X connect 0 1 1 1;','#X connect 1 0 2 0;','#X connect 1 1 2 1;']
    for i,p in enumerate(m['parameters']):
        x=260+(i%3)*240; y=30+(i//3)*110
        lines += [f'#X obj {x} {y} r {p["name"]} @hv_param {p["min"]} {p["max"]} {p["default"]};',f'#X msg {x} {y+40} {p.get("selector",p["name"])} \\$1;']
        n=3+i*2;connects += [f'#X connect {n} 0 {n+1} 0;',f'#X connect {n+1} 0 1 2;']
    return '\n'.join(lines+connects)+'\n'

def outdir(m): return ROOT/'build'/m['name']

def render(template, replacements):
    text=(ROOT/'pipeline/templates'/template).read_text()
    for k,v in replacements.items():text=text.replace('@'+k+'@',str(v))
    if re.search(r'@[A-Z_]+@',text):fail('Unexpanded template token in '+template)
    return text

def unreal(m, cdir, output, selected):
    name=m['name'];module='Pd'+name;api=module.upper()+'_API'
    output.mkdir(parents=True,exist_ok=True)
    source=output/'Source'/module
    priv=source/'Private';pub=source/'Public';heavy=priv/'Heavy'
    shutil.copytree(cdir,heavy,dirs_exist_ok=True)
    # Unreal treats undefined feature flags and local shadowing as errors even
    # though Heavy's portable sources rely on the normal C/C++ behavior.
    utils=heavy/'HvUtils.h'
    fallback='\n'.join('#ifndef '+flag+'\n#define '+flag+' 0\n#endif' for flag in ('HV_WIN','HV_APPLE','HV_ANDROID','HV_UNIX','HV_EMSCRIPTEN'))
    write(utils,utils.read_text().replace('// basic includes',fallback+'\n\n// basic includes'))
    pipe=heavy/'HvLightPipe.c'
    write(pipe,pipe.read_text().replace('#if __SSE__ || HV_SIMD_SSE','#if (defined(__SSE__) && __SSE__) || HV_SIMD_SSE').replace('#elif __arm__ || HV_SIMD_NEON','#elif (defined(__arm__) && __arm__) || HV_SIMD_NEON'))
    for cpp in heavy.glob('*.cpp'):
        write(cpp,'#if defined(_MSC_VER)\n#pragma warning(disable: 4458)\n#elif defined(__clang__)\n#pragma clang diagnostic ignored "-Wshadow"\n#endif\n'+cpp.read_text())
    params=m['parameters'];f=lambda x:format(float(x),'.10g')+('.0f' if float(x).is_integer() else 'f')
    common={'NAME':name,'COUNT':len(params),'API':api,'DISPLAY':m.get('display_name',name).replace('"','\\"'),'MAKER':m.get('maker','').replace('"','\\"')}
    common.update({'HASHES':', '.join('static_cast<unsigned>(HV_'+name.upper()+'_PARAM_IN_'+p['name'].upper()+')' for p in params),
        'MIN':', '.join(f(p['min']) for p in params),'MAX':', '.join(f(p['max']) for p in params),'DEFAULT':', '.join(f(p['default']) for p in params)})
    # Shared header lives in Public so Submix preset headers can include it.
    write(pub/('Pd'+name+'Dsp.hpp'),render('Dsp.hpp.in',common))
    deps=['Core','CoreUObject','Engine','AudioMixer','SignalProcessing']
    if 'metasound' in selected:deps+=['MetasoundEngine','MetasoundGraphCore','MetasoundFrontend','MetasoundStandardNodes']
    json_write(output/(module+'.uplugin'),{'FileVersion':3,'Version':1,'VersionName':m['version'],'FriendlyName':m.get('display_name',name),'Category':'Audio','CanContainContent':False,'Modules':[{'Name':module,'Type':'Runtime','LoadingPhase':'PostEngineInit'}], 'Plugins':[{'Name':'Metasound','Enabled':True}] if 'metasound' in selected else []})
    write(source/(module+'.Build.cs'),'''using UnrealBuildTool;
using System.IO;
public class '''+module+''' : ModuleRules {
    public '''+module+'''(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bUseUnity = false; // Generated Heavy translation units must remain separate.
        IWYUSupport = IWYUSupport.None; // Generated vendor files use their own include order.
        CppStandard = CppStandardVersion.Cpp20;
        PublicDependencyModuleNames.AddRange(new string[] { '''+', '.join('"'+d+'"' for d in deps)+''' });
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "Private", "Heavy"));
        PublicDefinitions.AddRange(new string[] { "HV_SIMD_NONE=1", "HV_SIMD_AVX=0", "HV_SIMD_SSE=0", "HV_SIMD_NEON=0", "HV_SIMD_FMA=0" });
'''+('        PrivateDefinitions.Add("METASOUND_PLUGIN='+module+'");\n        PrivateDefinitions.Add("METASOUND_MODULE='+module+'");\n' if 'metasound' in selected else '')+'''
    }
}
''')
    write(priv/(module+'Module.cpp'),'#include "Modules/ModuleManager.h"\n'+('#include "MetasoundFrontendModuleRegistrationMacros.h"\nMETASOUND_IMPLEMENT_MODULE_REGISTRATION_LIST\n' if 'metasound' in selected else '')+'class F'+module+'Module : public IModuleInterface { public: void StartupModule() override { '+('METASOUND_REGISTER_ITEMS_IN_MODULE' if 'metasound' in selected else '')+' } void ShutdownModule() override { '+('METASOUND_UNREGISTER_ITEMS_IN_MODULE' if 'metasound' in selected else '')+' } };\nIMPLEMENT_MODULE(F'+module+'Module, '+module+')\n')
    if 'unreal-submix' in selected:
        properties=[]
        for p in params:
            properties += ['    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PD", meta=(ClampMin="'+str(p['min'])+'", ClampMax="'+str(p['max'])+'"))',f'    float {p["name"]} = {f(p["default"])};']
        r=dict(common,PROPERTIES='\n'.join(properties),SET_SUBMIX='\n'.join(f'    Dsp.Set({i}, Settings.{p["name"]});' for i,p in enumerate(params)))
        write(pub/('Pd'+name+'Submix.h'),render('Submix.h.in',r));write(priv/('Pd'+name+'Submix.cpp'),render('Submix.cpp.in',r))
    if 'metasound' in selected:
        r=dict(common,PARAM_MEMBERS='\n'.join(f'    FFloatReadRef Param{i};' for i in range(len(params))),
            PARAM_INIT='\n'.join(f'        , Param{i}(Params.InputData.GetOrCreateDefaultDataReadReference<float>("{p["name"]}", Params.OperatorSettings))' for i,p in enumerate(params)),
            PARAM_VERTICES=''.join(f',\n                TInputDataVertex<float>("{p["name"]}", FDataVertexMetadata{{}}, {f(p["default"])})' for p in params),
            PARAM_BIND='\n'.join(f'        Data.BindReadVertex("{p["name"]}", Param{i});' for i,p in enumerate(params)),
            SET_META='\n'.join(f'        Dsp.Set({i}, *Param{i});' for i,p in enumerate(params)))
        write(priv/('Pd'+name+'MetaSound.cpp'),render('MetaSound.cpp.in',r))
    write(output/'README.md',f'''# {module}
Generated from {m['_manifest'].name}. Contains: {', '.join(selected)}.
Copy this folder into an Unreal project's Plugins directory, then rebuild the project.
For an installed engine use the pipeline build command, which calls RunUAT BuildPlugin.
Use a stereo submix; other submix layouts bypass. The MetaSound has Left/Right audio
inputs and outputs plus float parameter pins. Keep the MetaSound active for tails.
Changing parameters preserves the running DSP instance. Recreating the node or
submix effect clears its delay state. This export does not guarantee map-travel persistence.
Set the delay wet parameter to 1 on a parallel effects return.
''')

def export(m, targets):
    dest=outdir(m);dest.mkdir(parents=True,exist_ok=True)
    for stale in ('build-info.json','target-status.json'):
        (dest/stale).unlink(missing_ok=True)
    compiler=compiler_python()
    ver=subprocess.check_output([str(compiler),'-c',"import importlib.metadata;print(importlib.metadata.version('hvcc'))"],text=True).strip()
    if ver!=PIN['hvcc']:fail('Compiler version differs from pipeline/toolchain.json. Re-run bootstrap.')
    patch=m.get('_patch')
    if patch is None:
        patch=dest/'entry.pd';write(patch,wrapper(m))
    # Scalar DSP accepts any host block length, including odd tails.
    metadata={'nosimd':True,'dpf':{'plugin_formats':['clap','vst3'],'midi_input':False,'midi_output':False,'denormals':False,'maker':m.get('maker',''),'brand_id':m['brand_id'],'unique_id':m['unique_id'],'version':m['version'].replace('.',', '),'plugin_clap_id':'org.pdpatches.'+m['name'].lower()}}
    metadata['dpf']['plugin_clap_id']=m.get('clap_id',metadata['dpf']['plugin_clap_id'])
    if m.get('adapter')=='convoy':
        metadata['dpf'].pop('brand_id',None)
        metadata['dpf'].pop('unique_id',None)
        metadata['dpf'].update(homepage='https://github.com/ianshores/convoy',license='MIT (Convoy); see component notices')
    json_write(dest/'metadata.json',metadata)
    generated=dest/'generated'
    # Never leave a stale generated source file in a rebuilt target.
    if generated.exists():shutil.rmtree(generated)
    generators=['c']+(['dpf'] if 'reaper' in targets else [])+(['wwise'] if 'wwise' in targets else [])
    job=dest/'compile-job.json'
    json_write(job,{'adapter':m.get('adapter'),'patch':str(patch),'output':str(generated),'name':m['name'],'metadata':str(dest/'metadata.json'),'search_paths':list(map(str,m['_paths'])),'generators':generators,'results':str(dest/'compiler-results.json')})
    run([compiler,ROOT/'pipeline/compile_job.py',job])
    if m.get('adapter')=='convoy' and 'reaper' in targets:
        sys.path.insert(0,str(ROOT/'adapters/convoy/tools'))
        from add_wav_selector import configure
        configure(generated)
        makefile=generated/'plugin/source/Makefile'
        write(makefile,makefile.read_text()+'\nBUILD_CXX_FLAGS += -std=c++17 -fno-fast-math\nBUILD_C_FLAGS += -fno-fast-math\n')
    ir=json.loads((generated/'ir'/(m['name']+'.heavy.ir.json')).read_text())
    if ir['signal']['numInputBuffers']!=2 or ir['signal']['numOutputBuffers']!=2:fail('Compiled patch must have exactly two audio inputs and outputs.')
    header=(generated/'c'/('Heavy_'+m['name']+'.h')).read_text()
    for p in m['parameters']:
        if '_PARAM_IN_'+p['name'].upper() not in header:fail('Parameter was not exported: '+p['name'])
    # Do not infer SDK compatibility from a successful source export.
    if 'wwise' in targets:
        w=generated/'wwise';config=w/(m['name']+'Config.h');text=config.read_text();text=re.sub(r'PluginID = \d+',f'PluginID = {m["wwise_plugin_id"]}',text);write(config,text)
        xml=w/'WwisePlugin'/(m['name']+'.xml');write(xml,re.sub(r'PluginID="\d+"',f'PluginID="{m["wwise_plugin_id"]}"',xml.read_text()))
        # Heavy's generic wrapper needs bounded zero-input tail processing for delay FX.
        tail=w/'SoundEnginePlugin/PdTailCounter.hpp'
        write(tail, (ROOT/'pipeline/templates/TailCounter.hpp.in').read_text())
        h=w/'SoundEnginePlugin'/(m['name']+'FX.h')
        write(h,h.read_text().replace('#include <AK/SoundEngine/Common/IAkPlugin.h>', '#include <AK/SoundEngine/Common/IAkPlugin.h>\n#include "PdTailCounter.hpp"').replace('    uint32_t m_uSampleRate;','    uint32_t m_uSampleRate;\n    FPdTailCounter PdTail;'))
        cpp=w/'SoundEnginePlugin'/(m['name']+'FX.cpp');text=cpp.read_text()
        anchor='    io_pBuffer->ZeroPadToMaxFrames();'
        if text.count(anchor)!=1:fail('Pinned Wwise template changed; review tail integration.')
        # ZeroPadToMaxFrames changes uValidFrames: account for original input first.
        text=text.replace(anchor,'    const auto Tail = PdTail.Advance(io_pBuffer->eState == AK_NoMoreData, io_pBuffer->uValidFrames, io_pBuffer->MaxFrames(), static_cast<int64_t>(m_uSampleRate * '+str(m.get('max_tail_seconds',10))+'));\n'+anchor+'\n    io_pBuffer->eState = Tail.More ? AK_DataReady : AK_NoMoreData;')
        text=text.replace('io_pBuffer->uValidFrames = numFramesToProcess;', 'io_pBuffer->uValidFrames = static_cast<AkUInt16>(Tail.Valid);')
        reset_code = '\n    PdTail.Reset();\n    auto* Context = static_cast<Heavy_'+m['name']+'*>(m_pHeavyCtx);\n    Context->~Heavy_'+m['name']+'();\n    new (Context) Heavy_'+m['name']+'(static_cast<double>(m_uSampleRate), 10, 4, 2);\n    Context->setUserData(this);\n#ifndef AK_OPTIMIZED\n    Context->setPrintHook(&'+m['name']+'_Private::OnHeavyPrint);\n#endif\n    m_pParams->m_paramChangeHandler.SetAllParamChanges();'
        text=text.replace(m['name']+'FX::Reset()\n{',m['name']+'FX::Reset()\n{'+reset_code)
        text=text.replace('in_rFormat.GetNumChannels() > 2','in_rFormat.GetNumChannels() != 2').replace('only supports one and two channel bus configurations','requires a stereo bus configuration')
        text='#include <new>\n'+text
        write(cpp,text)
        premake=w/'PremakePlugin.lua';write(premake,premake.read_text().replace('Plugin.sdk.static.defines = {}','Plugin.sdk.static.defines = { "HV_SIMD_NONE=1" }'))

    ue=dest/'unreal'/('Pd'+m['name'])
    if ue.exists():shutil.rmtree(ue)
    selected=[t for t in targets if t.startswith('unreal') or t=='metasound']
    if selected:unreal(m,generated/'c',ue,selected)
    inputs=[m['_manifest'],patch,ROOT/'pipeline/toolchain.json',ROOT/'pipeline/requirements.lock',*sorted((ROOT/'pipeline/patches').glob('*.json')),*[f for path in m['_paths'] for f in sorted(path.rglob('*.pd'))],*sorted((ROOT/'pipeline').rglob('*.py')),*sorted((ROOT/'pipeline/templates').glob('*'))]
    if m.get('adapter')=='convoy':
        sys.path.insert(0,str(ROOT/'adapters/convoy/tools'))
        from engine import require_engine
        engine=require_engine()
        inputs += sorted((engine/'include').glob('*.hpp')) + [engine/'module.json',engine/'LICENSE']
        inputs += [p for p in sorted((ROOT/'adapters/convoy').rglob('*')) if p.is_file() and p.suffix in ('.py','.cpp','.hpp','.pd') and 'build' not in p.relative_to(ROOT/'adapters/convoy').parts and '__pycache__' not in p.parts]
        if 'wwise' in targets:
            premake=generated/'wwise/PremakePlugin.lua'
            write(premake,premake.read_text()+'\n-- Convoy is a C++17 module.\ncppdialect "C++17"\n')
    json_write(dest/'build-info.json',{'project':m['name'],'targets':targets,'hvcc':ver,'dpf_commit':PIN['dpf_commit'],'host':platform.platform(),'source_sha256':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'status':'source-generated; target builds require separate verification'})
    print('Exported:',dest)

def sdk_config():
    p=ROOT/'local-sdk.json';return json.loads(p.read_text()) if p.exists() else {}

def doctor(strict=False):
    cfg=sdk_config();missing=[]
    for label,ok in [('C++ compiler',bool(shutil.which('g++') or shutil.which('clang++') or shutil.which('cl'))),('make',bool(shutil.which('make'))),('DPF', (ROOT/'.toolchain/dpf/Makefile.plugins.mk').is_file())]:
        print(('OK      ' if ok else 'MISSING ')+label)
        if not ok:missing.append(label)
    try:
        py=compiler_python();run([py,'-c','import sys; from hvcc import main; sys.exit(main())','-V'])
    except (ValueError,subprocess.CalledProcessError):missing.append('hvcc')
    engine=os.environ.get('UE_ROOT',cfg.get('ue_root',''))
    ww=os.environ.get('WWISEROOT',cfg.get('wwise_root',''))
    for label,root,rel in [('Unreal Engine',engine,'Engine/Build/Build.version'),('Wwise SDK',ww,'SDK/include/AK/AkWwiseSDKVersion.h')]:
        found=bool(root) and (Path(root)/rel).is_file()
        print(('OK      ' if found else 'MISSING ')+label)
        if found and label=='Unreal Engine':print((Path(root)/rel).read_text())
        if found and label=='Wwise SDK':print((Path(root)/rel).read_text()[:1800])
        if not found:missing.append(label)
    print('Unreal/Wwise integration compatibility: select a supported pair in Wwise Launcher; source generation does not prove compatibility.')
    if strict and missing:fail('Missing prerequisites: '+', '.join(missing))

def patch_dpf(copy):
    spec=json.loads((ROOT/'pipeline/patches/dpf-clap-state.json').read_text())
    target=copy/spec['path']
    original=(ROOT/'.toolchain/dpf'/spec['path']).read_text()
    if hashlib.sha256(original.encode()).hexdigest()!=spec['source_sha256']:
        fail('DPF state-reader source changed; review the pinned compatibility patch.')
    patched=original
    for replacement in spec['replacements']:
        if patched.count(replacement['old'])!=1:fail('DPF patch anchor is not unique.')
        patched=patched.replace(replacement['old'],replacement['new'])
    current=target.read_text()
    if current not in (original,patched):fail('Generated DPF source has unexpected local changes; export again.')
    write(target,patched)

def build(m,target,args):
    dest=outdir(m);generated=dest/'generated';cfg=sdk_config()
    if not (generated/'c').exists():fail('Export this project before building.')
    info=json.loads((dest/'build-info.json').read_text())
    for path,digest in info['source_sha256'].items():
        src=Path(path) if Path(path).is_absolute() else ROOT/path
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest()!=digest:fail('Sources changed; export the project again before building.')
    if target not in info['targets']:fail('Target was not exported; export it first.')
    if target=='reaper':
        dpf=ROOT/'.toolchain/dpf'
        if not (dpf/'Makefile.plugins.mk').exists():fail('Run bootstrap to install pinned DPF.')
        actual=subprocess.check_output(['git','-C',str(dpf),'rev-parse','HEAD'],text=True).strip()
        if actual!=PIN['dpf_commit']:fail('DPF commit does not match toolchain pin.')
        copy=generated/'dpf'
        if not copy.exists():shutil.copytree(dpf,copy,ignore=shutil.ignore_patterns('.git'))
        patch_dpf(copy)
        run(['make','-C',generated/'plugin/source','-j',str(args.jobs),'clap','vst3'])
        print('REAPER plugins:',generated/'bin')
    elif target in ('unreal-submix','metasound'):
        root=args.ue_root or os.environ.get('UE_ROOT') or cfg.get('ue_root')
        if not root:fail('Set UE_ROOT or --ue-root to an installed engine supporting your Wwise integration.')
        root=Path(root);version=root/'Engine/Build/Build.version'
        if not version.is_file():fail('UE_ROOT must contain Engine/Build/Build.version.')
        v=json.loads(version.read_text())
        if v.get('MajorVersion')!=5:fail('This generator targets Unreal Engine 5.')
        host='Win64' if os.name=='nt' else ('Mac' if sys.platform=='darwin' else 'Linux')
        uat=root/'Engine/Build/BatchFiles'/('RunUAT.bat' if os.name=='nt' else host.replace('Win64','')+'/RunUAT.sh')
        if not uat.is_file():fail('RunUAT not found: '+str(uat))
        descriptor=dest/'unreal'/('Pd'+m['name'])/('Pd'+m['name']+'.uplugin')
        cmd=[uat,'BuildPlugin','-Plugin='+str(descriptor),'-Package='+str(dest/'packages'/('Pd'+m['name'])),'-TargetPlatforms='+args.platforms]
        run((['cmd','/c'] if os.name=='nt' else ['bash'])+cmd)
    else:
        root=args.wwise_root or os.environ.get('WWISEROOT') or cfg.get('wwise_root')
        if not root:fail('Set WWISEROOT or --wwise-root to your Wwise installation.')
        script=Path(root)/'Scripts/Build/Plugins/wp.py'
        if not script.is_file():fail('Wwise wp.py not found: '+str(script))
        env=os.environ.copy();env['WWISEROOT']=str(Path(root).resolve());env['WWISESDK']=str(Path(root).resolve()/'SDK')
        platforms=list(dict.fromkeys((['Authoring'] if os.name=='nt' else [])+[args.wwise_platform]))
        inferred=re.search(r'_(vc\d+)$',args.wwise_platform)
        toolset=getattr(args,'wwise_toolset',None) or (inferred.group(1) if inferred else 'vc170')
        flags=['-t',toolset] if os.name=='nt' else []
        premake_flags=['--disable-codesign'] if os.name=='nt' and not getattr(args,'wwise_codesign',False) else []
        for platform_name in platforms:
            for step in [('premake',*flags,*premake_flags,platform_name),('build','-c','Release','-x','x64',*flags,platform_name)]:
                cmd=[sys.executable,str(script),*step]
                print('+',subprocess.list2cmdline(cmd));subprocess.run(cmd,cwd=generated/'wwise',env=env,check=True)
    statuses=dest/'target-status.json'
    data=json.loads(statuses.read_text()) if statuses.exists() else {}
    data[target]={'status':'build-succeeded','host':platform.platform()};json_write(statuses,data)

def init_project(name, patch):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,39}',name):fail('Use an alphanumeric project name beginning with a letter.')
    source=Path(patch).resolve()
    if not source.is_file() or source.suffix!='.pd':fail('Supply an existing top-level Pd patch from its module repository.')
    dest=ROOT/'projects'/name.lower()
    if dest.exists():fail('Project directory already exists: '+str(dest))
    h=hashlib.sha256(name.encode()).hexdigest()
    manifest={'name':name,'display_name':name,'patch':os.path.relpath(source,dest),'search_paths':[os.path.relpath(source.parent,dest)],'channels':2,'maker':'','brand_id':'PdFx','unique_id':h[:4],'version':'0.1.0','wwise_plugin_id':max(1,int(h[:4],16)),'max_tail_seconds':1,'parameters':[{'name':'gain','selector':'gain','label':'Gain','min':0,'max':1,'default':1}]}
    json_write(dest/'plugin.json',manifest)
    print('Created deployment recipe:',dest,'— edit its parameters to match the external patch.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    i=sub.add_parser('init');i.add_argument('name');i.add_argument('--patch',required=True,help='Top-level Pd patch in an independent module repository')
    d=sub.add_parser('doctor');d.add_argument('--strict',action='store_true')
    e=sub.add_parser('export');e.add_argument('project');e.add_argument('--target',choices=['all',*TARGETS],default='all')
    b=sub.add_parser('build');b.add_argument('project');b.add_argument('--target',choices=['all',*TARGETS],required=True);b.add_argument('--jobs',type=int,default=4);b.add_argument('--ue-root');b.add_argument('--wwise-root');b.add_argument('--platforms',default='Win64' if os.name=='nt' else 'Linux');b.add_argument('--wwise-platform',default='Windows_vc170' if os.name=='nt' else 'Linux')
    b.add_argument('--wwise-toolset',choices=['vc160','vc170','vc180'],help='Windows compiler selection; inferred from the Wwise platform when omitted')
    b.add_argument('--wwise-codesign',action='store_true',help='Enable the Wwise SDK signing steps using an already configured certificate')
    args=parser.parse_args()
    if args.command=='init':init_project(args.name,args.patch);return
    if args.command=='doctor':doctor(args.strict);return
    m=load(args.project)
    if args.command=='export':export(m,list(TARGETS) if args.target=='all' else [args.target])
    elif args.command=='build':
        errors=[]
        for target in (TARGETS if args.target=='all' else [args.target]):
            try:build(m,target,args)
            except (ValueError,FileNotFoundError,subprocess.CalledProcessError) as error:
                errors.append(target+': '+str(error))
                status=outdir(m)/'target-status.json'
                data=json.loads(status.read_text()) if status.exists() else {}
                data[target]={'status':'not-built','reason':str(error)};json_write(status,data)
                print('NOT BUILT:',errors[-1],file=sys.stderr)
        if errors:fail('Some targets were not built. See target-status.json.')
if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,subprocess.CalledProcessError) as error:
        print('ERROR:',error,file=sys.stderr);sys.exit(1)
