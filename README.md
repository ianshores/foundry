# Foundry

**Build DSP modules into tools for the audio pipeline.**

Foundry owns adapters, compiler integration, plugin interfaces, packaging, and
host verification. DSP algorithms live in independent repositories, consumed
here at pinned revisions. A module can be used directly without Foundry; its
deployment recipe selects the compiler and host adapters it needs.

## Layout

| Location | Responsibility |
|---|---|
| `modules/convoy` | Pinned [Convoy](https://github.com/ianshores/convoy) engine checkout |
| `modules/pd-patches` | Pinned [Pd modules](https://github.com/ianshores/pd-patches) checkout |
| `projects/` | Plugin metadata, parameters, source locations and target recipes |
| `adapters/convoy/` | Convoy's Pd external, optional Heavy bridge, WAV loader and plugin editor |
| `pipeline/` | Shared build orchestration and host-wrapper templates |
| `tests/`, `demos/` | Deployment checks and host review projects |
| `build/` | Generated sources and binaries; ignored by Git |

Convoy's C++ engine has no Heavy dependency. The current graph deployment route
uses pinned hvcc and DPF; supporting another compiler or a direct native host
adapter belongs here. A new module does not need to move its algorithm into
this repository.

## Get started

```sh
git clone --recurse-submodules https://github.com/ianshores/foundry.git
cd foundry
python3 pipeline/bootstrap.py
python3 foundry.py doctor
python3 foundry.py export convoy
python3 foundry.py build convoy --target reaper
```

Bootstrap prepares a local Python/compiler environment and pinned DPF checkout.
It does not install operating-system packages or proprietary SDKs. Linux needs
a C++17 compiler, make and pkg-config. Convoy's WAV editor also needs libsndfile,
libsamplerate, X11 and OpenGL development packages (Debian/Ubuntu:
`libsndfile1-dev libsamplerate0-dev libx11-dev libgl1-mesa-dev`).

Convoy outputs:

```text
build/Convoy/generated/bin/Convoy.clap
build/Convoy/generated/bin/Convoy.vst3/
```

Close your host before replacing an installed binary. Install one format in
its plugin search path and rescan. The editor loads mono/stereo WAVs, remembers
the selected file path and exposes the optional tail cutoff. The effect is wet
only. [Convoy adapter and auditioning guide](adapters/convoy/README.md).

The existing Pd stereo-delay recipe uses the same shared pipeline:

```sh
python3 foundry.py export stereo-delay
python3 foundry.py build stereo-delay --target reaper
python3 tests/test_pipeline.py
```

## Targets and readiness

| Target | Convoy | Stereo delay |
|---|---|---|
| CLAP / VST3 | Linux binaries built; CLAP audio, state and loader checks | Linux build and headless checks; earlier REAPER review recorded |
| Native Pd / standalone PlugData | `convoy~` external; headless Pd render checks | Original Pd abstraction |
| Wwise | Source generated; SDK build/listening still required | Earlier Windows authoring/runtime review recorded |
| Unreal Submix / MetaSound | Source generated; SDK build/listening still required | Earlier UE 5.8.4 review and transition demos recorded |

Recorded SDK reviews describe the earlier delay build, not a new binary built
from this checkout. Rebuild and review against your chosen SDK versions before
shipping. [Detailed build/SDK guide](pipeline/README.md) and
[host demos](demos/README.md). Unreal/Wwise SDKs and proprietary platform tools
are local dependencies and are not distributed here.

## Independent module development

1. Develop and test DSP in its own repository. Convoy exposes `convoy.hpp`,
   `convoy::Convolver`, and `convoy::convoy` for direct C++ integration.
2. Add a pinned checkout under `modules/` and a recipe under `projects/`.
3. Implement a thin adapter for the module's API or supported graph compiler.
4. Export, build and verify each target here. Commit the updated module pin
   together with adapter changes when promoting a new engine revision.

Git submodules record exact source commits. Generated build records also hash
inputs, and builds reject changed sources until re-exported. For local Convoy
experiments, set `CONVOY_ROOT=/absolute/path/to/convoy`; the build record hashes
that checkout's headers. Keep that environment variable unset for pinned builds.

The manifest-driven shared exporter currently handles stereo float-parameter
Pd effects and the Convoy adapter. Direct C++ deployment without a graph
compiler is a future adapter, not an automatic capability for every module.

## Checks

```sh
python3 tests/test_bootstrap.py
python3 tests/test_pipeline.py
python3 adapters/convoy/tools/test_wav_selector.py build/Convoy/generated --dpf .toolchain/dpf
python3 adapters/convoy/tools/test_wav_selector.py build/Convoy/generated --dpf .toolchain/dpf --sanitize
```

Run the appropriate export/build first. Core algorithm tests and benchmarks
belong to the module repository; these checks exercise its deployment.
[Repository split and verification](docs/repository-split.md).

## License and provenance

Original Foundry code is [MIT licensed](LICENSE). Imported Convoy adapter code
comes from `ianshores/heavyverb` commit `19d19c6`; the engine continues in
`ianshores/convoy` with its existing history. The Pd deployment tools and delay
review records were developed in the separate PD Patches workspace.

Compiler-generated code, DPF, file-loading libraries and host SDKs retain their
own notices and terms. Keep those notices with distributions. Historical
reports preserve their original names, source paths and build identities.
