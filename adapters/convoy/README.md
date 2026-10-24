# Convoy deployment adapter

This directory adapts the independently versioned Convoy engine to Pd and
plugin hosts. The DSP implementation comes from `modules/convoy/include`.

## DAW effect

From the Foundry repository root:

```sh
python3 foundry.py export convoy
python3 foundry.py build convoy --target reaper
```

The CLAP/VST3 editor displays **Convoy**, by **Ian Shores**. Use **Load WAV…**
to audition an IR and **Use demo IR** to restore the synthetic Pd response.
The output is wet only; place it on an effects return or blend it in the host.

The loader accepts mono/stereo WAVs up to 30 seconds at 8–384kHz. Mono supplies
both channels; stereo channels are independent. It resamples to the session
rate using sinc interpolation and source-rate/session-rate coefficient scaling.
There is no automatic peak normalization. Loading and graph construction run
on a worker, followed by latency priming and a 50ms crossfade. Switching briefly
runs two graphs; the old tail ends at the end of that fade.

Project state stores the last successfully loaded file path, not the WAV audio.
Wait for **WAV ready** before saving and keep that file available. Failed loads
leave the current response active. A missing file in a fresh instance leaves
the synthetic demo response active and displays an error.

The existing CLAP ID `org.heavyverb.demo`, numeric plugin identity, and cutoff
parameter index/symbol are retained for saved sessions. Install the new build
as a replacement, not alongside the previous build with the same identity.
Old binary filenames can be retained when a host's existing project refers
to them. The user-facing name is Convoy.

## Pd and standalone PlugData

```sh
make -C adapters/convoy pd PD_INCLUDE_DIR=/path/to/pure-data/src
```

Open `adapters/convoy/examples/click-demo.pd` in standalone PlugData, enable DSP,
and start the short noise bursts. They reveal the convolution response. This
preview needs a PlugData build that supports custom Pd externals.

`[convoy~ array-name 256]` uses a saved array and a 256-sample partition. An
optional third argument selects the IR channel for exported stereo hosts:
`0` for left, `1` for right. The native Pd preview uses the specified array.
Disable/re-enable DSP after editing that array. It does not resample the array.

`pd/export/convoy~.pd` is a compiler shim; keep it out of the preview search path.
Saved, finite, nonempty arrays are required for export. Heavy is scalar; the
Convoy core performs its own FFT/vectorization.

## SDK hosts

`foundry.py export convoy` generates Wwise, Unreal Submix and MetaSound sources
alongside DAW sources. Build them with Foundry's SDK commands and review them
against real hosts. Convoy's SDK targets have not been binary-validated in this
split. The WAV selector is a DAW host feature; the generated SDK graph currently
uses the saved synthetic IR. The prior delay host demos remain separate.

The [earlier WAV-selector report](docs/ir-selector/README.md) records the original
implementation under its earlier name. Current split checks are in
[the Foundry verification record](../../docs/repository-split.md).
