"""Run with UnrealEditor-Cmd -run=pythonscript -script=... after building demo module."""
import json
from pathlib import Path
import unreal as u
folder='/Game/PDReview'
assets=u.AssetToolsHelpers.get_asset_tools()
u.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([folder],True)
project=Path(u.Paths.project_dir())
# The generated samples are shared with the Wwise review project.
samples=project.parent/'Samples'
for name in ['Click','ClickLoop','RoomClickLoop']:
    task=u.AssetImportTask();task.filename=str(samples/(name+'.wav'));task.destination_path=folder
    task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=True
    assets.import_asset_tasks([task])
    if not task.imported_object_paths:raise RuntimeError('Sound import failed: '+name)
loop=u.load_asset(folder+'/ClickLoop');room_loop=u.load_asset(folder+'/RoomClickLoop')
room_loop.set_editor_property('looping',True)
for wave in [loop,room_loop]:
    wave.set_editor_property('sound_asset_compression_type',u.SoundAssetCompressionType.PCM)
    u.EditorAssetLibrary.save_loaded_asset(wave)

# A real stereo submix asset with the actual compiled submix preset in its chain.
preset_class=u.load_class(None,'/Script/PdStereoDelay.PdStereoDelaySubmixPreset')
preset=u.load_asset(folder+'/PD_StereoDelayReturn')
if preset is None:
    factory=u.SoundSubmixEffectFactory();factory.set_editor_property('sound_effect_submix_preset_class',preset_class)
    preset=assets.create_asset('PD_StereoDelayReturn',folder,preset_class,factory)
settings=preset.get_editor_property('settings')
for key,value in {'left_ms':700.,'right_ms':1050.,'feedback':.72,'wet':1.}.items():settings.set_editor_property(key,value)
preset.set_settings(settings);u.EditorAssetLibrary.save_loaded_asset(preset)
submix=u.load_asset(folder+'/SM_PersistentDelayReturn')
if submix is None:submix=assets.create_asset('SM_PersistentDelayReturn',folder,u.SoundSubmix,u.SoundSubmixFactory())
submix.set_editor_property('auto_disable',False)
submix.set_editor_property('submix_effect_chain',[preset])
u.EditorAssetLibrary.save_loaded_asset(submix)

# The sample contains 65ms of transient followed by silence; looping it every four
# seconds leaves ample space for distinct echoes instead of a continuous tone.
def ok(result,label):
    if result!=u.MetaSoundBuilderResult.SUCCEEDED:raise RuntimeError(label+': '+str(result))
system=u.get_engine_subsystem(u.MetaSoundBuilderSubsystem)
b,onplay,onfinished,outputs,result=system.create_source_builder('PD_ClickDemo',u.MetaSoundOutputAudioFormat.STEREO,False);ok(result,'builder')
def add(namespace,name,variant):
    node,result=b.add_node_by_class_name(u.MetasoundFrontendClassName(namespace=namespace,name=name,variant=variant),1);ok(result,name);return node
def inp(node,name):
    h,r=b.find_node_input_by_name(node,name);ok(r,name);return h
def out(node,name):
    h,r=b.find_node_output_by_name(node,name);ok(r,name);return h
def connect(a,z):ok(b.connect_nodes(a,z),'connect')
lit=u.MetasoundFrontendLiteralBlueprintAccess
player=add('UE','Wave Player','Stereo');delay=add('PD','StereoDelay','Stereo')
connect(onplay,inp(player,'Play'))
ok(b.set_node_input_default(inp(player,'Wave Asset'),lit.create_object_meta_sound_literal(loop)),'set wave')
ok(b.set_node_input_default(inp(player,'Loop'),lit.create_bool_meta_sound_literal(True)),'loop')
for i,channel in enumerate(['Left','Right']):
    connect(out(player,'Out '+channel),inp(delay,channel));connect(out(delay,channel),outputs[i])
editor=u.get_editor_subsystem(u.MetaSoundEditorSubsystem)
for i,(name,value) in enumerate({'left_ms':700.,'right_ms':1050.,'feedback':.65,'wet':.65}.items()):
    h,r=b.add_graph_input_node(name,'Float',lit.create_float_meta_sound_literal(value),False);ok(r,name);connect(h,inp(delay,name))
    parent,r=b.find_node_output_parent(h);ok(r,name);ok(editor.set_node_location(b,parent,u.Vector2D(-400,250+140*i)),'position')
for node,pos in [(player,(-450,-200)),(delay,(50,50))]:ok(editor.set_node_location(b,node,u.Vector2D(*pos)),'position')
for i,h in enumerate(outputs):
    parent,r=b.find_node_input_parent(h);ok(r,'outputparent');ok(editor.set_node_location(b,parent,u.Vector2D(600,100+i*160)),'position')
