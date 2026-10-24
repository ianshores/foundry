param([Parameter(Mandatory=$true)][string]$UERoot,[Parameter(Mandatory=$true)][string]$Project,[string]$Python='python',[string]$WwiseCapture='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $Project
$out=Split-Path -Parent $projectRoot
function Run-Demo([string]$Flag,[string]$Log){
 $arguments=@('"'+$Project+'"','/Game/PDReview/PersistentDemo','-game',$Flag,'-DeterministicAudio','-PdOfflineAudio','-ini:Engine:[ConsoleVariables]:au.UseRenderScheduler=0,au.nrt.RenderEveryTick=0','-NullRHI','-unattended','-nop4','-nosplash','-stdout','-FullStdOutLogOutput')
 $process=Start-Process "$UERoot\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" -ArgumentList $arguments -PassThru -RedirectStandardOutput "$out\$Log.log" -RedirectStandardError "$out\$Log-errors.log"
 $process.Handle | Out-Null # Retain the process handle so Windows exit status stays available.
 if(!$process.WaitForExit(180000)){Stop-Process -Id $process.Id;throw "Demo timed out: $Flag"}
 if($process.ExitCode -ne 0){throw "Demo failed: see $out\$Log.log"}
}
Run-Demo '-PdDemoTest' 'submix-streaming'
# The MetaSound test starts a fresh game instance and timeline. Preserve streaming evidence.
Copy-Item "$projectRoot\Saved\PD-Demo-Timeline.txt" "$out\PD-Demo-Timeline.txt" -Force
Run-Demo '-PdMetaDemoTest' 'metasound-clicks'
$arguments=@("$PSScriptRoot\..\verify_audio.py",'--unreal',"$projectRoot\Saved\BouncedWavFiles\PersistentDelayReturn.wav",'--timeline',"$out\PD-Demo-Timeline.txt",'--meta',"$projectRoot\Saved\BouncedWavFiles\MetaSoundClickDelay.wav",'--out',"$out\demo-verification.json")
if($WwiseCapture){$arguments+=@('--wwise',$WwiseCapture)}
& $Python @arguments
if($LASTEXITCODE -ne 0){throw 'Recorded audio validation failed'}
