"""Runs inside UnrealEditor-Cmd; invoked by unreal_host.py."""
import unreal
import json
from pathlib import Path

def ok(result,label):
    if result!=unreal.MetaSoundBuilderResult.SUCCEEDED:
        raise RuntimeError(label+': '+str(result))

cls=unreal.load_class(None,'/Script/PdStereoDelay.PdStereoDelaySubmixPreset')
if cls is None:raise RuntimeError('Submix preset class is unavailable')
preset=unreal.new_object(cls)
settings=preset.get_editor_property('settings')
expected={'left_ms':250.0,'right_ms':375.0,'feedback':.35,'wet':1.0}
for name,value in expected.items():settings.set_editor_property(name,value)
preset.set_settings(settings)
for name,value in expected.items():
    actual=preset.get_editor_property('settings').get_editor_property(name)
    if abs(actual-value)>1e-6:raise RuntimeError('Preset setting failed: '+name)
asset_path='/Game/PDReview/PD_StereoDelayReturn'
factory=unreal.SoundSubmixEffectFactory()
factory.set_editor_property('sound_effect_submix_preset_class',cls)
saved=unreal.EditorAssetLibrary.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset('PD_StereoDelayReturn','/Game/PDReview',cls,factory)
if saved is None:raise RuntimeError('Could not save Submix preset asset')
saved.set_settings(settings)
if not unreal.EditorAssetLibrary.save_loaded_asset(saved):raise RuntimeError('Could not save preset')

subsystem=unreal.get_engine_subsystem(unreal.MetaSoundBuilderSubsystem)
builder,on_play,on_finished,audio_outputs,result=subsystem.create_source_builder('PdStereoDelayReview',unreal.MetaSoundOutputAudioFormat.STEREO,False)
ok(result,'Create stereo source')
name=unreal.MetasoundFrontendClassName(namespace='PD',name='StereoDelay',variant='Stereo')
delay,result=builder.add_node_by_class_name(name,1)
ok(result,'Register compiled PD delay node')
pins={}
inputs,result=builder.find_node_inputs(delay)
ok(result,'Read delay inputs')
for pin in inputs:
    pin_name,pin_type,result=builder.get_node_input_data(pin)
    ok(result,'Inspect input')
    pins[str(pin_name)]=str(pin_type)
if pins!={'Left':'Audio','Right':'Audio','left_ms':'Float','right_ms':'Float','feedback':'Float','wet':'Float'}:
    raise RuntimeError('Unexpected delay node interface: '+str(pins))
sine_name=unreal.MetasoundFrontendClassName(namespace='UE',name='Sine',variant='Audio')
sine,result=builder.add_node_by_class_name(sine_name,1)
ok(result,'Add review tone oscillator')
sine_output,result=builder.find_node_output_by_name(sine,'Audio')
ok(result,'Find tone output')
for index,channel in enumerate(['Left','Right']):
    incoming,result=builder.find_node_input_by_name(delay,channel)
    ok(result,'Find delay input')
    ok(builder.connect_nodes(sine_output,incoming),'Connect oscillator to '+channel)
    outgoing,result=builder.find_node_output_by_name(delay,channel)
    ok(result,'Find delay output')
    ok(builder.connect_nodes(outgoing,audio_outputs[index]),'Connect delay to source output')
editor=unreal.get_editor_subsystem(unreal.MetaSoundEditorSubsystem)
literal_library=unreal.MetasoundFrontendLiteralBlueprintAccess
for index,(param,value) in enumerate({'left_ms':250.0,'right_ms':375.0,'feedback':.35,'wet':.3}.items()):
    literal=literal_library.create_float_meta_sound_literal(value)
    graph_input,result=builder.add_graph_input_node(param,'Float',literal,False)
    ok(result,'Expose '+param)
    parent,result=builder.find_node_output_parent(graph_input)
    ok(result,'Find graph input node')
    ok(editor.set_node_location(builder,parent,unreal.Vector2D(-450,250+index*150)),'Position control')
    node_input,result=builder.find_node_input_by_name(delay,param)
    ok(result,'Find '+param)
    ok(builder.connect_nodes(graph_input,node_input),'Connect '+param)
editor=unreal.get_editor_subsystem(unreal.MetaSoundEditorSubsystem)
ok(editor.set_node_location(builder,sine,unreal.Vector2D(-350,0)),'Position oscillator')
ok(editor.set_node_location(builder,delay,unreal.Vector2D(0,100)),'Position delay')
for index,handle in enumerate(audio_outputs):
    parent,result=builder.find_node_input_parent(handle)
    ok(result,'Find graph output node')
    ok(editor.set_node_location(builder,parent,unreal.Vector2D(500,index*200)),'Position output')
source,result=editor.build_to_asset(builder,'Ian Shores','MS_StereoDelayReview','/Game/PDReview')
ok(result,'Build review source asset')
source.set_editor_property('volume',.05)
if not unreal.EditorAssetLibrary.save_loaded_asset(source):raise RuntimeError('Could not save MetaSound')
result={'status':'passed','engine':unreal.SystemLibrary.get_engine_version(),
    'preset_asset':asset_path,'source_asset':source.get_path_name(),'node_inputs':pins,
    'graph':'Sine oscillator -> compiled PD stereo delay -> stereo output; four exposed controls',
    'limitations':'Headless load, settings and graph-build checks. Listening and game-level transition routing remain manual.'}
Path(unreal.Paths.project_dir()).joinpath('review-result.json').write_text(json.dumps(result,indent=2))
unreal.log('PD_REVIEW_ASSETS_PASSED '+json.dumps(result))
