# Convoy / Foundry repository split

Verified on Odysseus, Linux x86_64, Intel Core Ultra 9 185H, October 24, 2026.

## Ownership

- **Convoy:** C++17 convolution engine, public API, headers, standalone example,
  CMake package, tests, benchmarks and the original performance records. Its
  Git history continues from HeavyVerb. It requires no graph compiler or host SDK.
- **Foundry:** module adapters, compiler integration, plugin UI, WAV loading,
  host packaging, integration tests and review demos. Convoy and the Pd module
  collection are pinned Git submodules. Module sources are not duplicated here.
- **PD Patches:** reusable Pd source modules and ideation patches. Its README
  links to Foundry for deployment. Existing uncommitted local deployment work
  was copied into Foundry; the original local files were left intact.

The public repositories are `ianshores/convoy`, `ianshores/foundry` and
`ianshores/pd-patches`. Local roots are `~/dev/code/convoy` and
`~/dev/code/foundry`; the old local `heavyverb` path redirects to Convoy for
existing file references. Prior deployment sources remain in Git history and
Foundry, not the current engine source tree.

## Integration contract

`convoy.hpp`, `convoy::Convolver`, and `convoy::convoy` are the current engine
entry points. Installed CMake consumers use `find_package(Convoy CONFIG REQUIRED)`.
Compatibility headers accept the earlier include/namespace spellings.
The rename changes identifiers and repository ownership, not DSP arithmetic.

Foundry's Convoy recipe builds the renamed editor and passes its independently
versioned engine through the Heavy graph adapter. The shared pipeline also
exports Wwise, Unreal Submix and MetaSound sources. Direct C++ embedding works
in the engine; a compiler-free native host deployment backend is future work.

## Validation

| Check | Result |
|---|---|
| Convoy Make suite | Passed reference convolution, FFT scalar/SSE/AVX paths, cutoff, variable/in-place callbacks and zero-allocation checks. |
| Convoy CMake | Seven tests passed. GitHub CI also passed, including fallback and uniform builds. |
| Installed CMake consumer | Built outside the source build and produced expected impulse output `1, 0.5, 0.25`. |
| Full-quality double-precision comparison | Passed at 44.1/48/96kHz; raw results retained. No new performance claim made. |
| Foundry Convoy CLAP/VST3 | Linux binaries built from pinned external engine source. |
| CLAP host checks | Controls, mono/stereo WAVs, resampling, bad-file fallback, state restore and sample-rate changes passed. |
| Sanitizers / callback allocation checks | Passed for WAV loader, full generated graph/runtime and queue. |
| Real earlier plugin state → Convoy | State saved by the installed HeavyVerbDemo CLAP restored and rendered correctly in Convoy. |
| Plugin identity | CLAP ID retained; both VST3 factory class IDs match the earlier build. New display names are Convoy. |
| Native `convoy~` Pd external | Full response and cutoff checks passed; maximum render error 2.24e-8. |
| Generated Convoy graph | 15 stereo reference renders and nine cutoff/restore renders passed; baseline maximum error 7.73e-9. |
| Existing delay pipeline | Nine regression tests and bootstrap-recovery check passed. |

[Raw logs and module pins](validation/repository-split).
Tests ran without opening or interrupting the user's REAPER instance.

## Issues resolved during the split

The common pipeline's stricter CLAP reader rejected an incomplete hand-written
state fixture. The fixture now includes the parameter section and terminator,
and real state produced by the earlier plugin was checked separately.

The first VST3 identity probe queried class metadata before `ModuleEntry` and
crashed inside the earlier plugin. The crash record and framework source were
consistent with an uninitialized metadata object. Calling the required entry
point made the identity comparison pass. This was an isolated test process;
REAPER and user projects were not involved.

GitHub rejected the new Pd module snapshot's private author email. That
unpublished commit was recreated using the account's GitHub no-reply address;
account privacy settings were preserved.

## Scope

Existing Linux plugin identities and the IR state key are preserved. Native Pd
patches in this adapter use `convoy~`; old graph source needs its object name
updated or an explicitly supplied compatibility abstraction. The older binary
filename can be kept when replacing an installed DAW plugin to preserve host
path references. Do not install both builds with the same plugin identity.

No Unreal or Wwise SDK binary was rebuilt in this split. Convoy's SDK exports
need their own build and listening review; the imported delay review records
refer to the earlier validated delay build. This migration did not contact
Cradle or modify its installed projects.
