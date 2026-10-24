# Foundry build and SDK guide

A project manifest and a shared Pd effect produce four targets:

| Target | Output | Audio host |
| --- | --- | --- |
| `reaper` | CLAP + VST3 | REAPER or another compatible DAW |
| `wwise` | Wwise authoring/runtime C++ project | Wwise, including its Unreal integration |
| `unreal-submix` | Native Unreal Submix Effect preset | Unreal Audio Mixer |
| `metasound` | Stereo MetaSound node | Unreal MetaSound graph |

The two Unreal targets share a single generated runtime plugin when exported together. All targets share the Pd implementation and manifest parameters. The first project, `stereo-delay`, wraps `modules/pd-patches/modules/lab-delay~.pd`; edits to that module flow into every export.

The public Convoy module is a pinned Git submodule. The private Pd module
collection is optional: run `python3 pipeline/fetch_module.py pd-patches` with
repository access before using the delay recipe. Clone Foundry recursively or run
`git submodule update --init --recursive` before exporting. The Convoy recipe
uses `adapters/convoy` and the independent `modules/convoy` engine.

## First build

Run these commands from the repository root. Use `python` instead of `python3` on Windows if appropriate.

```sh
python3 pipeline/bootstrap.py
python3 pipeline/pdplugins.py doctor
python3 pipeline/fetch_module.py pd-patches
python3 pipeline/pdplugins.py export stereo-delay
python3 pipeline/pdplugins.py build stereo-delay --target reaper
python3 tests/test_pipeline.py
```

Bootstrap installs the exact Python dependencies in `pipeline/requirements.lock` into `.toolchain/venv`, then checks out the DPF commit pinned in `pipeline/toolchain.json`. It does not install system packages. You need Python 3.10+ with venv/pip support, Git, make, and a native C/C++ compiler. Linux builds were verified here with GCC; Windows DAW builds use a compatible GNU make/MinGW toolchain. The Unreal and Wwise targets use their own platform build tools.

The REAPER build outputs are:

```text
build/StereoDelay/generated/bin/StereoDelay.clap
build/StereoDelay/generated/bin/StereoDelay.vst3/
```

Copy the relevant plugin into your DAW's plugin search path and rescan. The headless plugins expose their parameters through the host's generic control interface. PlugData's graph layout is not the exported plugin UI. Plugin installation is intentionally separate from building.

## SDK-dependent builds

Install the **latest UE5 version supported by your selected Wwise Unreal Integration**, using the compatibility list in Wwise Launcher / that integration's release notes. Use the matching Wwise SDK and authoring version. The pipeline does not guess a compatible pair from the newest engine version, and no claim of compatibility is inferred from a successful source export.

Set `UE_ROOT` and `WWISEROOT`, or copy `pipeline/local-sdk.example.json` to the repository root as `local-sdk.json` and set the paths there. `UE_ROOT` must contain `Engine/Build/Build.version`; `WWISEROOT` is the Wwise installation containing both `SDK` and `Scripts`.

```sh
python3 pipeline/pdplugins.py doctor --strict
python3 pipeline/pdplugins.py build stereo-delay --target unreal-submix --platforms Win64
python3 pipeline/pdplugins.py build stereo-delay --target wwise --wwise-platform Windows_vc170
```

The first Unreal command packages both the Submix Effect and MetaSound node if both were exported. Use `--platforms Linux` when building for Linux, and `--wwise-platform Linux` for Wwise Linux runtime libraries. On Windows the Wwise command builds both the authoring plugin and the selected runtime library. It selects the compiler from the platform suffix (for example, `Windows_vc170` uses Visual Studio 2022); `--wwise-toolset` can override that selection. Development builds disable the SDK's certificate signing steps; use `--wwise-codesign` when a signing certificate is already configured.

Run Windows authoring builds with the Visual Studio components required by your Wwise SDK, including C++ ATL/MFC. The Wwise build invokes Audiokinetic's `Scripts/Build/Plugins/wp.py`; Unreal builds invoke `RunUAT BuildPlugin`. Wwise's tool may place compiled libraries in its SDK directories, as described in its build documentation. These SDK tools and licensed platform SDKs are not downloaded by bootstrap.

Build every exported target with:

```sh
python3 pipeline/pdplugins.py build stereo-delay --target all
```

Each target is attempted independently. Missing SDKs produce `not-built` entries in `build/<Name>/target-status.json` and a nonzero command exit; they do not turn generated source into a reported binary success. `doctor` prints installed SDK versions, but compatibility with the Wwise integration still needs confirmation in its release notes. SDK paths remain local and are ignored by Git.

