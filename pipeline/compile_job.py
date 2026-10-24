"""Run pinned hvcc in its own environment and preserve structured diagnostics."""
import json
from pathlib import Path
import sys
from hvcc.compiler import compile_dataflow
job=json.loads(Path(sys.argv[1]).read_text())
if job.get('adapter') == 'convoy':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/convoy/tools'))
    from export import register
    register()
results=compile_dataflow(in_path=Path(job['patch']),out_dir=Path(job['output']),patch_name=job['name'],patch_meta_file=Path(job['metadata']),search_paths=[Path(p) for p in job['search_paths']],generators=job['generators'])
Path(job['results']).write_text(json.dumps(results.model_dump(),default=str,indent=2)+'\n')
failed=False
for stage in results.root.values():
    for warning in stage.notifs.warnings:print(f'WARNING {stage.stage}: {warning.message}')
    if stage.notifs.has_error:
        failed=True
        for error in stage.notifs.errors:print(f'ERROR {stage.stage}: {error.message}')
        if stage.notifs.exception:print(f'ERROR {stage.stage}: {stage.notifs.exception}')
if not failed:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/convoy/tools'))
    from patch_heavy_runtime import patch_light_pipe
    for pipe in Path(job['output']).rglob('HvLightPipe.c'):
        patch_light_pipe(pipe)
sys.exit(1 if failed else 0)
