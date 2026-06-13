# Stingray Crash Analyzer

A desktop tool for analyzing `.dmp` minidump files from games built on the **Autodesk Stingray / Bitsquid engine**.

---

<!-- LATEST_RELEASE_START -->
### Latest Release: v1.3 (2026-06-13)

- Download: [release_release_v1.3.zip](https://github.com/ERRORX2/Styngray-crash-analyzer/releases/download/v1.3/release_v1.3.zip)

### Integrity

- EXE SHA256: DE45550F5D84F3F073B57090F3EB501183159E15946D103567CCAEDB107E1CEC
- crash_patterns.json SHA256: 8D9A46521C669C8012D0BC812C7318B616042A132946A90FBEF91D0AAC5F2108
- Manifest SHA256: A4D4B71059BACE6337F4C2CD8B1E6457ADF743EDD2823ADBAF6E360EEE9733A7
- ZIP SHA256: 490CE5407D6127C4199DA461F0279D158147A4C5EA72D6392C0702543B391CAC
<!-- LATEST_RELEASE_END -->

---

## Download

Download the latest `release_vX.X.zip` from the [Releases](../../releases) page. Unzip and run `StingrayAnalyzer.exe`. Keep `crash_patterns.json` in the same folder.

---

## Features

**Simple View** - The first thing you see. Plain English.
- Identifies known crash patterns automatically
- Tells the player exactly what to try
- Detects mods that may have caused the crash
- Shows which subsystems were active at crash time

**Root Cause tab** - For developers.
- Distinguishes engine suicide (false flag) from real crashes
- Decodes the actual CPU instruction at the crash address
- Identifies active game threads at crash time with register state
- Clickable findings navigate to the relevant module or thread

**Threads tab** - Simulates `~*k` from WinDbg.
- Every thread listed individually with its state (crashed, active, waiting, sleeping, suspended)
- Full heuristic call stack per thread with subsystem annotations
- Recognises crash handlers (crs-client.dll etc.) and flags them as byproducts, not causes

**Modules tab** - All loaded DLLs.
- Red = module the crash address landed in
- Yellow = game-owned DLLs
- White = Windows system DLLs
- Click a Root Cause finding to jump here and see the hex dump of the crash address

**Quick Hints tab** - Only fires when the crash address actually landed inside a subsystem module. No noise from just having a DLL loaded.

**Overview tab** - Raw parsed dump data.

---

## False Flag Detection

Stingray uses `MOV [0x00000000], ESI` (opcode `89 34 25 00 00 00 00`) to intentionally kill itself when it detects an internal error. This is **not** the root cause - it is a deliberate suicide mechanism.

The analyzer:
- Decodes the exact bytes at the crash address to detect this pattern
- Flags it clearly as a false flag in the Overview, Root Cause, and Simple View tabs
- Looks through the suicide to find what was actually happening (active threads, stack frames, subsystems)
- Separates the crash handler (crs-client.dll) from meaningful threads

---

## Crash Pattern Library

The tool matches crashes against a library of known patterns and tells players exactly what to do. Built-in patterns cover:

| Pattern | Detection method |
|---|---|
| Engine suicide - DirectStorage | Confirmed suicide instruction + dstorage on any thread stack |
| Engine suicide - Lua scripting | Confirmed suicide instruction + lua on any thread stack |
| Engine suicide - Audio | Confirmed suicide instruction + wwise/fmod on stack, no GPU driver present |
| Engine suicide - GPU rendering | Confirmed suicide instruction + exact GPU driver DLL on any thread stack |
| Engine suicide - generic | Confirmed suicide instruction, subsystem unknown |
| GPU driver crash | Crash address inside exact GPU driver DLL (amdxc64, nvwgf2umx, etc.) |
| DXGI device lost / hung | DXGI error exception codes (0x887A0005-0x887A0020) |
| Stack overflow | Exception code 0xC00000FD |
| Heap corruption | Exception code 0xC0000374 |
| Mod crash | HIGH confidence mod detection (workshop/mod manager path) |
| Unhandled C++ exception | Exception code 0xE06D7363 |

Pattern matching uses full stack walks, not just the thread RIP, so subsystems that are waiting in ntdll are still detected.

---

## Editing Patterns

All patterns live in `crash_patterns.json` next to the exe. Click **Patterns** in the toolbar to open the built-in editor. Changes take effect on the next dump load - no restart needed.

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
| `ex_code` | string | Exception code hex e.g. `"0xC0000005"` |
| `is_suicide` | bool | Whether the instruction is the engine suicide pattern |
| `fault_addr_max` | int | Faulting address must be <= this value |
| `fault_addr_min` | int | Faulting address must be >= this value |
| `crash_mod_contains` | string | Module the crash landed in must contain this |
| `module_loaded` | string | This DLL must be in the module list |
| `module_not_loaded` | string | This DLL must NOT be in the module list |
| `stack_contains` | string | Any thread stack must pass through a module containing this |
| `active_thread_mod_contains` | string | Active game thread RIP module must contain this |

Custom patterns are checked before built-in ones.

---

## WinDbg Integration

When you click a Root Cause finding that links to the Modules tab, the hex dump panel shows copy-paste WinDbg commands pre-filled with the correct addresses and thread IDs from the dump.

Note: Helldivers 2 and most retail Stingray games have no public PDBs. The commands still work and will show raw addresses, register state, and disassembly - the tool notes this and explains what you can and cannot see without symbols.

---

## Files

| File | Purpose |
|---|---|
| `StingrayAnalyzer.exe` | Main application |
| `crash_patterns.json` | Editable pattern library (built-in + custom patterns) |

---

## Building from Source

Requirements: Python 3.9+, tkinter (included with standard Python on Windows), no pip installs needed.

```
python stingray_crash_analyzer.py
```

To build the exe yourself:

```
pip install pyinstaller
pyinstaller --onefile --noconsole --name StingrayAnalyzer stingray_crash_analyzer.py
```

The CI workflow (`.github/workflows/build.yml`) does this automatically on every push to master and on release tags.

---

## Known Limitations

- Stack walking is heuristic (scanning RSP for return addresses). Without unwind tables it may include false frames or miss frames in optimized code. It is accurate enough for subsystem identification.
- Module name detection for game install root uses Steam path conventions. Non-Steam installs may not detect mods correctly.
- ntdll syscall offsets used for thread state detection are based on a specific Windows version. They degrade gracefully - threads will show as WAITING rather than the specific wait type if the offset does not match.
- Memory at the crash address is only available if the dump was created with stack memory capture (standard for Stingray). Full memory dumps give more detail in the hex view.

---

## License

MIT License - Developed for the hardware enthusiast and troubleshooting community.