## Generated sources

```text
build/<Name>/
  entry.pd                       generated stereo wrapper
  metadata.json                  compiler target settings
  compiler-results.json          structured Heavy diagnostics
  build-info.json                source hashes + toolchain identity
  target-status.json             actual target build results
  generated/c/                   shared C/C++ DSP
  generated/plugin/source/       DPF CLAP/VST3 source
  generated/wwise/               Wwise SDK project
  unreal/Pd<Name>/               Unreal runtime plugin source
  packages/Pd<Name>/             Unreal packaged binaries, after an SDK build
```

Exports recreate generated sources, reset previous build status, and preserve your source patches. Re-export before rebuilding after a source or pipeline edit; the build command checks the recorded source hashes. Output paths used by make/SDK tools should not contain spaces.

## New effects

```sh
python3 foundry.py init MyEffect --patch /path/to/my-module/effect.pd
```

This creates only `projects/myeffect/plugin.json`, pointing to the external module. Edit the recipe parameters to match the patch. Keep development of the DSP in that module repository, then export it:

```sh
python3 pipeline/pdplugins.py export myeffect
python3 pipeline/pdplugins.py build myeffect --target reaper
```

The abstraction contract is **left audio input, right audio input, selector-message input**, followed by **left/right audio outputs**. Add float parameters to `plugin.json`, with a unique `name`, a Pd `selector`, and finite `min`, `max`, and `default` values. The pipeline generates named `@hv_param` receivers and routes their values into the abstraction's control inlet. Those parameters become DAW controls, Wwise RTPC-capable properties, Unreal preset fields, and MetaSound float pins.

You can instead set `patch` to a project-relative top-level `.pd` file and omit `abstraction`. That patch must provide `[adc~ 1 2]`, `[dac~ 1 2]`, and its own matching `[r parameter_name @hv_param min max default]` declarations. The exporter rejects mismatched channel counts and missing parameter declarations.

This version handles **stereo effects with float parameters**, not arbitrary Pd GUI objects, source instruments, MIDI interfaces, surround effects, or dynamic patching. Use Heavy-compatible objects; unsupported objects fail at export with diagnostics. Public project names are alphanumeric; parameter names are lowercase ASCII identifiers. Give every distributed plugin its own DAW IDs and Wwise plugin ID. Heavy's generated Wwise Company ID remains its development default; use the company ID assigned for your distribution before shipping.

## Unreal usage

Copy `build/<Name>/unreal/Pd<Name>` into your project's `Plugins` folder and rebuild, or install the package produced by RunUAT. The plugin has no Wwise dependency: its Submix Effect and MetaSound node process Unreal audio; the Wwise target processes Wwise audio separately.

For a shared delay return, create a **stereo** Sound Submix, add the generated preset, set `wet` to **1**, and route sound sends into it. Other submix channel counts bypass unchanged. Change settings through the preset's Blueprint-callable `SetSettings`; Unreal queues the update to the audio effect. Parameter changes preserve delay state. Replacing the effect or resetting a MetaSound clears it.

A persistent Game Instance Subsystem can hold references and coordinate transition sends and fades. Keep the same effect instance and audio device running, keep the return processing its tail, and test actual map travel. Merely generating a Submix Effect does not implement or guarantee cross-level persistence. MetaSound nodes likewise require their parent graph to remain active.

## Wwise usage and tails

Build/install the authoring and runtime parts using the SDK matching your Wwise integration. Add the effect to a **stereo Auxiliary Bus**, set its wet mix to 1, and use auxiliary sends plus RTPCs to control it. Keep the return and required banks available across transitions.

The exporter adds bounded tail accounting to Heavy's generic effect wrapper so processing can continue after input ends. `max_tail_seconds` in the manifest caps this duration. The delay example uses 140 seconds, enough for repeated 2-second taps at feedback 0.9 to fall below roughly -60 dB. Lower it for a shorter budget; this is a fixed upper bound, not silence detection or an infinite freeze. A standalone counter test checks partial final buffers and tail termination. The Windows SDK callback test exercises the actual wrapper, including reset, instance isolation, and partial-buffer tail termination at 44.1/48/96 kHz.

## Verification

The automated suite compiles the shared DSP and the Unreal audio-layout adapter, checks echo timing/feedback at 44.1/48/96 kHz, compares planar and interleaved audio and odd block lengths, tests the Wwise tail counter, and loads/renders the actual Linux CLAP plugin. It also loads the Linux VST3 factory. On Windows, run the suite from an x64 Visual Studio developer command prompt; it uses MSVC and skips the Linux plugin-host checks. A separate setup recovery test verifies an interrupted initial dependency checkout. These are not REAPER UI, Wwise authoring, Unreal Header Tool, or map-travel tests.

