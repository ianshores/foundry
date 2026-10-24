import json
from pathlib import Path
import unreal as u
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
placement={}
for name in ['Room_A','Room_B','PersistentDemo']:
    assert levels.load_level('/Game/PDReview/'+name)
    assert levels.set_current_level_by_name(name)
    placement[name]=[{'actor':a.get_path_name(),'label':a.get_actor_label(),'pitch':a.get_editor_property('audio').get_editor_property('pitch_multiplier'),'looping':a.get_editor_property('audio').get_editor_property('sound').get_editor_property('looping')} for a in actors.get_all_level_actors() if a.get_class().get_name()=='PdRoomClickSource' and a.get_outer()==levels.get_current_level()]
assert len(placement['Room_A'])==1 and len(placement['Room_B'])==1 and not placement['PersistentDemo'],placement
assert placement['Room_A'][0]['pitch']==.5 and placement['Room_B'][0]['pitch']==2.,placement
assert all(placement[n][0]['looping'] for n in ['Room_A','Room_B']),placement
Path(u.Paths.project_dir(),'source-placement.json').write_text(json.dumps(placement,indent=2))
u.log('PD_SOURCE_PLACEMENT_VERIFIED '+json.dumps(placement))
levels.load_level('/Game/PDReview/Room_A')
actors.set_selected_level_actors([a for a in actors.get_all_level_actors() if a.get_class().get_name()=='PdRoomClickSource'])