meta=u.load_asset(folder+'/MS_ClickDelay')
if meta is None:
    meta,r=editor.build_to_asset(b,'Ian Shores','MS_ClickDelay',folder);ok(r,'save MetaSound')
u.EditorAssetLibrary.save_loaded_asset(meta)
# Remove the misleading sine demo from this separate review project.
u.EditorAssetLibrary.delete_asset(folder+'/MS_StereoDelayReview')
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
def open_map(name):
    if (project/'Content/PDReview'/(name+'.umap')).exists():
        if not levels.load_level(folder+'/'+name):raise RuntimeError('load '+name)
    elif not levels.new_level(folder+'/'+name):raise RuntimeError('create '+name)
for index,name in enumerate(['Room_A','Room_B']):
    open_map(name)
    for actor in actors.get_all_level_actors():
        if actor.get_class().get_name() in ['PdDelayDemo','PdRoomClickSource'] or actor.get_actor_label().startswith(name+'_'):
            actors.destroy_actor(actor)
    marker=actors.spawn_actor_from_class(u.Actor,u.Vector(0,0,0));marker.set_actor_label(name+'_Streamed_Content')
    cube=actors.spawn_actor_from_class(u.StaticMeshActor,u.Vector(index*300,0,0))
    cube.set_actor_label(name+'_Geometry');cube.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
    source=actors.spawn_actor_from_class(u.load_class(None,'/Script/DelayReview.PdRoomClickSource'),u.Vector(0,0,100))
    source.set_actor_label(name+'_Click_Source')
    source.get_editor_property('audio').set_editor_property('sound',room_loop)
    source.get_editor_property('audio').set_editor_property('pitch_multiplier',.5 if name=='Room_A' else 2.)
    levels.save_current_level()
open_map('PersistentDemo')
world=u.EditorLevelLibrary.get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode',u.load_class(None,'/Script/DelayReview.PdDemoGameMode'))
for name in ['Room_A','Room_B']:
    level=u.GameplayStatics.get_streaming_level(world,name)
    if level is None:level=u.EditorLevelUtils.add_level_to_world(world,folder+'/'+name,u.LevelStreamingDynamic)
    if level is None:raise RuntimeError('streaming '+name)
    level.set_editor_property('initially_loaded',False);level.set_editor_property('initially_visible',False)
    level.set_editor_property('should_be_loaded',False);level.set_editor_property('should_be_visible',False)
assert levels.set_current_level_by_name('PersistentDemo'),'Persistent level not found'
for actor in actors.get_all_level_actors():
    if actor.get_class().get_name()=='PdDelayDemo':actors.destroy_actor(actor)
demo=actors.spawn_actor_from_class(u.load_class(None,'/Script/DelayReview.PdDelayDemo'),u.Vector(0,0,0))
demo.set_actor_label('PD_Delay_Demo_Controller');demo.set_editor_property('meta_click',meta);demo.set_editor_property('shared_return',submix)
levels.save_all_dirty_levels();u.EditorAssetLibrary.save_directory(folder)
result={'status':'assets-created','meta':meta.get_path_name(),'return':submix.get_path_name(),'preset':preset.get_path_name(),'map':folder+'/PersistentDemo','streamed_levels':['Room_A','Room_B'],'saved_source_levels':['Room_A','Room_B'],'source_looping':True,'room_pitches':{'Room_A':.5,'Room_B':2.}}
(project/'demo-assets-result.json').write_text(json.dumps(result,indent=2));u.log('PD_AUDIBLE_ASSETS '+json.dumps(result))

placement={}
for name in ['Room_A','Room_B','PersistentDemo']:
    levels.load_level(folder+'/'+name)
    assert levels.set_current_level_by_name(name)
    placement[name]=[{'actor':a.get_path_name(),'label':a.get_actor_label(),'pitch':a.get_editor_property('audio').get_editor_property('pitch_multiplier'),'looping':a.get_editor_property('audio').get_editor_property('sound').get_editor_property('looping')} for a in actors.get_all_level_actors() if a.get_class().get_name()=='PdRoomClickSource' and a.get_outer()==levels.get_current_level()]
assert len(placement['Room_A'])==1,placement
assert len(placement['Room_B'])==1 and not placement['PersistentDemo'],placement
assert placement['Room_A'][0]['pitch']==.5 and placement['Room_B'][0]['pitch']==2.,placement
assert placement['Room_A'][0]['looping'] and placement['Room_B'][0]['looping'],placement
(project/'source-placement.json').write_text(json.dumps(placement,indent=2))
levels.load_level(folder+'/PersistentDemo')