`.github/workflows/pd-plugins.yml` runs the Linux compiler and audio checks and saves generated sources and DAW binaries as artifacts. Unreal and Wwise binary validation require runners with the matching installed SDKs; the Linux CI runner has neither SDK. The Windows SDK review is recorded separately below.

Generated Heavy/DPF sources retain their upstream notices. Include required runtime notices and apply your project/distribution licensing when packaging. SDK and engine distribution terms remain those of their respective vendors.

## References

- [Heavy Wwise exporter and SDK build commands](https://wasted-audio.github.io/hvcc/latest/generators/wwise/)
- [Heavy DPF exporter](https://wasted-audio.github.io/hvcc/latest/generators/dpf/)
- [Heavy supported objects](https://wasted-audio.github.io/hvcc/latest/reference/objects/supported/)
- [Unreal Submix Effect interface](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/Sound/FSoundEffectSubmix)
- [Unreal MetaSound operator interface](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MetasoundGraphCore/IOperator)
- [Wwise effect processing and tails](https://www.audiokinetic.com/en/public-library/2024.1.7_8863/?id=soundengine_plugins_effects.html&source=SDK)

## Recorded delay review: October 21, 2026

The first end-to-end review is recorded in `pipeline/runs/2026-10-21-stereo-delay-review.json`. Both Linux formats were loaded and rendered in REAPER 7.82, with the expected left/right timing and feedback. The local regression suite passed all nine checks.

The review fixed the CLAP saved-state reader's acceptance of incomplete data and enabled Heavy's scoped handling of extremely small floating-point values. The DPF state-reader fix is a checked, reproducible patch applied only to the generated dependency copy, leaving the pinned checkout untouched. The broader CLAP validator still reports a denormal timing warning; an isolated audio-only benchmark measured 1.03x and verified that host floating-point settings were restored. That warning is retained in the review record rather than hidden.

The real-REAPER check runs on its own virtual display and uses a private settings folder:

```sh
python3 tests/reaper_host.py --reaper /path/to/reaper --xvfb /path/to/Xvfb
```

There is no fallback to the desktop display. It creates a small test recording, exercises normalized controls in CLAP and VST3, renders both projects, and checks the resulting echoes. REAPER and Xvfb are local test tools, not bundled into the plugin package. The Windows SDK build and review are recorded in `pipeline/runs/2026-10-21-cradle-setup.json`.


## Windows SDK review on Cradle

The validated SDK pair is Unreal Engine 5.8.4 and Wwise 2025.1.12.9287, with Wwise Unreal Integration 2025.1.12.4547 for UE 5.8. Audiokinetic’s [release notes](https://www.audiokinetic.com/en/library/2025.1.12_9287/?source=UE4&id=releasenotes_2025_1_12.html) explicitly support and test UE 5.8; the 2026 branch was still beta at this review. Visual Studio 2022 17.14, MSVC 14.44, and Windows SDK 10.0.26100 were installed. The Unreal generator uses C++20 and UE 5.8’s module-level MetaSound registration API.

Run the Wwise SDK and headless authoring checks from an x64 Visual Studio developer prompt after building the Wwise target:

```sh
python tests/wwise_host.py --wwise-root C:/dev/sdks/Wwise2025.1.12.9287
```

This compiles a callback fixture against the actual generated runtime library, checks timing, feedback, reset, instance isolation and bounded tails at three sample rates, then starts a private WwiseConsole API server on a temporary loopback port. It verifies plugin registration and all four saved preset controls, then stops its own server. Existing authoring sessions and audio devices are left alone. This does not verify game routing or persistence across level changes.


The Unreal host check creates a fresh project on every run, loads the packaged plugin through `UnrealEditor-Cmd`, verifies the Submix settings, and builds a stereo MetaSound example using the native delay node:

```sh
python tests/unreal_host.py --ue-root C:/dev/sdks/UE_5.8
```

Its result file identifies the new review project and log. The project contains a wet-only Submix preset and a quiet sine-through-delay MetaSound with four exposed controls. The check uses a null renderer and disables audio devices; listening and game-level transition routing remain manual review tasks. Unreal reports a MetaSound presave cache warning in this audio-disabled commandlet mode; the graph and assets are saved and the commandlet succeeds.
