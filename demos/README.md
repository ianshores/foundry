# Audible delay demos

The review projects deliberately use short clicks with silence between them. There
are separate demonstrations for Wwise, the native Unreal submix effect, and the
MetaSound node. Wwise and Unreal remain separate projects.

## Review on Cradle

Open `C:\dev\pd-patches-build\room-source-review\DelayReview\DelayReview.uproject`
with UE 5.8.4. Open `/Game/PDReview/PersistentDemo` and press Play, then click the
play viewport to give it keyboard focus.

- **1**: persistent submix / streamed-level transition (starts automatically).
- **2**: MetaSound click loop; a transient every four seconds.
- **Space**: send another click from the currently loaded room.
- **R**: restart the streaming sequence.
- **Escape**: stop Play in Editor.

The submix demo streams Room A, triggers `Room_A_Click_Source`, a looping sound actor saved directly in that
room, unloads it 350 ms later, runs full garbage collection, then streams Room B.
The first left/right echoes arrive at 700/1050 ms, after the source actor has been
destroyed. Room A uses pitch 0.5x (low knock), and Room B uses 2.0x (high click), two octaves apart. The demo alternates between them, always destroying the previous source during unloading. The HUD reports actual streaming
state. The extra garbage collection is intentional stress testing, not a
requirement for using the return in a game.

Open `Room_A` or `Room_B` in the editor to inspect the placed source and its Audio component. `source-placement.json` records saved actor ownership: one source in each room with its saved pitch, and none in PersistentDemo. The runtime also checks that this looping source is still playing immediately before unload.

`UPdDelayReturnSubsystem` holds the return asset for the GameInstance lifetime.
The audio device owns the effect instance. The subsystem activates its chain once, after the playable world exists, and holds both the return and preset through garbage collection. `/Game/PDReview/SM_PersistentDelayReturn`
has automatic silence disabling turned off and contains the compiled
`PD_StereoDelayReturn` preset at 100% wet. `SendToDelay(AudioComponent, Amount)` is
the reusable send entry point. The source keeps its normal dry path as well.
Room actors never own or recreate the return. The persistent controller contains no Submix-demo source or click asset. Its separate MetaSound preview is used only in mode 2.

The MetaSound `/Game/PDReview/MS_ClickDelay` plays `ClickLoop` through the compiled
PD node and exposes all four controls. The loop is a short transient followed by
silence, not a sustained tone. The default dry/wet mix is 35/65 percent.

Open `C:\dev\pd-patches-build\audible-review\WwiseClickDemo\WwiseClickDemo.wproj`
with Wwise 2025.1.12. In Containers > Default Work Unit, select
`01_Clicks_PD_Send` and press Space to audition it. Compare
`02_Dry_Clicks_Reference`. The 28-second clip contains clicks four seconds apart.
The sound sends to Busses > Default Work Unit > Main Audio Bus > `PD_Delay_Return`,
which hosts the wet-only `PD_ClickDelay_700_1050` ShareSet. A Play event is also
provided under Events. Edit the ShareSet to hear the parameters change.

## Reproduce

Build/package the PD plugin with the normal pipeline first. On Windows, run:

```powershell
python demos/wwise/build_demo.py --sdk C:/dev/sdks/Wwise2025.1.12.9287 --out C:/dev/pd-patches-build/audible-review --verify
powershell -ExecutionPolicy Bypass -File demos/unreal/setup.ps1 -UERoot C:/dev/sdks/UE_5.8 -Out C:/dev/pd-patches-build/audible-review
```

The Wwise SDK must already contain the built custom authoring/runtime plugin.
`--verify` temporarily inserts Wwise Recorder on the main bus, auditions the
actual sound through its auxiliary return, then removes the recorder and saves
the clean project. It writes `WwiseClickDelayCapture.wav` beside the projects.

The Unreal setup creates or updates only this dedicated review project. Its
source and config are checked in here; Unreal assets and compiled demo binaries
are generated outputs. Existing MetaSound graph edits are preserved on reruns.
Close the generated demo before rebuilding it.

`-PdDemoTest` runs the automatic transition and quits after 32 seconds of game
time. The return recording and timeline are in `Saved/BouncedWavFiles` and
`Saved/PD-Demo-Timeline.txt`. `-PdMetaDemoTest` records the MetaSound output and
quits after 12 seconds. `demos/unreal/verify.ps1` runs both renders with game-synchronized offline audio and checks the recordings:

```powershell
powershell -ExecutionPolicy Bypass -File demos/unreal/verify.ps1 -UERoot C:/dev/sdks/UE_5.8 -Project C:/dev/pd-patches-build/audible-review/DelayReview/DelayReview.uproject -WwiseCapture C:/dev/pd-patches-build/audible-review/WwiseClickDelayCapture.wav
```

The offline path disables the audio render scheduler/automatic rendering and advances audio exactly once per fixed game step. These flags are for review checks, not production logic.

The scope is streaming sublevels inside one persistent world. This demonstrates
that the return survives real level/source removal and garbage collection; it
does not claim seamless `OpenLevel` travel between different worlds, Wwise game
integration, or packaged-platform/cooked-game validation.
