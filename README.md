<p align="center">
  <img src="assets/icon.ico" alt="Stingray Crash Analyzer" width="128" height="128">
</p>

<h1 align="center">Stingray Crash Analyzer</h1>

<p align="center">
  <a href="https://github.com/ERRORX2/Styngray-crash-analyzer/releases/latest">
    <img alt="Latest Release" src="https://img.shields.io/github/v/release/ERRORX2/Styngray-crash-analyzer?style=flat&label=Latest%20Release&color=58a6ff">
  </a>
  <a href="https://github.com/ERRORX2/Styngray-crash-analyzer/releases">
    <img alt="Total Releases" src="https://img.shields.io/github/downloads/ERRORX2/Styngray-crash-analyzer/total?style=flat&label=Downloads&color=3fb950">
  </a>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-8b949e?style=flat">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-a371f7?style=flat">
</p>

A desktop tool for analyzing `.dmp` minidump files from games built on the **Autodesk Stingray / Bitsquid engine**. Tells you in plain English whether a crash is the engine killing itself, a GPU driver fault, a mod, or a real game bug - and what to try next.

---

<!-- LATEST_RELEASE_START -->
### Latest Release: V2.0.1 (2026-09-27)

- Download: [release_V2.0.1.zip](https://github.com/ERRORX2/Styngray-crash-analyzer/releases/download/V2.0.1/release_V2.0.1.zip)
- All releases: [releases](https://github.com/ERRORX2/Styngray-crash-analyzer/releases)

### Cryptographic Integrity

<details>
<summary>SHA-256 Hashes</summary>

| File | SHA-256 |
|---|---|
| `StingrayAnalyzer.exe` | `549DDD4A6A43FF82D69ACBB346F4C1BB6D186449496EB05ECCCB73FCA3B1AFE4` |
| `crash_patterns.json` | `9E7D123B749BD5ADDEF67A78E5DE692C5AB69CCD1F2C5E6A3941B13550E6096F` |
| `manifest.json` | `C6EC40A60CB14D7BAB7C572AC764D1C680D707F8A569441CA431A2C9B4B85C18` |
| `release_V2.0.1.zip` | `A71AF3457B28B13A0116ECF49E65D1DBF050402B825A1FBDDC2DEF3E1EC8C07F` |

</details>
<!-- LATEST_RELEASE_END -->

---

## Installation

### Windows (prebuilt EXE)

1. Download **[release_v2.0.zip](https://github.com/ERRORX2/Styngray-crash-analyzer/releases/download/v2.0/release_v2.0.zip)** from the [latest release](../../releases/latest).
2. **Extract the ZIP fully** - the `assets/` folder and `crash_patterns.json` must sit next to `StingrayAnalyzer.exe`.
3. Run `StingrayAnalyzer.exe`.

`crash_patterns.json` holds the pattern library and is editable (see [Editing Patterns](#editing-patterns)). The `assets/icon.ico` file is the window icon - without it, the app still runs but shows the default tkinter icon.

### Linux (from source)

Tested on Arch / CachyOS. The only system dependency is `tk`:

```bash
sudo pacman -S git python tk
```

Optional but recommended - enables drag-and-drop of `.dmp` files onto the window:

```bash
pip install tkinterdnd2
```

Then:

```bash
git clone https://github.com/ERRORX2/Styngray-crash-analyzer.git
cd Stynray-crash-analyzer
python stingray_crash_analyzer.py
```

If `tkinterdnd2` is not installed, the app runs normally - drag-and-drop is disabled (noted in the status bar at startup) and the Browse button remains fully functional.

---

## How It Works: The Verdict Banner

Every analysis opens with a pinned verdict banner at the top of the window. This is the answer to the only question that matters: **whose fault is this crash?**

| Verdict | Color | Meaning |
|---|---|---|
| `SUICIDE` | Red | The Stingray engine intentionally killed itself after detecting an internal error. **Not a player-side issue.** |
| `GPU` | Orange | GPU driver crash, DXGI device hang/removal, or a TDR. Update drivers, lower settings, or revert overclocks. |
| `MOD` | Yellow | A mod, proxy DLL, or tampered runtime is the likely cause. Remove mods and retest. |
| `GAME_BUG` | Blue | Real crash inside game code - null deref, bad vtable, use-after-free, etc. Report to devs. |
| `INCONCLUSIVE` | Grey | Dump is too small or the call chain is too short to identify a cause confidently. |

Below the banner, the action panel changes based on the verdict: suicide shows "Open `.log` file", GPU shows "Update GPU drivers", mod shows "Remove mods and retest", and so on. The banner stays visible on every tab.

---

## The 7 Tabs

| Tab | Purpose |
|---|---|
| **Summary** | Crash summary card, crash instruction, mod detection banner, DLL authenticity row, what the engine was doing, active game thread, top-5 call chain, player notes. |
| **Crash Timeline** | 8-card visual chain: verdict → active subsystems → engine state → crash instruction → call chain → register state → environment/mod status → pattern match. |
| **Evidence** | All findings with confidence levels (HIGH/MED/LOW), clickable navigation to the relevant module or thread. |
| **Registers** | Full GPR analysis with x64 calling-convention context (which register holds `this`, which holds arg 1, etc.), XMM0–XMM15 with hex + 4×float32 + 2×float64 views, exception parameters, and automatic screen-resolution detection in register values (17 common resolutions matched). |
| **Threads** | Every thread listed individually with state (crashed, active, waiting, sleeping, suspended) and color-coded purpose pills (Audio, GPU, DirectStorage, Network, Anti-Cheat, Bink, XAudio2, PlayFab, etc.). Full call stack per thread with `[pdata✓]` (confirmed via PE .pdata unwind) or `[heuristic]` (fallback) frame tags. |
| **Modules & DLLs** | All loaded DLLs. Red = crash module, yellow = game-owned, white = Windows system. DLL Verify panel grades the 5 Microsoft C/C++ runtime DLLs as **OK / SUSPICIOUS / LIKELY TAMPERED** (see [DLL Authenticity](#dll-authenticity-verification)). |
| **GPU Hang** | Separate pipeline for DirectX 12 DRED (Device Removed Extended Data) text logs. Decodes all 45 `D3D12_AUTO_BREADCRUMB_OP` queue operations, ranks queues by risk, and suggests feature-specific in-game setting workarounds. |

---

## Stingray Suicide Detection

The Stingray engine intentionally kills itself with an intentional null-pointer write when it detects an internal error. The crash address points at the suicide instruction, **not at the bug that triggered it**. Without proper handling, every engine suicide gets mislabeled as a "null pointer write" - useless for diagnosis.

### How v2.0 detects it

`_is_stingray_suicide()` classifies any `0xC0000005` (access violation) occurring inside `helldivers2.exe` - or any host `.exe` alongside `crs-client.dll` - as an engine suicide, **regardless of instruction bytes**.

This is the correct approach. Earlier versions (v1.3–v1.8) tried to detect the suicide by matching specific instruction byte patterns (`MOV [0x00000000], ESI` = `89 34 25 00 00 00 00`). That approach was structurally broken because Stingray uses multiple suicide instruction shapes - register-based null derefs, vtable calls, offset reads - that byte-pattern matching cannot reliably identify.

### What the analyzer does after classifying a suicide

1. Flags the crash as `SUICIDE` in the verdict banner (red).
2. Looks through the suicide to find what was actually happening - active game threads, their register state, and the subsystem each was executing in.
3. Runs scored subsystem matching against the crash thread's call chain (HIGH confidence if a module is at depth ≤ 4, MED if 2+ hits, LOW for single deep hits) - **not** against every loaded module. This eliminates the v1.x false positive where `dstorage.dll` being loaded matched every dump.
4. Tries to identify the failing subsystem (DirectStorage, Lua, Audio, GPU, Network, Physics, Save/Load, Level Streaming, Animation, UI, Entity, Resource, Shader, or generic).
5. Separates the crash handler (`crs-client.dll`) from meaningful threads - it's a byproduct of the crash, not the cause.

---

## Crash Pattern Library

The tool matches crashes against **61 builtin patterns** (expandable via `crash_patterns.json`). Patterns are grouped by category:

### Engine Suicide (14 patterns)
All 14 Stingray suicide sub-patterns, each matched against the crash thread's call chain (not just loaded modules):

| Pattern | Trigger |
|---|---|
| `SUICIDE_DSTORAGE` | Suicide + DirectStorage in crash chain |
| `SUICIDE_LUA` | Suicide + `lua51.dll` / `lua` in crash chain |
| `SUICIDE_AUDIO` | Suicide + Wwise / FMOD in crash chain, no GPU |
| `SUICIDE_GPU` | Suicide + GPU driver DLL in crash chain |
| `SUICIDE_NETWORK` | Suicide + network DLL in crash chain |
| `SUICIDE_PHYSICS` | Suicide + PhysX in crash chain |
| `SUICIDE_SAVEGAME` | Suicide + save/load subsystem |
| `SUICIDE_LEVEL_STREAMING` | Suicide + level streaming |
| `SUICIDE_ANIMATION` | Suicide + animation subsystem |
| `SUICIDE_UI` | Suicide + UI/HUD subsystem |
| `SUICIDE_ENTITY` | Suicide + entity system |
| `SUICIDE_RESOURCE` | Suicide + resource loading |
| `SUICIDE_SHADER` | Suicide + shader compilation |
| `SUICIDE_GENERIC` | Suicide, subsystem unknown |

### Exception Codes (16 patterns)
| Pattern | Exception Code |
|---|---|
| `NULL_DEREF_READ` / `NEAR_NULL_READ` / `NULL_DEREF_WRITE` | `0xC0000005` (AV, by fault address) |
| `ILLEGAL_INSTR` | `0xC000001D` |
| `PRIVILEGED_INSTR` | `0xC0000096` |
| `INT_DIVIDE_BY_ZERO` / `FLOAT_DIVIDE_BY_ZERO` | `0xC0000094` / `0xC000008C` |
| `INT_OVERFLOW` | `0xC0000095` |
| `FLOAT_INVALID` | `0xC0000093` |
| `ARRAY_BOUNDS` | `0xC000008C` |
| `STACK_OVERFLOW` | `0xC00000FD` |
| `GUARD_PAGE` | `0x80000001` |
| `MISALIGNMENT` | `0xC000009C` |
| `IN_PAGE_ERROR` | `0xC0000006` |
| `INVALID_HANDLE` | `0xC0000008` |
| `NOT_MAPPED` | `0xC0000019` |
| `ACCESS_DENIED` | `0xC0000022` |
| `OUT_OF_MEMORY` | `0xC0000017` |
| `ENTRY_POINT_NOT_FOUND` / `DLL_NOT_FOUND` / `DLL_INIT_FAILED` | `0xC0000139` / `0xC0000135` / `0xC0000142` |
| `ASSERTION_FAILURE` | `0xC0000420` |
| `STACK_BUFFER_OVERRUN` | `0xC0000409` (GS cookie) |
| `HEAP_CORRUPTION` | `0xC0000374` |
| `CPP_EXCEPTION` | `0xE06D7363` |
| `INVALID_CRT_PARAM` | `0xC0000417` |

### Crash Module (10 patterns)
Matched when the crash address lands inside a known module: `ntdll.dll`, `kernel32.dll`, EasyAntiCheat, GameGuard, Bink Video, Steam API, Wwise, FMOD, PhysX, Lua runtime, or the crash reporter itself.

### Mods & DLL Tamper (5 patterns)
| Pattern | Trigger |
|---|---|
| `PROXY_DLL_CRASH` | Proxy DLL injection detected (ReShade, etc.) |
| `MOD_CRASH` | Mod manager path or workshop content detected |
| `RESHADE_DIRECT_CRASH` | Crash inside ReShade DLL |
| `RESHADE_D3D_CORRUPTION` | ReShade D3D interceptor corruption |
| `DLL_TAMPER` / `DLL_MISMATCH` / `DLL_HIJACK` | Tampered/mismatched/hijacked runtime DLL (see [DLL Authenticity](#dll-authenticity-verification)) |

### GPU / DXGI (3 patterns)
| Pattern | Trigger |
|---|---|
| `GPU_DRIVER_CRASH` | Crash address inside GPU driver DLL (`nvwgf2umx`, `amdxc64`, etc.) |
| `DUAL_GPU_DRIVER_CRASH` | Crash with both NVIDIA + Intel GPU drivers loaded |
| `DXGI_DEVICE_LOST` | DXGI removal codes `0x887A0005`–`0x887A0020` (device removed, hung, reset, driver error) |

### Heuristic (1 pattern)
| Pattern | Trigger |
|---|---|
| `POSSIBLE_USE_AFTER_FREE` | Heuristic detection based on register state and call chain shape |

Pattern matching uses **scored evidence** against the crash thread's call chain, not flat module-loaded checks. This eliminates false positives from modules that are loaded but never executing.

---

## Editing Patterns

All patterns live in `crash_patterns.json` next to the EXE. Click **Patterns** in the toolbar to open the built-in editor. Changes take effect on the next dump load - no restart needed.

### Edit a built-in pattern

Find it in `builtin_patterns` by its `id` and change any text field:

```json
{
    "id": "SUICIDE_DSTORAGE",
    "name": "Engine suicide during DirectStorage streaming",
    "player_message": "Your updated message here.",
    "fix": [
        "Updated step 1",
        "Updated step 2"
    ],
    "dev_note": "Updated dev note",
    "confidence": "HIGH",
    "enabled": true
}
```

Set `"enabled": false` to suppress a built-in pattern entirely.

### Add a new pattern

Add to the `patterns` array with a `match` block:

```json
{
    "id": "MY_PATTERN",
    "name": "Short name shown in UI",
    "player_message": "Plain-English explanation for players.",
    "fix": [
        "Step 1",
        "Step 2"
    ],
    "dev_note": "Technical notes for devs",
    "confidence": "MED",
    "match": {
        "ex_code": "0xC0000005",
        "is_suicide": true,
        "active_thread_mod_contains": "lua"
    },
    "enabled": true
}
```

All `match` conditions are AND - every specified condition must be true.

### Match conditions

| Field | Type | Description |
|---|---|---|
| `ex_code` | string | Exception code hex, e.g. `"0xC0000005"` |
| `is_suicide` | bool | Whether `_is_stingray_suicide()` returned true |
| `fault_addr_max` | int | Faulting address must be ≤ this value |
| `fault_addr_min` | int | Faulting address must be ≥ this value |
| `crash_mod_contains` | string | Module the crash landed in must contain this substring |
| `module_loaded` | string | This DLL must be in the module list |
| `module_not_loaded` | string | This DLL must NOT be in the module list |
| `stack_contains` | string | Any thread stack must pass through a module containing this |
| `stack_contains_depth` | int | Restricts `stack_contains` to only the top N frames of a thread's stack - prevents false positives from modules buried deep in background threads |
| `active_thread_mod_contains` | string | Active game thread RIP module must contain this |

Custom patterns are checked **before** built-in ones, so you can override default behavior.

---

## DLL Authenticity Verification

Every dump triggers a verification pass on the 5 Microsoft C/C++ runtime DLLs:

- `MSVCP140.dll` - Visual C++ 2015–2022 C++ Standard Library
- `VCRUNTIME140.dll` - Visual C++ 2015–2022 C Runtime
- `VCRUNTIME140_1.dll` - Visual C++ 2019–2022 Extended C Runtime
- `CONCRT140.dll` - Visual C++ 2015–2022 Concurrency Runtime
- `ucrtbase.dll` - Windows Universal C Runtime

Each DLL gets a color-coded verdict: **OK**, **SUSPICIOUS**, or **LIKELY TAMPERED**, with a breakdown of exactly what failed.

### What gets checked

- **Load path** - `ucrtbase.dll` outside `System32` is immediately flagged as a potential hijack vector.
- **File size** - compared against a reference table spanning VS2015 RTM through VS2022 17.10, covering both x64 and x86 (SysWOW64).
- **PE checksum** - Microsoft runtime DLLs always carry a non-zero checksum. A zeroed checksum means the file was modified outside Microsoft's build system. (Reproducible-build DLLs from VS2017+ use a content hash in the timestamp field - the verifier is aware of this and only flags as forged if **both** the timestamp is implausible AND the checksum is zeroed.)
- **PE timestamp** - cross-referenced against each DLL's known existence window.
- **Cross-DLL version consistency** - all loaded VC++ 140-family DLLs must come from the same VS generation. A partial install (e.g. MSVCP140 from VS2019 + VCRUNTIME140 from VS2022) is flagged.

---

## DRED / GPU Hang Analysis

Separate from the `.dmp` pipeline: the analyzer can parse DirectX 12 DRED (Device Removed Extended Data) text logs.

- **Open GPU Log** button (topbar + landing screen) accepts `_dred.txt` and `.dred.txt` files.
- `parse_dred_log()` extracts the DXGI device-removed reason, every command queue's breadcrumb trail (decoded against the full 45-entry `D3D12_AUTO_BREADCRUMB_OP` enum), render-pass debug labels, and the page-fault address.
- `assess_dred()` picks the most likely culprit queue when a hang involves many incomplete queues, with a HIGH/MED/LOW confidence label based on operation risk (draw calls and compute dispatches rank higher than barriers/clears) and breadcrumb count.
- Per-DXGI-removal-reason explanations with numbered fix steps: `DEVICE_HUNG`, `DEVICE_REMOVED`, `DEVICE_RESET`, `DRIVER_INTERNAL_ERROR`, `INVALID_CALL`.
- Render-pass-aware workaround suggestions - if the hung render pass matches a known feature category (shadows, reflections/cubemaps, ambient occlusion, particles, water), the tool suggests the specific in-game setting to lower as a temporary workaround.

---

## Engine Log Parser

`parse_engine_log()` parses Stingray `.log` files, extracts structured `ERROR` / `FATAL` / `ASSERT` / `CRASH` events, and surfaces the last 20 lines as tail context. Useful for suicides - the engine log often contains the actual error message that triggered the suicide, which the `.dmp` alone can't show.

To capture a Stingray log: right-click the game in Steam → Properties → Launch Options, add `--log-to-file`, then launch and play until it crashes. The log will be in `%APPDATA%\Arrowhead\Helldivers 2\logs`.

---

## Instruction Decoder

The crash instruction at the crash address is disassembled in-place from the dump's memory map. Coverage:

- **Standard x64 opcodes**: `0x8B` (MOV r, r/m), `0x89` (MOV r/m, r), `0xFF` (group), `0xC6`/`0xC7` (MOV imm), etc. - all with full ModRM + SIB + displacement + REX prefix support (`REX.B`/`REX.R`/`REX.X`/`REX.W`), extended register addressing (`r8`–`r15`).
- **AVX/AVX2** via VEX prefixes: `_decode_vex_instruction()` handles 20+ opcodes across both 2-byte (`0xC5`) and 3-byte (`0xC4`) VEX prefixes - `VMOVAPS`/`VMOVUPS`/`VMOVAPD`/`VMOVUPD`, `VMOVDQA`/`VMOVDQU`, `VMOVD`/`VMOVQ`, `VADDPS`/`VADDPD`, `VMULPS`/`VMULPD`, `VANDPS`/`VANDNPS`/`VORPS`/`VXORPS` (+PD variants), `VPCMPEQB`/`VPCMPEQD`, `VPMOVMSKB`, `VBROADCASTSS`/`VBROADCASTPS`, `VPTEST`, `VPACKUSDW`.
- **XMM register extraction**: `XMM0`–`XMM15` (16 × 128-bit) are extracted from the x64 CONTEXT block at offsets `0x1A0`–`0x29F`. Each register is displayed as hex + 4×`float32` + 2×`float64` interpretation.
- **Alignment fault notices**: `VMOVAPS` and `VMOVDQA` instructions include an explicit note that 16/32-byte alignment is required - misalignment (not just null pointers) also causes crashes.

---

## Crash Signature

Every analysis produces an 8-character MD5 crash signature with a verdict prefix, e.g. `SUI-6CF20EFD` or `GPU-3A2B9C44`. The signature is derived from:

```
verdict + crash_module + offset_bucket(4KB) + exception_code
```

Two dumps with the same signature hit the same crash at the same instruction (modulo a 4 KB offset bucket, which accounts for build-specific variations). This is the foundation for a future community-searchable crash database - if you see the same signature in someone else's report, you're hitting the same bug.

---

## WinDbg Integration

When you click a Root Cause finding that links to the Modules tab, the hex dump panel shows copy-paste WinDbg commands pre-filled with the correct addresses and thread IDs from the dump:

```
!analyze -v
~#s                    # select crash thread
kb                     # stack trace
u rip L10              # disassemble 16 instructions at crash
dps @rsp L40           # walk stack as symbols+addresses
```

Note: Helldivers 2 and most retail Stingray games have no public PDBs. The commands still work and will show raw addresses, register state, and disassembly - the tool notes this and explains what you can and cannot see without symbols.

---

## Files

| File | Purpose |
|---|---|
| `StingrayAnalyzer.exe` | Main application |
| `crash_patterns.json` | Editable pattern library (61 builtin + your custom patterns) |
| `assets/icon.ico` | Window icon (Windows) |
| `assets/icon.png` | Logo (used in this README) |
| `manifest.json` | Release manifest (hashes, version, build info) |

`crash_patterns.json` must stay in the same folder as the EXE. The `assets/` folder must also be next to the EXE for the window icon to load (the app falls back to the default tkinter icon if it's missing).

---

## Building from Source

**Requirements**: Python 3.9+, `tkinter` (bundled with standard Python on Windows; install `python-tk` on Linux).

**Optional**: `pip install tkinterdnd2` - enables drag-and-drop of `.dmp` files onto the window. Without it, the app runs normally (drag-and-drop is disabled, Browse button still works).

```bash
git clone https://github.com/ERRORX2/Styngray-crash-analyzer.git
cd Stynray-crash-analyzer
python stingray_crash_analyzer.py
```

### Build the EXE yourself

```bash
pip install pyinstaller tkinterdnd2
pyinstaller --onefile --noconsole --name StingrayAnalyzer \
    --add-data "assets;assets" \
    --add-data "crash_patterns.json;." \
    stingray_crash_analyzer.py
```

The CI workflow (`.github/workflows/build.yml`) does this automatically on every push to master and on release tags.

### Run the test suite

```bash
pip install pytest
python -m pytest test_stingray_analyzer.py -v
```

30 tests cover the instruction decoder (MOV read/write/SIB/REX, suicide patterns, AVX), Stingray suicide detection, root cause analysis, pattern matching, DLL verify, verdict engine, engine log parser, and null register filtering.

### Internal debugger

Press `Ctrl+F8` inside the running app to open the internal feature-test debugger: 82 scenarios across 8 categories (Exceptions, Suicides, GPU/D3D, Mods & DLLs, Crash Modules, Baselines, Edge Cases) × 16 test sections, 5,823 checks total.

---

## Known Limitations

- **`[heuristic]` stack frames**: When a module has no `.pdata` exception directory (rare for game DLLs, common for some anti-cheat modules), stack walking falls back to scanning RSP for return addresses that land inside known modules. These frames are tagged `[heuristic]` rather than `[pdata✓]`. Subsystem identification is still accurate.
- **No public PDBs**: Helldivers 2 and most retail Stingray games ship without symbols. WinDbg commands from the tool will show raw addresses and disassembly, not function names.
- **Crash signature is build-specific**: The signature includes a 4 KB offset bucket - two dumps from different game versions hitting the "same" bug will have different signatures. Always confirm the game version when comparing signatures across reports.
- **Memory at the crash address is only available if the dump was created with stack memory capture** (standard for Stingray minidumps). Full-memory dumps give more detail in the hex view but are 10–50× larger.
- **Thread state detection uses ntdll syscall offsets** based on specific Windows versions. The tool degrades gracefully - threads will show as `WAITING` rather than the specific wait type (`WrQueue`, `WrUserRequest`, etc.) if the offset doesn't match.

---

## License

MIT License - Developed for the hardware enthusiast and troubleshooting community. Pull requests welcome.
