import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False
import threading
import json
import re
import struct
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

BG        = "#0e1117"
BG2       = "#161b22"
BG3       = "#1c2333"
BORDER    = "#30363d"
ACCENT    = "#e85d04"
ACCENT2   = "#faa307"
TEXT      = "#e6edf3"
TEXT_DIM  = "#8b949e"
GREEN     = "#3fb950"
RED       = "#f85149"
YELLOW    = "#d29922"
PURPLE    = "#a371f7"
CARD_HOVER = "#1e2736"
MONO      = "Consolas" if sys.platform == "win32" else "Courier New"
UI_FONT   = "Segoe UI" if sys.platform == "win32" else "SF Pro Display"
UI_MONO   = MONO

def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / Path(*parts)



DXGI_REMOVAL_REASONS = {
    "0x887A0005": ("DXGI_ERROR_DEVICE_REMOVED",
                   "The GPU device was physically removed or powered off, or a driver upgrade "
                   "was installed that required a reboot, or the GPU reset itself due to overheating "
                   "or hardware instability. DRED breadcrumbs record what the GPU was doing just "
                   "before it disappeared.",
                   "1) Update to the latest GPU driver from NVIDIA/AMD/Intel directly (not just Windows "
                   "Update) and reboot afterward - a pending driver install can trigger this. "
                   "2) Check GPU temperatures under load (HWiNFO, GPU-Z) - if the card is thermal-throttling "
                   "or shutting off, clean dust from the cooler/case and check fan curves. "
                   "3) If recently changed, reseat the GPU and check the power connectors are fully seated - "
                   "intermittent power delivery can cause the OS to think the device disappeared. "
                   "4) Run a GPU stress test (FurMark, OCCT) briefly to see if the same removal reproduces "
                   "outside the game - if so, this is a hardware/driver issue, not a game bug."),
    "0x887A0006": ("DXGI_ERROR_DEVICE_HUNG",
                   "The GPU did not respond to a command within Windows' TDR (Timeout Detection and "
                   "Recovery) timeout period - usually 2 seconds. This is the most common GPU crash "
                   "cause and typically means a shader entered an infinite or very long loop, a draw "
                   "call deadlocked, or the driver got stuck waiting on a GPU fence. "
                   "DRED breadcrumbs show the last GPU commands issued before the hang.",
                   "1) Update GPU drivers to the latest version - many DEVICE_HUNG cases are fixed by "
                   "driver updates addressing specific shader compiler or scheduling bugs. "
                   "2) Lower graphics settings (especially ray tracing, shadow quality, or any setting tied "
                   "to the render pass named in the breadcrumb trace below) - if the hang stops, that "
                   "feature's shader is the likely culprit. "
                   "3) Disable GPU overclocks/undervolts (including factory OC profiles in vendor software) "
                   "and test on stock clocks - an unstable overclock causing a hang under specific shader "
                   "workloads is common. "
                   "4) If this reproduces in one specific location/scene, that's valuable - report the "
                   "render pass name and location to the developers along with this DRED log. "
                   "5) Verify the TDR delay hasn't been manually shortened in the registry "
                   "(TdrDelay value under HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers) - if "
                   "set below the 2-second default, legitimate long-but-not-infinite shaders may be killed "
                   "prematurely."),
    "0x887A0007": ("DXGI_ERROR_DEVICE_RESET",
                   "The GPU was reset (not removed) - Windows' TDR recovered from an earlier hang "
                   "or another process caused a GPU reset. Breadcrumb data may be from after the reset "
                   "and should be interpreted with caution.",
                   "1) Treat this the same as DEVICE_HUNG (see above) - a reset is TDR's recovery action "
                   "after detecting a hang, so the same fixes apply: update drivers, lower settings tied to "
                   "the breadcrumb render pass, and check for unstable overclocks. "
                   "2) Check Windows Event Viewer (Application and System logs) around the crash timestamp "
                   "for additional driver-reset events from other applications - if resets are happening "
                   "outside this game too, the issue is system-wide, not game-specific."),
    "0x887A0020": ("DXGI_ERROR_DRIVER_INTERNAL_ERROR",
                   "The GPU driver itself hit an internal bug and crashed. This is usually a driver-side "
                   "bug rather than a game-side bug. The breadcrumbs record what the game was submitting "
                   "immediately before the driver crashed, which may help identify a known driver-specific "
                   "workload that triggers this.",
                   "1) Update to the latest GPU driver - this is the single most effective fix for internal "
                   "driver errors, since it means the driver itself crashed, not the game. "
                   "2) If already on the latest driver, try rolling back one or two versions - new driver "
                   "releases occasionally introduce regressions for specific games or render features. "
                   "3) Report the render pass name from the breadcrumb trace to NVIDIA/AMD/Intel driver "
                   "feedback channels in addition to the game developers, since this is most likely fixed "
                   "on the driver side, not the game side. "
                   "4) Disable any GPU driver-level overlay/recording features (e.g. in-driver instant "
                   "replay, performance overlays) temporarily to rule those out as a contributing factor."),
    "0x887A0001": ("DXGI_ERROR_INVALID_CALL",
                   "The application made an invalid D3D12 API call. When reported as a device-removed "
                   "reason, this usually means the API was called in an illegal state - e.g. after the "
                   "device was already removed by another cause.",
                   "1) This is almost always a downstream symptom of an earlier, separate device removal - "
                   "check Windows Event Viewer around this timestamp for an earlier DEVICE_HUNG, "
                   "DEVICE_REMOVED, or DRIVER_INTERNAL_ERROR event that happened first. "
                   "2) If this is the only device-removed event with no earlier cause found, this points to "
                   "an actual game-side bug calling a D3D12 function incorrectly - share this log with the "
                   "development team since it likely needs a code fix, not a settings/driver change."),
}

D3D12_BREADCRUMB_OPS = {
    0:  "SETMARKER",
    1:  "BEGINEVENT",
    2:  "ENDEVENT",
    3:  "DRAWINSTANCED",
    4:  "DRAWINDEXEDINSTANCED",
    5:  "EXECUTEINDIRECT",
    6:  "DISPATCH (compute)",
    7:  "COPYBUFFERREGION",
    8:  "COPYTEXTUREREGION",
    9:  "COPYRESOURCE",
    10: "COPYTILES",
    11: "RESOLVESUBRESOURCE",
    12: "CLEARRENDERTARGETVIEW",
    13: "CLEARUNORDEREDACCESSVIEW",
    14: "CLEARDEPTHSTENCILVIEW",
    15: "RESOURCEBARRIER",
    16: "EXECUTEBUNDLE",
    17: "PRESENT",
    18: "RESOLVEQUERYDATA",
    19: "BEGINSUBMISSION",
    20: "ENDSUBMISSION",
    21: "DECODEFRAME",
    22: "PROCESSFRAMES",
    23: "ATOMICCOPYBUFFERUINT",
    24: "ATOMICCOPYBUFFERUINT64",
    25: "RESOLVESUBRESOURCEREGION",
    26: "WRITEBUFFERIMMEDIATE",
    27: "DECODEFRAME1",
    28: "SETPROTECTEDRESOURCESESSION",
    29: "DECODEFRAME2",
    30: "PROCESSFRAMES1",
    31: "BUILDRAYTRACINGACCELERATIONSTRUCTURE",
    32: "EMITRAYTRACINGACCELERATIONSTRUCTUREPOSTBUILDINFO",
    33: "COPYRAYTRACINGACCELERATIONSTRUCTURE",
    34: "DISPATCHRAYS (raytracing)",
    35: "INITIALIZEMETACOMMAND",
    36: "EXECUTEMETACOMMAND",
    37: "ESTIMATEMOTION",
    38: "RESOLVEMOTIONVECTORHEAP",
    39: "SETPIPELINESTATE1",
    40: "INITIALIZEEXTENSIONCOMMAND",
    41: "EXECUTEEXTENSIONCOMMAND",
    42: "DISPATCHMESH (mesh shaders)",
    43: "ENCODEFRAME",
    44: "RESOLVEENCODEROUTPUTMETADATA",
}

D3D12_HANG_RISK = {
    "DRAWINSTANCED":               "HIGH",
    "DRAWINDEXEDINSTANCED":        "HIGH",
    "DISPATCH (compute)":          "HIGH",
    "EXECUTEINDIRECT":             "HIGH",
    "DISPATCHRAYS (raytracing)":   "HIGH",
    "DISPATCHMESH (mesh shaders)": "HIGH",
    "EXECUTEMETACOMMAND":          "HIGH",
    "BUILDRAYTRACINGACCELERATIONSTRUCTURE": "HIGH",
    "RESOURCEBARRIER":             "MED",
    "EXECUTEBUNDLE":               "MED",
    "COPYRESOURCE":                "MED",
    "COPYTEXTUREREGION":           "MED",
    "COPYBUFFERREGION":            "MED",
    "RESOLVESUBRESOURCE":          "MED",
    "PRESENT":                     "MED",
    "CLEARRENDERTARGETVIEW":       "LOW",
    "CLEARDEPTHSTENCILVIEW":       "LOW",
    "CLEARUNORDEREDACCESSVIEW":    "LOW",
    "SETMARKER":                   "LOW",
    "BEGINEVENT":                  "LOW",
    "ENDEVENT":                    "LOW",
}

EXCEPTION_CODES = {
    0xC0000005: "⚠ STINGRAY ENGINE SUICIDE (false flag) – Engine detected an internal error and intentionally terminated. This is NOT the root cause - To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs",
    0xC000001D: "ILLEGAL_INSTRUCTION – CPU executed an invalid instruction",
    0xC0000034: "OBJECT_NAME_NOT_FOUND – Named object not found",
    0xC000008C: "ARRAY_BOUNDS_EXCEEDED – Array index out of bounds",
    0xC000008E: "FLOAT_DIVIDE_BY_ZERO – Floating-point division by zero",
    0xC0000090: "FLOAT_INVALID_OPERATION – Invalid floating-point operation",
    0xC0000094: "INTEGER_DIVIDE_BY_ZERO – Integer division by zero",
    0xC0000095: "INTEGER_OVERFLOW – Integer overflow",
    0xC0000096: "PRIVILEGED_INSTRUCTION – Privileged CPU instruction",
    0xC00000FD: "STACK_OVERFLOW – Stack pointer out of bounds",
    0xC0000135: "DLL_NOT_FOUND – Required DLL not found",
    0xC0000139: "ENTRY_POINT_NOT_FOUND – DLL export not found",
    0xC0000142: "DLL_INIT_FAILED – DLL initialization failed",
    0xC0000374: "HEAP_CORRUPTION – Heap metadata corrupted",
    0x80000001: "GUARD_PAGE – Guard page access (stack near overflow)",
    0x80000003: "BREAKPOINT – Debugger breakpoint hit",
    0x80000004: "SINGLE_STEP – Single-step trace trap",
    0xC0000409: "STACK_BUFFER_OVERRUN – /GS stack check failed",
    0xC0000602: "ASSERTION_FAILURE – Assertion failed",
    0xE06D7363: "CPP_EXCEPTION – C++ exception (0xE06D7363 = 'msc')",
    0xC0000006: "IN_PAGE_ERROR – Page fault reading from disk (corrupted install or failing drive)",
    0xC0000008: "INVALID_HANDLE – Handle used after being closed (use-after-close)",
    0xC000000D: "INVALID_PARAMETER – Invalid parameter passed to a system call",
    0xC0000017: "NO_MEMORY / NO_PAGEFILE – Out of virtual address space or pagefile exhausted",
    0xC000001A: "NOT_MAPPED_VIEW – Memory region is not mapped",
    0xC0000022: "ACCESS_DENIED – File or registry permission failure (antivirus / UAC)",
    0xC000009A: "INSUFFICIENT_RESOURCES – OS kernel resource exhaustion",
    0xC0000353: "INVALID_CRUNTIME_PARAMETER – C runtime security check (_invalid_parameter)",
    0xC0000420: "ASSERTION_FAILURE – MSVC assert() macro fired in release build",
    0x80000002: "DATATYPE_MISALIGNMENT – Unaligned memory access (SSE/NEON or ARM)",
    0x40010005: "DBG_CONTROL_C – Ctrl+C signal (not a real crash; console application)",

}

EXCEPTION_HEADLINES = {
    0xC000001D: "The game crashed because the CPU tried to execute an invalid instruction - usually a sign of corrupted code in memory or a JIT/codegen bug.",
    0xC0000034: "The game crashed because it tried to open a named system object (event, mutex, etc.) that doesn't exist.",
    0xC000008C: "The game crashed because it accessed an array using an index outside its valid bounds.",
    0xC000008E: "The game crashed due to a floating-point division by zero in game or engine code.",
    0xC0000090: "The game crashed due to an invalid floating-point operation, such as taking the square root of a negative number.",
    0xC0000094: "The game crashed due to an integer division by zero in game or engine code.",
    0xC0000095: "The game crashed due to an integer overflow that the CPU flagged as an error.",
    0xC0000096: "The game crashed because it tried to execute a CPU instruction that requires kernel-level privileges it doesn't have.",
    0xC0000135: "The game failed to start because a required DLL could not be found - usually a missing or incorrectly installed dependency.",
    0xC0000139: "The game failed to start because a DLL was found but didn't contain a function the game expected - usually a version mismatch between the game and one of its DLLs.",
    0xC0000409: "The game crashed because a stack buffer overrun was detected by the compiler's security check (/GS) - typically caused by writing past the end of a local array or buffer.",
    0xC0000602: "The game crashed because an internal assertion check failed - the engine detected a condition it expected to never happen.",
    0xC0000006: "The game crashed while reading game files from disk - this usually points to a corrupted installation or a failing/disconnected drive, not a code bug.",
    0xC0000008: "The game crashed because it tried to use a system handle (file, event, etc.) after that handle had already been closed.",
    0xC000000D: "The game crashed because it passed an invalid parameter to a Windows system call.",
    0xC0000017: "The game crashed because it ran out of memory or virtual address space - try closing other applications or increasing your page file size.",
    0xC000001A: "The game crashed because it tried to access a region of memory that was never mapped into the process.",
    0xC0000022: "The game crashed due to a permissions error accessing a file or registry key - antivirus software or Windows UAC may be blocking it.",
    0xC000009A: "The game crashed because Windows ran out of an internal kernel resource (such as handles) - try restarting your PC.",
    0xC0000353: "The game crashed because a C runtime security check rejected an invalid parameter passed to a standard library function.",
    0xC0000420: "The game crashed because an assert() check built into the game's release build failed - the developers added a safety check that caught an unexpected condition.",
    0x80000001: "The game's stack came within a guard page of overflowing - this is an early warning sign of the same cause as a stack overflow (likely infinite recursion).",
    0x80000002: "The game crashed because the CPU tried to access memory at an address that wasn't properly aligned for the data type being read or written.",
    0x40010005: "This isn't a crash - it's a Ctrl+C signal sent to a console application, which Windows reports as an exception even though nothing went wrong.",
}

STINGRAY_PATTERNS = {
    "lua":              ("Lua scripting crash",       YELLOW,
                         "Could be: bad Lua script accessing a nil unit/component, "
                         "script calling a C function with wrong args, Lua stack corruption, "
                         "or a Flow node invoking a deleted entity."),
    "script":           ("Script/Lua error",          YELLOW,
                         "Could be: script error during level load or gameplay event, "
                         "missing resource referenced from script, or a callback fired on a destroyed object."),
    "resource_manager": ("Resource manager fault",    ACCENT,
                         "Could be: resource loaded while streaming is in progress, "
                         "corrupted or missing .package/.bundle file, double-free of a resource handle, "
                         "or resource type mismatch at runtime."),
    "render":           ("Renderer crash",            PURPLE,
                         "Could be: invalid draw call with unbound shader resource, "
                         "render target size mismatch, GPU memory exhaustion, "
                         "or a material referencing a deleted texture."),
    "d3d":              ("Direct3D / GPU crash",      PURPLE,
                         "Could be: D3D device lost (GPU hang/driver crash), "
                         "invalid resource barrier, descriptor heap overflow, "
                         "or shader accessing out-of-bounds memory on GPU."),
    "dxgi":             ("DXGI / swap-chain fault",   PURPLE,
                         "Could be: swap chain resize during render, "
                         "alt+tab or resolution change while GPU work is in flight, "
                         "or monitor/display driver change invalidating the swap chain."),
    "physx":            ("PhysX crash",               ACCENT2,
                         "Could be: rigid body with NaN transform (bad position/rotation fed to physics), "
                         "collision mesh with degenerate geometry, "
                         "or PhysX scene update called on a destroyed actor."),
    "physics":          ("Physics subsystem crash",   ACCENT2,
                         "Could be: physics body spawned at an invalid position (NaN/inf), "
                         "joint constraint between two destroyed actors, "
                         "or physics tick running on a level that has already unloaded."),
    "audio":            ("Audio subsystem crash",     GREEN,
                         "Could be: audio event triggered on a destroyed emitter, "
                         "sound bank not loaded when event fires, "
                         "or audio thread accessing a freed voice slot."),
    "wwise":            ("Wwise audio crash",         GREEN,
                         "Could be: Wwise event posted with an invalid game object ID, "
                         "missing or mismatched SoundBank, "
                         "Wwise not initialized before first event, "
                         "or AkBank unloaded while sounds are still playing."),
    "network":          ("Network subsystem crash",   TEXT_DIM,
                         "Could be: packet received with unexpected layout (version mismatch), "
                         "RPC called on an object that no longer exists on this peer, "
                         "or network buffer overflow during high-traffic spike."),
    "animation":        ("Animation system crash",    ACCENT2,
                         "Could be: animation played on a unit with mismatched skeleton, "
                         "blend tree accessing a deleted animation state, "
                         "or bone index out of range in an attachment query."),
    "memory":           ("Memory manager fault",      RED,
                         "Could be: heap corruption from a buffer overwrite earlier in the frame, "
                         "double-free of an allocation, use-after-free on a pooled object, "
                         "or allocator internal structure stomped by a bad pointer write."),
    "alloc":            ("Allocator crash",           RED,
                         "Could be: allocation size overflow (negative or huge size passed), "
                         "custom allocator's free list corrupted, "
                         "or out-of-memory condition in a fixed-size pool."),
    "assert":           ("Assertion failure",         YELLOW,
                         "Could be: engine precondition violated (null pointer passed to API), "
                         "array index out of expected range, "
                         "or a state machine entered an impossible state."),
    "foundation":       ("Foundation layer crash",    ACCENT,
                         "Could be: core container (Array/HashMap) accessed out of bounds, "
                         "string table overflow, file I/O error treated as fatal, "
                         "or thread synchronisation primitive used after destruction."),
    "entity":           ("Entity system crash",       ACCENT,
                         "Could be: component accessed on a destroyed entity, "
                         "entity ID reused before all references were cleared, "
                         "or entity spawned with a malformed resource definition."),
    "unit":             ("Unit system crash",         ACCENT,
                         "Could be: unit spawned with a missing or incompatible .unit resource, "
                         "script accessing a unit node/bone that doesn't exist, "
                         "or unit destroyed while an animation or physics callback is still pending."),
    "dstorage":         ("DirectStorage failure",    PURPLE,
                         "Could be: DirectStorage asset streaming failed mid-load (the engine then null-dereferences "
                         "the unloaded asset - this will always show as 0xC0000005). "
                         "Check if dstorage.dll / dstoragecore.dll are present and up to date, "
                         "verify GPU drivers support DirectStorage, "
                         "and look for streaming errors in the .log file before the crash."),
    "dstoragecore":     ("DirectStorage core failure", PURPLE,
                         "Could be: DirectStorage core runtime crashed during asset decompression or GPU upload. "
                         "The engine will null-deref the failed asset - always appears as 0xC0000005. "
                         "Try disabling DirectStorage in game settings if available, or update GPU drivers."),
    "flow":             ("Flow (visual scripting)",   YELLOW,
                         "Could be: Flow graph event fired on a destroyed unit, "
                         "external event name not registered in the Flow system, "
                         "or a Flow variable node referencing a component that was removed."),
    "input":            ("Input system crash",         ACCENT2,
                         "Could be: input callback fired on a destroyed unit, "
                         "controller hotplug during gameplay causing a dangling device handle, "
                         "or a key-binding referencing a deleted action."),
    "ai":               ("AI subsystem crash",         ACCENT2,
                         "Could be: behavior tree ticking on a destroyed unit, "
                         "navmesh query on an unloaded level, "
                         "or a perception event referencing a dead actor."),
    "navmesh":          ("Navigation mesh crash",      ACCENT2,
                         "Could be: pathfinding query on a stale navmesh tile, "
                         "navmesh rebuilt while agents are mid-query, "
                         "or an agent position that is NaN/inf."),
    "particles":        ("Particle system crash",      YELLOW,
                         "Could be: particle emitter update on a destroyed unit, "
                         "effect spawned at a NaN position, "
                         "or a particle material referencing an unloaded texture."),
    "vfx":              ("VFX system crash",           YELLOW,
                         "Could be: VFX component accessed on a destroyed entity, "
                         "effect template missing from loaded packages, "
                         "or VFX tick running after the level has unloaded."),
    "terrain":          ("Terrain system crash",       ACCENT,
                         "Could be: height-map sampling at an out-of-bounds coordinate, "
                         "terrain LOD transition on an unloaded chunk, "
                         "or a terrain material referencing an unloaded texture."),
    "camera":           ("Camera system crash",        ACCENT,
                         "Could be: camera follow-target unit destroyed mid-frame, "
                         "spring-arm query against invalid geometry, "
                         "or camera blend from a deleted camera entity."),
    "hud":              ("HUD / UI crash",             YELLOW,
                         "Could be: UI widget accessing a destroyed entity or player state, "
                         "font or texture atlas not loaded when HUD is drawn, "
                         "or a Flow-driven UI event firing on an unloaded level."),
    "shader":           ("Shader system crash",        PURPLE,
                         "Could be: shader permutation not found in the compiled cache, "
                         "shader constant buffer size mismatch at bind time, "
                         "or a hot-reload of shaders with an incompatible pipeline state."),
    "texture":          ("Texture streaming crash",    PURPLE,
                         "Could be: texture handle dereferenced before streaming is complete, "
                         "mip-map request on an evicted texture, "
                         "or a texture atlas rebuilt while a draw call is in flight."),
    "mesh":             ("Mesh / geometry crash",      ACCENT,
                         "Could be: mesh LOD switch on a destroyed unit, "
                         "vertex buffer freed while GPU draw call is in flight, "
                         "or a skinned mesh with a mismatched skeleton."),
    "material":         ("Material system crash",      PURPLE,
                         "Could be: material parameter update on an unloaded material, "
                         "material referencing a deleted texture or shader, "
                         "or a material hot-swap during a render pass."),
    "plugin":           ("Plugin system crash",        ACCENT,
                         "Could be: plugin DLL version mismatch with the engine, "
                         "plugin accessing engine internals that changed between builds, "
                         "or a plugin not properly unregistered before level unload."),
    "level":            ("Level streaming crash",      ACCENT,
                         "Could be: level unloaded while objects in it are still being ticked, "
                         "cross-level object reference not cleared before unload, "
                         "or streaming trigger fired on a level that failed to load."),
    "savegame":         ("Save/load system crash",     ACCENT2,
                         "Could be: save data version mismatch with current build, "
                         "corrupted save file causing bad pointer reconstruction, "
                         "or async save completing after the level that owns the data unloaded."),
}

def addr_to_mod(addr: int, modules: list) -> "tuple | None":
    for m in modules:
        try:
            base = int(m["base"], 16)
            if base <= addr < base + m["size"]:
                return PureWindowsPath(m["name"]).name, addr - base, m["name"], base
        except Exception:
            pass
    return None


def parse_engine_log(path: str) -> dict:
    result = {"errors": [], "warnings": [], "last_lines": [], "has_errors": False, "_raw_path": path}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        result["error"] = str(e)
        return result

    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in ("error", "fatal", "assert", "crash", "exception", "failed")):
            if "warning" in line_lower:
                result["warnings"].append(line.rstrip())
            else:
                result["errors"].append(line.rstrip())
        elif "warning" in line_lower or "warn" in line_lower:
            result["warnings"].append(line.rstrip())

    result["has_errors"] = len(result["errors"]) > 0
    result["last_lines"] = [l.rstrip() for l in lines[-20:]]
    return result


def parse_minidump(path: str) -> dict:

    result = {
        "file": path,
        "_raw_path": path,
        "size_mb": round(os.path.getsize(path) / 1024 / 1024, 2),
        "parse_errors": [],
        "streams": [],
        "exception": None,
        "modules": [],
        "system_info": {},
        "threads": [],
        "raw_flags": None,
        "memory_map": [],
    }

    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        result["parse_errors"].append(f"Cannot read file: {e}")
        return result

    result["_raw_bytes"] = data

    if len(data) < 32 or data[:4] != b"MDMP":
        result["parse_errors"].append("Not a valid minidump (bad magic bytes)")
        return result

    version       = struct.unpack_from("<H", data, 4)[0]
    impl_version  = struct.unpack_from("<H", data, 6)[0]
    stream_count  = struct.unpack_from("<I", data, 8)[0]
    stream_rva    = struct.unpack_from("<I", data, 12)[0]
    checksum      = struct.unpack_from("<I", data, 16)[0]
    timestamp     = struct.unpack_from("<I", data, 20)[0]
    flags         = struct.unpack_from("<Q", data, 24)[0]

    result["raw_flags"]  = flags
    result["version"]    = f"{version}.{impl_version}"
    result["timestamp"]  = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else "N/A"
    result["stream_count"] = stream_count

    STREAM_TYPES = {
        3:  "ThreadListStream",
        4:  "ModuleListStream",
        5:  "MemoryListStream",
        6:  "ExceptionStream",
        7:  "SystemInfoStream",
        8:  "ThreadExListStream",
        9:  "Memory64ListStream",
        10: "CommentStreamA",
        11: "CommentStreamW",
        12: "HandleDataStream",
        13: "FunctionTableStream",
        14: "UnloadedModuleListStream",
        15: "MiscInfoStream",
        16: "MemoryInfoListStream",
        17: "ThreadInfoListStream",
        21: "TokenStream",
    }

    for i in range(min(stream_count, 64)):
        offset = stream_rva + i * 12
        if offset + 12 > len(data):
            break
        stype  = struct.unpack_from("<I", data, offset)[0]
        ssize  = struct.unpack_from("<I", data, offset + 4)[0]
        srva   = struct.unpack_from("<I", data, offset + 8)[0]
        name   = STREAM_TYPES.get(stype, f"Unknown({stype})")
        result["streams"].append({"type": stype, "name": name, "size": ssize, "rva": srva})

        if stype == 7 and ssize >= 56 and srva + 56 <= len(data):
            arch   = struct.unpack_from("<H", data, srva)[0]
            level  = struct.unpack_from("<H", data, srva + 2)[0]
            rev    = struct.unpack_from("<H", data, srva + 4)[0]
            ncpus  = struct.unpack_from("<B", data, srva + 6)[0]
            ptype  = struct.unpack_from("<B", data, srva + 7)[0]
            osmaj  = struct.unpack_from("<I", data, srva + 8)[0]
            osmin  = struct.unpack_from("<I", data, srva + 12)[0]
            osbld  = struct.unpack_from("<I", data, srva + 16)[0]
            ARCH   = {0: "x86", 5: "ARM", 6: "IA64", 9: "x64", 12: "ARM64"}
            result["system_info"] = {
                "arch":       ARCH.get(arch, f"arch_{arch}"),
                "cpu_level":  level,
                "cpu_rev":    rev,
                "cpu_count":  ncpus,
                "os_version": f"{osmaj}.{osmin} build {osbld}",
            }

        if stype == 6 and ssize >= 16 and srva + ssize <= len(data):
            tid  = struct.unpack_from("<I", data, srva)[0]
            exc  = srva + 8
            if exc + 40 <= len(data):
                code    = struct.unpack_from("<I", data, exc)[0]
                eflags  = struct.unpack_from("<I", data, exc + 4)[0]
                addr    = struct.unpack_from("<Q", data, exc + 16)[0] if exc + 24 <= len(data) else 0
                nparams = struct.unpack_from("<I", data, exc + 24)[0] if exc + 28 <= len(data) else 0
                params  = []
                for p in range(min(nparams, 15)):
                    poff = exc + 32 + p * 8
                    if poff + 8 <= len(data):
                        params.append(hex(struct.unpack_from("<Q", data, poff)[0]))
                desc = EXCEPTION_CODES.get(code, f"Unknown exception 0x{code:08X}")

                ex_ctx_regs = {}
                ex_ctx_loc  = srva + 160
                if ex_ctx_loc + 8 <= len(data):
                    ex_ctx_size = struct.unpack_from("<I", data, ex_ctx_loc)[0]
                    ex_ctx_rva  = struct.unpack_from("<I", data, ex_ctx_loc + 4)[0]
                    if ex_ctx_rva + 0x100 <= len(data) and ex_ctx_size >= 0x100:
                        def _r(off): return struct.unpack_from("<Q", data, ex_ctx_rva + off)[0]
                        ex_ctx_regs = {
                            "rax": _r(0x78), "rcx": _r(0x80), "rdx": _r(0x88),
                            "rbx": _r(0x90), "rsp": _r(0x98), "rbp": _r(0xA0),
                            "rsi": _r(0xA8), "rdi": _r(0xB0), "r8":  _r(0xB8),
                            "r9":  _r(0xC0), "r10": _r(0xC8), "r11": _r(0xD0),
                            "r12": _r(0xD8), "r13": _r(0xE0), "r14": _r(0xE8),
                            "r15": _r(0xF0),
                            "rip": _r(0xF8),
                        }
                        if ex_ctx_rva + 0x2A0 <= len(data) and ex_ctx_size >= 0x2A0:
                            xmm_regs = {}
                            for i in range(16):
                                xmm_off = 0x1A0 + i * 16
                                lo = struct.unpack_from("<Q", data, ex_ctx_rva + xmm_off)[0]
                                hi = struct.unpack_from("<Q", data, ex_ctx_rva + xmm_off + 8)[0]
                                xmm_regs[f"xmm{i}"] = (lo, hi)
                            if xmm_regs:
                                ex_ctx_regs["_xmm"] = xmm_regs

                result["exception"] = {
                    "thread_id":   tid,
                    "code":        f"0x{code:08X}",
                    "code_desc":   desc,
                    "flags":       f"0x{eflags:08X}",
                    "address":     f"0x{addr:016X}",
                    "param_count": nparams,
                    "params":      params,
                    "regs":        ex_ctx_regs,
                }

        if stype == 4 and srva + 4 <= len(data):
            nmod = struct.unpack_from("<I", data, srva)[0]
            moff = srva + 4
            MODULE_ENTRY_SIZE = 108
            for m in range(min(nmod, 256)):
                eoff = moff + m * MODULE_ENTRY_SIZE
                if eoff + MODULE_ENTRY_SIZE > len(data):
                    break
                base  = struct.unpack_from("<Q", data, eoff)[0]
                size  = struct.unpack_from("<I", data, eoff + 8)[0]
                cs    = struct.unpack_from("<I", data, eoff + 12)[0]
                ts    = struct.unpack_from("<I", data, eoff + 16)[0]
                nrva  = struct.unpack_from("<I", data, eoff + 20)[0]
                name_str = ""
                if nrva + 4 <= len(data):
                    nlen = struct.unpack_from("<I", data, nrva)[0]
                    try:
                        nlen = min(nlen, 1024)
                        raw = data[nrva + 4: nrva + 4 + nlen]
                        name_str = raw.decode("utf-16-le", errors="replace").rstrip("\x00")
                        printable = sum(1 for c in name_str if c.isprintable())
                        if name_str and printable / len(name_str) < 0.7:
                            name_str = f"<unreadable @ 0x{nrva:X}>"
                    except Exception:
                        name_str = f"<decode error @ 0x{nrva:X}>"
                result["modules"].append({
                    "name":      name_str or f"module_{m}",
                    "base":      f"0x{base:016X}",
                    "size":      size,
                    "checksum":  f"0x{cs:08X}",
                    "timestamp": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "N/A",
                })

        if stype == 5 and srva + 4 <= len(data):
            nranges = struct.unpack_from("<I", data, srva)[0]
            for r in range(min(nranges, 8192)):
                roff     = srva + 4 + r * 16
                if roff + 16 > len(data): break
                start    = struct.unpack_from("<Q", data, roff)[0]
                datasize = struct.unpack_from("<I", data, roff + 8)[0]
                datarva  = struct.unpack_from("<I", data, roff + 12)[0]
                result["memory_map"].append((start, datasize, datarva))

        if stype == 9 and srva + 16 <= len(data):
            n64ranges = struct.unpack_from("<Q", data, srva)[0]
            base_rva  = struct.unpack_from("<Q", data, srva + 8)[0]
            offset = base_rva
            for r in range(min(n64ranges, 65536)):
                roff = srva + 16 + r * 16
                if roff + 16 > len(data): break
                start = struct.unpack_from("<Q", data, roff)[0]
                dsize = struct.unpack_from("<Q", data, roff + 8)[0]
                result["memory_map"].append((start, dsize, offset))
                offset += dsize

        if stype == 15 and srva + 24 <= len(data):
            mflags = struct.unpack_from("<I", data, srva)[0]
            pid    = struct.unpack_from("<I", data, srva + 4)[0]
            if mflags & 1:
                result["process_id"] = pid

        if stype == 3 and srva + 4 <= len(data):
            nthreads = struct.unpack_from("<I", data, srva)[0]
            THREAD_SIZE = 48
            for t in range(min(nthreads, 512)):
                toff     = srva + 4 + t * THREAD_SIZE
                if toff + THREAD_SIZE > len(data): break
                tid      = struct.unpack_from("<I", data, toff)[0]
                suspend  = struct.unpack_from("<I", data, toff + 4)[0]
                pri      = struct.unpack_from("<I", data, toff + 12)[0]
                stk_rva  = struct.unpack_from("<I", data, toff + 36)[0]
                stk_size = struct.unpack_from("<I", data, toff + 32)[0]
                ctx_size = struct.unpack_from("<I", data, toff + 40)[0]
                ctx_rva  = struct.unpack_from("<I", data, toff + 44)[0]

                rip = rsp = rax = rcx = rdx = rbx = rbp = rsi = rdi = 0
                r8 = r9 = r10 = r11 = r12 = r13 = r14 = r15 = 0
                if ctx_rva + 0x100 <= len(data) and ctx_size >= 0x100:
                    rax = struct.unpack_from("<Q", data, ctx_rva + 0x78)[0]
                    rcx = struct.unpack_from("<Q", data, ctx_rva + 0x80)[0]
                    rdx = struct.unpack_from("<Q", data, ctx_rva + 0x88)[0]
                    rbx = struct.unpack_from("<Q", data, ctx_rva + 0x90)[0]
                    rsp = struct.unpack_from("<Q", data, ctx_rva + 0x98)[0]
                    rbp = struct.unpack_from("<Q", data, ctx_rva + 0xA0)[0]
                    rsi = struct.unpack_from("<Q", data, ctx_rva + 0xA8)[0]
                    rdi = struct.unpack_from("<Q", data, ctx_rva + 0xB0)[0]
                    r8  = struct.unpack_from("<Q", data, ctx_rva + 0xB8)[0]
                    r9  = struct.unpack_from("<Q", data, ctx_rva + 0xC0)[0]
                    r10 = struct.unpack_from("<Q", data, ctx_rva + 0xC8)[0]
                    r11 = struct.unpack_from("<Q", data, ctx_rva + 0xD0)[0]
                    r12 = struct.unpack_from("<Q", data, ctx_rva + 0xD8)[0]
                    r13 = struct.unpack_from("<Q", data, ctx_rva + 0xE0)[0]
                    r14 = struct.unpack_from("<Q", data, ctx_rva + 0xE8)[0]
                    r15 = struct.unpack_from("<Q", data, ctx_rva + 0xF0)[0]
                    rip = struct.unpack_from("<Q", data, ctx_rva + 0xF8)[0]
                result["threads"].append({
                    "tid": tid, "suspend": suspend, "pri": pri,
                    "rip": rip, "rsp": rsp,
                    "rax": rax, "rcx": rcx, "rdx": rdx, "rbx": rbx,
                    "rbp": rbp, "rsi": rsi, "rdi": rdi,
                    "r8":  r8,  "r9":  r9,  "r10": r10, "r11": r11,
                    "r12": r12, "r13": r13, "r14": r14, "r15": r15,
                })

    return result


MSVCP140_KNOWN_GOOD: list[dict] = [
    {"version": "14.38.x (VS2022 17.8)",  "timestamp": 0x6543C0D5, "size_min": 570_000, "size_max": 620_000,
     "notes": "VS2022 17.8 redistributable - standard shipping version"},
    {"version": "14.40.x (VS2022 17.10)", "timestamp": 0x6656D2F0, "size_min": 570_000, "size_max": 625_000,
     "notes": "VS2022 17.10 redistributable"},
    {"version": "14.36.x (VS2022 17.6)",  "timestamp": 0x6458F060, "size_min": 565_000, "size_max": 615_000,
     "notes": "VS2022 17.6 redistributable"},
    {"version": "14.34.x (VS2022 17.4)",  "timestamp": 0x638EDE40, "size_min": 560_000, "size_max": 610_000,
     "notes": "VS2022 17.4 redistributable"},
    {"version": "14.32.x (VS2022 17.2)",  "timestamp": 0x6281F2F0, "size_min": 555_000, "size_max": 608_000,
     "notes": "VS2022 17.2 redistributable"},
    {"version": "14.30.x (VS2022 17.0)",  "timestamp": 0x618B7E60, "size_min": 550_000, "size_max": 605_000,
     "notes": "VS2022 17.0 initial release redistributable"},
    {"version": "14.29.x (VS2019 16.11)", "timestamp": 0x60E23DC0, "size_min": 540_000, "size_max": 595_000,
     "notes": "VS2019 16.11 redistributable"},
    {"version": "14.28.x (VS2019 16.8)",  "timestamp": 0x5F87F400, "size_min": 535_000, "size_max": 590_000,
     "notes": "VS2019 16.8 redistributable"},
    {"version": "14.26.x (VS2019 16.6)",  "timestamp": 0x5EC61A60, "size_min": 530_000, "size_max": 585_000,
     "notes": "VS2019 16.6 redistributable"},
    {"version": "14.16.x (VS2017 15.9)",  "timestamp": 0x5C5C9CE0, "size_min": 490_000, "size_max": 550_000,
     "notes": "VS2017 15.9 final redistributable"},
    {"version": "14.0.x (VS2015 RTM)",    "timestamp": 0x55C1C4C0, "size_min": 420_000, "size_max": 490_000,
     "notes": "VS2015 RTM redistributable (oldest supported)"},
    {"version": "14.x x86 (VS2017-2022)", "timestamp": 0,          "size_min": 380_000, "size_max": 530_000,
     "notes": "x86 32-bit build - loaded from SysWOW64 by 32-bit processes"},
    {"version": "14.0.x x86 (VS2015)",    "timestamp": 0,          "size_min": 300_000, "size_max": 430_000,
     "notes": "x86 32-bit VS2015 build from SysWOW64"},
]

DISCORD_KNOWN_GOOD: list[dict] = [
    {"dll": "discord_game_sdk.dll", "version": "3.2.1", "size_min": 2_500_000, "size_max": 3_200_000,
     "notes": "Discord Game SDK v3.2.1 - current official release"},
    {"dll": "discord_game_sdk.dll", "version": "3.1.x", "size_min": 2_400_000, "size_max": 3_100_000,
     "notes": "Discord Game SDK v3.1.x"},
    {"dll": "discord_game_sdk.dll", "version": "2.x",   "size_min": 1_800_000, "size_max": 2_600_000,
     "notes": "Discord Game SDK v2.x"},
    {"dll": "discordrpc.dll",       "version": "1.x",   "size_min":   200_000, "size_max":   800_000,
     "notes": "Legacy Discord Rich Presence SDK v1.x"},
]



VCRUNTIME140_KNOWN_GOOD: list[dict] = [
    {"version": "14.38.x (VS2022 17.8)",  "size_min":  80_000, "size_max": 115_000,
     "notes": "VS2022 17.8 redistributable"},
    {"version": "14.40.x (VS2022 17.10)", "size_min":  80_000, "size_max": 115_000,
     "notes": "VS2022 17.10 redistributable"},
    {"version": "14.36.x (VS2022 17.6)",  "size_min":  78_000, "size_max": 112_000,
     "notes": "VS2022 17.6 redistributable"},
    {"version": "14.34.x (VS2022 17.4)",  "size_min":  76_000, "size_max": 110_000,
     "notes": "VS2022 17.4 redistributable"},
    {"version": "14.32.x (VS2022 17.2)",  "size_min":  75_000, "size_max": 108_000,
     "notes": "VS2022 17.2 redistributable"},
    {"version": "14.30.x (VS2022 17.0)",  "size_min":  74_000, "size_max": 106_000,
     "notes": "VS2022 17.0 redistributable"},
    {"version": "14.29.x (VS2019 16.11)", "size_min":  72_000, "size_max": 105_000,
     "notes": "VS2019 16.11 redistributable"},
    {"version": "14.28.x (VS2019 16.8)",  "size_min":  70_000, "size_max": 102_000,
     "notes": "VS2019 16.8 redistributable"},
    {"version": "14.26.x (VS2019 16.6)",  "size_min":  68_000, "size_max": 100_000,
     "notes": "VS2019 16.6 redistributable"},
    {"version": "14.16.x (VS2017 15.9)",  "size_min":  65_000, "size_max":  96_000,
     "notes": "VS2017 15.9 final redistributable"},
    {"version": "14.0.x  (VS2015 RTM)",   "size_min":  55_000, "size_max":  85_000,
     "notes": "VS2015 RTM redistributable (oldest supported)"},
    {"version": "14.x x86 (any VS2017-2022)", "size_min": 45_000, "size_max": 80_000,
     "notes": "x86 32-bit build from SysWOW64 - smaller than x64 equivalent"},
    {"version": "14.0.x x86 (VS2015)",        "size_min": 35_000, "size_max": 65_000,
     "notes": "x86 32-bit VS2015 build from SysWOW64"},
]

VCRUNTIME140_1_KNOWN_GOOD: list[dict] = [
    {"version": "14.38.x (VS2022 17.8)",  "size_min":  28_000, "size_max":  55_000,
     "notes": "VS2022 17.8 redistributable"},
    {"version": "14.40.x (VS2022 17.10)", "size_min":  28_000, "size_max":  55_000,
     "notes": "VS2022 17.10 redistributable"},
    {"version": "14.36.x (VS2022 17.6)",  "size_min":  27_000, "size_max":  54_000,
     "notes": "VS2022 17.6 redistributable"},
    {"version": "14.34.x (VS2022 17.4)",  "size_min":  27_000, "size_max":  53_000,
     "notes": "VS2022 17.4 redistributable"},
    {"version": "14.29.x (VS2019 16.11)", "size_min":  25_000, "size_max":  50_000,
     "notes": "VS2019 16.11 redistributable"},
    {"version": "14.28.x (VS2019 16.8)",  "size_min":  24_000, "size_max":  48_000,
     "notes": "VS2019 16.8 redistributable (first version to ship this DLL)"},
]

CONCRT140_KNOWN_GOOD: list[dict] = [
    {"version": "14.38.x (VS2022 17.8)",  "size_min": 300_000, "size_max": 420_000,
     "notes": "VS2022 17.8 redistributable"},
    {"version": "14.40.x (VS2022 17.10)", "size_min": 300_000, "size_max": 425_000,
     "notes": "VS2022 17.10 redistributable"},
    {"version": "14.36.x (VS2022 17.6)",  "size_min": 295_000, "size_max": 415_000,
     "notes": "VS2022 17.6 redistributable"},
    {"version": "14.34.x (VS2022 17.4)",  "size_min": 290_000, "size_max": 410_000,
     "notes": "VS2022 17.4 redistributable"},
    {"version": "14.29.x (VS2019 16.11)", "size_min": 275_000, "size_max": 395_000,
     "notes": "VS2019 16.11 redistributable"},
    {"version": "14.16.x (VS2017 15.9)",  "size_min": 250_000, "size_max": 370_000,
     "notes": "VS2017 15.9 final redistributable"},
    {"version": "14.0.x  (VS2015 RTM)",   "size_min": 210_000, "size_max": 320_000,
     "notes": "VS2015 RTM redistributable"},
]

UCRTBASE_KNOWN_GOOD: list[dict] = [
    {"version": "Win11 23H2 / 22631",  "size_min": 950_000, "size_max": 1_150_000,
     "notes": "Windows 11 23H2 in-box ucrtbase.dll"},
    {"version": "Win11 22H2 / 22621",  "size_min": 940_000, "size_max": 1_140_000,
     "notes": "Windows 11 22H2 in-box ucrtbase.dll"},
    {"version": "Win11 21H2 / 22000",  "size_min": 930_000, "size_max": 1_130_000,
     "notes": "Windows 11 initial release in-box ucrtbase.dll"},
    {"version": "Win10 22H2 / 19045",  "size_min": 900_000, "size_max": 1_100_000,
     "notes": "Windows 10 22H2 in-box ucrtbase.dll"},
    {"version": "Win10 21H2 / 19044",  "size_min": 895_000, "size_max": 1_095_000,
     "notes": "Windows 10 21H2 in-box ucrtbase.dll"},
    {"version": "Win10 20H2 / 19042",  "size_min": 885_000, "size_max": 1_085_000,
     "notes": "Windows 10 20H2 in-box ucrtbase.dll"},
    {"version": "Win10 1903 / 18362",  "size_min": 860_000, "size_max": 1_060_000,
     "notes": "Windows 10 1903 in-box ucrtbase.dll"},
    {"version": "Win10 RTM / 10240",   "size_min": 780_000, "size_max":   980_000,
     "notes": "Windows 10 RTM in-box ucrtbase.dll (oldest)"},
    {"version": "Win11 x86 (any build)",   "size_min": 620_000, "size_max": 880_000,
     "notes": "x86 32-bit ucrtbase.dll from SysWOW64"},
    {"version": "Win10 x86 (any build)",   "size_min": 580_000, "size_max": 860_000,
     "notes": "x86 32-bit ucrtbase.dll from SysWOW64"},
]

RUNTIME_LEGIT_PATHS = (
    "c:\\windows\\system32\\",
    "c:\\windows\\syswow64\\",
    "c:\\windows\\winsxs\\",
    "c:\\program files (x86)\\microsoft visual studio\\",
    "c:\\program files\\microsoft visual studio\\",
    "c:\\program files (x86)\\common files\\microsoft shared\\",
    "c:\\program files\\common files\\microsoft shared\\",
    "c:\\program files (x86)\\microsoft visual c++",
    "c:\\program files\\microsoft visual c++",
)

UCRTBASE_STRICT_PATHS = (
    "c:\\windows\\system32\\",
    "c:\\windows\\syswow64\\",
    "c:\\windows\\winsxs\\",
)

RUNTIME_DLL_REGISTRY: dict = {
    "vcruntime140.dll":   (VCRUNTIME140_KNOWN_GOOD,   2015,
                           "VC++ 2015-2022 C Runtime (vcruntime140.dll)"),
    "vcruntime140_1.dll": (VCRUNTIME140_1_KNOWN_GOOD, 2019,
                           "VC++ 2019-2022 Extended C Runtime (vcruntime140_1.dll)"),
    "concrt140.dll":      (CONCRT140_KNOWN_GOOD,      2015,
                           "VC++ 2015-2022 Concurrency Runtime (concrt140.dll)"),
    "ucrtbase.dll":       (UCRTBASE_KNOWN_GOOD,        2014,
                           "Windows Universal C Runtime (ucrtbase.dll)"),
}

MSVCP140_LEGIT_PATHS = (
    "c:\\windows\\system32\\",
    "c:\\windows\\syswow64\\",
    "c:\\windows\\winsxs\\",
    "c:\\program files (x86)\\microsoft visual studio\\",
    "c:\\program files\\microsoft visual studio\\",
    "c:\\program files (x86)\\common files\\microsoft shared\\",
    "c:\\program files\\common files\\microsoft shared\\",
    "c:\\program files (x86)\\microsoft visual c++",
    "c:\\program files\\microsoft visual c++",
)

DISCORD_LEGIT_PATH_FRAGMENTS = (
    "\\discord\\",
    "\\discordsdk\\",
    "\\discord_game_sdk",
    "\\discordrpc",
)


def verify_critical_dlls(parsed: dict) -> dict:
    modules = parsed.get("modules", [])

    def _check_msvcp140(m: dict) -> dict:
        sn   = PureWindowsPath(m["name"]).name.lower()
        path = m["name"].lower().replace("/", "\\")
        size = m.get("size", 0)
        cs   = m.get("checksum", "0x00000000")
        ts_raw = 0
        ts_date = m.get("timestamp", "N/A")

        issues = []
        matched_ref = None

        path_ok = any(path.startswith(p) for p in MSVCP140_LEGIT_PATHS)
        is_game_local = not path_ok
        if is_game_local:
            issues.append(
                f"Loaded from non-System32 path: {m['name']} - "
                "legitimate if shipped by game installer, suspicious if not"
            )

        if size < 280_000:
            issues.append(
                f"File size {size:,} bytes is abnormally small for MSVCP140.dll "
                "(x64 genuine copies ~420–660 KB, x86 copies ~350–530 KB) - "
                "possible stub or trojanised replacement"
            )
        elif size > 900_000:
            issues.append(
                f"File size {size:,} bytes is abnormally large for MSVCP140.dll "
                "(genuine copies are typically under 700 KB) - possible padded or injected file"
            )
        else:
            for ref in MSVCP140_KNOWN_GOOD:
                if ref["size_min"] <= size <= ref["size_max"]:
                    matched_ref = ref
                    break

        if ts_date and ts_date != "N/A":
            try:
                year = int(ts_date[:4])
                checksum_zeroed = cs in ("0x00000000", "0x0")
                if year < 2015 and checksum_zeroed:
                    issues.append(
                        f"PE timestamp date {ts_date} predates MSVCP140.dll's existence "
                        "(VC++ 2015 launched in July 2015) AND PE checksum is zeroed - "
                        "timestamp likely forged"
                    )
                elif year < 2015 and not checksum_zeroed:
                    pass
                elif year > 2026:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp {ts_date} is in the future AND the PE checksum "
                            "is 0x00000000 - the combination of a future timestamp with a "
                            "zeroed checksum strongly indicates tampering. "
                            "(Legitimate reproducible-build DLLs have a future-looking hash "
                            "timestamp but always retain a valid non-zero checksum.)"
                        )
            except Exception:
                pass


        if not issues:
            verdict = "OK"
            vc = GREEN
        elif any("small" in i or "large" in i or "zeroed" in i or "forged" in i
                 or "trojan" in i or "injected" in i for i in issues):
            verdict = "LIKELY_TAMPERED"
            vc = RED
        else:
            verdict = "SUSPICIOUS"
            vc = YELLOW

        return {
            "name":         PureWindowsPath(m["name"]).name,
            "path":         m["name"],
            "base":         m.get("base", "?"),
            "size":         size,
            "checksum":     cs,
            "timestamp_date": ts_date,
            "verdict":      verdict,
            "verdict_colour": vc,
            "issues":       issues,
            "matched_ref":  matched_ref,
        }

    def _check_discord(m: dict) -> dict:
        sn   = PureWindowsPath(m["name"]).name.lower()
        path = m["name"].lower().replace("/", "\\")
        size = m.get("size", 0)
        cs   = m.get("checksum", "0x00000000")
        ts_date = m.get("timestamp", "N/A")
        issues = []
        matched_ref = None

        ref_list = [r for r in DISCORD_KNOWN_GOOD if r["dll"] == sn]

        in_system = any(p in path for p in ("\\windows\\system32", "\\windows\\syswow64", "\\winsxs\\"))
        if in_system:
            issues.append(
                f"Discord DLL loaded from Windows system directory ({m['name']}) - "
                "Discord DLLs are never Windows components; this is a DLL hijack or trojan"
            )

        if ref_list:
            size_ok = any(r["size_min"] <= size <= r["size_max"] for r in ref_list)
            if size_ok:
                matched_ref = next(r for r in ref_list if r["size_min"] <= size <= r["size_max"])
            elif size < min(r["size_min"] for r in ref_list):
                issues.append(
                    f"Size {size:,} bytes is smaller than any known genuine {sn} "
                    f"(smallest known: {min(r['size_min'] for r in ref_list):,} bytes) - "
                    "possible stub, stripped, or trojanised file"
                )
            else:
                issues.append(
                    f"Size {size:,} bytes doesn't match any known genuine {sn} version - "
                    "could be a custom build or modified file"
                )
        else:
            if size < 100_000:
                issues.append(
                    f"Unknown Discord variant '{sn}' with very small size {size:,} bytes - "
                    "this doesn't match any known Discord SDK DLL"
                )


        if ts_date and ts_date != "N/A":
            try:
                year = int(ts_date[:4])
                checksum_zeroed = cs in ("0x00000000", "0x0")
                if year < 2017:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp {ts_date} predates Discord's SDK existence "
                            "(Discord Rich Presence SDK launched 2017) AND PE checksum is zeroed - "
                            "timestamp likely forged"
                        )
                elif year > 2026:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp {ts_date} is in the future AND PE checksum is "
                            "0x00000000 - this combination indicates tampering. "
                            "(Reproducible-build DLLs have future-looking timestamps but "
                            "always retain a valid non-zero checksum.)"
                        )
            except Exception:
                pass

        if not issues:
            verdict = "OK"
            vc = GREEN
        elif any("system directory" in i or "trojan" in i or "hijack" in i
                 or "stub" in i or "forged" in i for i in issues):
            verdict = "LIKELY_TAMPERED"
            vc = RED
        else:
            verdict = "SUSPICIOUS"
            vc = YELLOW

        return {
            "name":         PureWindowsPath(m["name"]).name,
            "path":         m["name"],
            "base":         m.get("base", "?"),
            "size":         size,
            "checksum":     cs,
            "timestamp_date": ts_date,
            "verdict":      verdict,
            "verdict_colour": vc,
            "issues":       issues,
            "matched_ref":  matched_ref,
        }


    def _check_runtime_dll(m: dict, dll_name: str) -> dict:
        sn    = dll_name
        path  = m["name"].lower().replace("/", "\\")
        size  = m.get("size", 0)
        cs    = m.get("checksum", "0x00000000")
        ts_date = m.get("timestamp", "N/A")
        issues = []
        matched_ref = None

        ref_table, min_year, ui_label = RUNTIME_DLL_REGISTRY[sn]
        is_ucrtbase = sn == "ucrtbase.dll"

        strict_paths = UCRTBASE_STRICT_PATHS if is_ucrtbase else RUNTIME_LEGIT_PATHS
        path_ok = any(path.startswith(p) for p in strict_paths)
        if not path_ok:
            if is_ucrtbase:
                issues.append(
                    f"ucrtbase.dll loaded from non-Windows path: {m['name']} - "
                    "ucrtbase.dll is a Windows in-box component and must only load "
                    "from System32 or SysWOW64. A game-local copy is a classic DLL "
                    "hijack vector and should be treated as LIKELY_TAMPERED."
                )
            else:
                issues.append(
                    f"{PureWindowsPath(m['name']).name} loaded from non-standard path: {m['name']} - "
                    "legitimate if shipped by a game installer alongside the exe, "
                    "suspicious if the path is unexpected or temporary."
                )

        if size == 0:
            issues.append(f"Size reported as 0 bytes - dump may be incomplete, or the "
                          f"module header was corrupted/zeroed.")
        else:
            global_min = min(r["size_min"] for r in ref_table)
            global_max = max(r["size_max"] for r in ref_table)
            if size < global_min * 0.40:
                issues.append(
                    f"Size {size:,} bytes is far smaller than any known genuine "
                    f"{sn} (smallest known reference: {global_min:,} bytes) - "
                    "possible stub, stripped binary, or trojanised replacement."
                )
            elif size > global_max * 2.2:
                issues.append(
                    f"Size {size:,} bytes is far larger than any known genuine "
                    f"{sn} (largest known reference: {global_max:,} bytes) - "
                    "possible padded or injected file."
                )
            else:
                for ref in ref_table:
                    if ref["size_min"] <= size <= ref["size_max"]:
                        matched_ref = ref
                        break


        SENTINEL_DATES = {"1970-01-01", "2005-03-24", "2005-04-16", "2014-06-17"}
        if ts_date and ts_date != "N/A":
            try:
                year = int(ts_date[:4])
                checksum_zeroed = cs in ("0x00000000", "0x0")
                is_sentinel = ts_date[:10] in SENTINEL_DATES

                if is_sentinel:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp is a known Microsoft sentinel value ({ts_date}) "
                            f"AND PE checksum is 0x00000000. Sentinel timestamps with a "
                            f"zeroed checksum indicate the file has been modified outside "
                            f"of Microsoft's build system."
                        )
                elif year < min_year:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp {ts_date} predates the existence of {sn} "
                            f"(first shipped {min_year}) AND PE checksum is zeroed - "
                            f"timestamp likely forged."
                        )
                elif year > 2026:
                    if checksum_zeroed:
                        issues.append(
                            f"PE timestamp {ts_date} is in the future AND PE checksum is "
                            "0x00000000. Legitimate reproducible-build DLLs have future-looking "
                            "timestamps but always retain a valid checksum. This combination "
                            f"indicates {sn} has been tampered with."
                        )
            except Exception:
                pass



        critical_keywords = (
            "hijack", "trojan", "stub", "forged", "tampered", "non-Windows path",
            "injected", "modified"
        )
        if not issues:
            verdict = "OK"
            vc = GREEN
        elif any(kw in " ".join(issues).lower() for kw in critical_keywords):
            verdict = "LIKELY_TAMPERED"
            vc = RED
        else:
            verdict = "SUSPICIOUS"
            vc = YELLOW

        return {
            "name":           PureWindowsPath(m["name"]).name,
            "path":           m["name"],
            "base":           m.get("base", "?"),
            "size":           size,
            "checksum":       cs,
            "timestamp_date": ts_date,
            "verdict":        verdict,
            "verdict_colour": vc,
            "issues":         issues,
            "matched_ref":    matched_ref,
            "ui_label":       ui_label,
        }

    msvcp140_result  = None
    discord_results  = []
    runtime_results  = {}

    DISCORD_DLL_NAMES = {"discord_game_sdk.dll", "discordrpc.dll", "discord-rpc.dll",
                         "discordgamesdk.dll", "discord_rpc.dll"}

    for m in modules:
        sn = PureWindowsPath(m["name"]).name.lower()
        if sn == "msvcp140.dll":
            msvcp140_result = _check_msvcp140(m)
        elif sn in DISCORD_DLL_NAMES:
            discord_results.append(_check_discord(m))
        elif sn in RUNTIME_DLL_REGISTRY:
            runtime_results[sn] = _check_runtime_dll(m, sn)

    SKIP_FROM_MISMATCH = {"ucrtbase.dll"}
    VCRUNTIME140_1_KEY = "vcruntime140_1.dll"

    def _version_family(version_str: str) -> str | None:
        if not version_str:
            return None
        if "x86" in version_str.lower():
            return None
        for fam in ("VS2022", "VS2019", "VS2017", "VS2015"):
            if fam in version_str:
                return fam
        return None

    family_map = {}
    if msvcp140_result and msvcp140_result.get("matched_ref"):
        fam = _version_family(msvcp140_result["matched_ref"]["version"])
        if fam:
            family_map["msvcp140.dll"] = fam

    for dll_name, res in runtime_results.items():
        if dll_name in SKIP_FROM_MISMATCH:
            continue
        if dll_name == VCRUNTIME140_1_KEY:
            msvcp_fam = family_map.get("msvcp140.dll", "")
            if msvcp_fam not in ("VS2019", "VS2022"):
                continue
        if res.get("matched_ref"):
            fam = _version_family(res["matched_ref"]["version"])
            if fam:
                family_map[dll_name] = fam

    unique_families = set(family_map.values())
    if len(unique_families) > 1:
        family_list = ", ".join(f"{k}: {v}" for k, v in family_map.items())
        mismatch_msg = (
            f"VC++ runtime generation mismatch detected: [{family_list}]. "
            "All VC++ 140-family DLLs should come from the same Visual Studio generation. "
            "A mismatch across generations (e.g. VS2017 vs VS2022) indicates a partial "
            "update, corrupted install, or deliberate replacement of one DLL. "
            "This can cause crashes and is worth investigating."
        )
        if msvcp140_result and "msvcp140.dll" in family_map:
            msvcp140_result["issues"].append(mismatch_msg)
            if msvcp140_result["verdict"] == "OK":
                msvcp140_result["verdict"] = "SUSPICIOUS"
                msvcp140_result["verdict_colour"] = YELLOW
        for dll_name, res in runtime_results.items():
            if dll_name in family_map:
                res["issues"].append(mismatch_msg)
                if res["verdict"] == "OK":
                    res["verdict"] = "SUSPICIOUS"
                    res["verdict_colour"] = YELLOW

    lines = []
    if msvcp140_result:
        v = msvcp140_result["verdict"]
        lines.append(f"MSVCP140.dll : {v}")
        if msvcp140_result["matched_ref"]:
            lines.append(f"  Matched ref : {msvcp140_result['matched_ref']['version']}")
        for iss in msvcp140_result["issues"]:
            lines.append(f"  ⚠ {iss}")
    else:
        lines.append("MSVCP140.dll : NOT FOUND in module list")

    if discord_results:
        for dr in discord_results:
            lines.append(f"{dr['name']} : {dr['verdict']}")
            if dr["matched_ref"]:
                lines.append(f"  Matched ref : {dr['matched_ref']['version']}")
            for iss in dr["issues"]:
                lines.append(f"  ⚠ {iss}")
    else:
        lines.append("Discord RPC / Game SDK : NOT FOUND in module list")

    for dll_name, res in runtime_results.items():
        v = res["verdict"]
        lines.append(f"{res['name']} : {v}")
        if res.get("matched_ref"):
            lines.append(f"  Matched ref : {res['matched_ref']['version']}")
        for iss in res["issues"]:
            lines.append(f"  ⚠ {iss}")
    for sn in RUNTIME_DLL_REGISTRY:
        if sn not in runtime_results:
            lines.append(f"{sn} : NOT FOUND in module list")

    return {
        "msvcp140": msvcp140_result,
        "discord":  discord_results,
        "runtime":  runtime_results,
        "summary":  "\n".join(lines),
    }


def annotate_frame(mod_name: str, offset: int) -> str:

    n = (mod_name or "").lower()

    if n in ("ntdll.dll",):
        return "Windows NT kernel interface"
    if n in ("kernel32.dll", "kernelbase.dll"):
        return "Windows core API"
    if n in ("ucrtbase.dll", "msvcp_win.dll", "msvcp140.dll", "vcruntime140.dll"):
        return "C/C++ runtime"
    if n in ("combase.dll", "ole32.dll", "oleaut32.dll"):
        return "Windows COM runtime"
    if n in ("rpcrt4.dll",):
        return "Windows RPC (remote procedure call)"
    if n in ("coremessaging.dll", "user32.dll", "win32u.dll"):
        return "Windows message / UI"
    if n in ("ws2_32.dll", "winhttp.dll", "wininet.dll", "dnsapi.dll"):
        return "Windows networking"
    if n in ("crypt32.dll", "bcryptprimitives.dll", "ncrypt.dll"):
        return "Windows cryptography"
    if n in ("dbgcore.dll", "dbghelp.dll"):
        return "Windows debug helper"
    if n in ("audioses.dll", "mmdevapi.dll"):
        return "Windows audio session"

    if n in ("d3d12.dll", "d3d12core.dll"):
        return "Direct3D 12 runtime"
    if n in ("d3d11.dll",):
        return "Direct3D 11 runtime"
    if n in ("dxgi.dll",):
        return "DXGI (swap chain / display)"
    if n in ("dxcore.dll",):
        return "DXCore adapter enumeration"
    if n in ("d3dcompiler_47.dll", "dxcompiler.dll"):
        return "DirectX shader compiler"
    if "amdxx" in n or "atidxx" in n:
        return "AMD GPU driver - DX11 user-mode"
    if "amdxc" in n:
        return "AMD GPU driver - DX12 shader compiler"
    if "amdihk" in n:
        return "AMD GPU driver - hook/intercept layer"
    if "amdcc" in n:
        return "AMD GPU driver - Chill/Crossfire/Compute"
    if "nvwgf" in n or "nvd3dum" in n:
        return "NVIDIA GPU driver - DirectX user-mode"
    if "igdumd" in n or "igxelp" in n:
        return "Intel GPU driver"

    if "dstoragecore" in n:
        return "DirectStorage core - GPU asset streaming"
    if "dstorage" in n:
        return "DirectStorage - fast asset streaming"

    if "wwise" in n:
        return "Wwise audio engine"
    if "fmod" in n:
        return "FMOD audio engine"
    if "xaudio" in n:
        return "XAudio2 (DirectX audio)"

    if "steam_api" in n or "steamclient" in n:
        return "Steam API"
    if "gameoverlayrenderer" in n:
        return "Steam overlay renderer"
    if "gameinputredist" in n:
        return "GameInput (controller input)"

    if "npggnt" in n or "npsc" in n or "gameguard" in n:
        return "GameGuard anti-cheat"
    if "easyanticheat" in n:
        return "EasyAntiCheat"
    if "battleye" in n:
        return "BattlEye anti-cheat"

    if "crs-client" in n:
        return "Arrowhead crash reporter"
    if "crashpad" in n:
        return "Crashpad crash reporter"
    if "sentry" in n:
        return "Sentry crash reporter"

    if "lua" in n:
        return "Lua scripting runtime"

    if "physx" in n or "nvphys" in n:
        return "NVIDIA PhysX"

    if "network" in n or "enet" in n or "raknet" in n:
        return "Game networking layer"

    if "concrt140" in n or "msvcp140_1" in n or "msvcp140_2" in n:
        return "C++ runtime (parallel/STL)"
    if "vcruntime140_1" in n:
        return "C/C++ runtime (coroutine support)"

    if "wwise" in n:
        return "Wwise audio engine / plugin"
    if "fmodstudio" in n or ("fmod" in n and "64" in n):
        return "FMOD Studio audio engine"
    if "xaudio" in n or "x3daudio" in n:
        return "XAudio2 / X3DAudio (DirectX audio)"

    if "easyanticheat" in n:
        return "EasyAntiCheat"
    if "battleye" in n or "beclient" in n:
        return "BattlEye anti-cheat"

    if "nvapi" in n:
        return "NVIDIA API (NVAPI) utility layer"
    if "amd_ags" in n:
        return "AMD GPU Services (AGS) utility layer"

    if "dxcompiler" in n:
        return "DirectX shader compiler (DXC)"
    if n == "dxil.dll":
        return "DirectX Intermediate Language validator"

    if "winpixeventruntime" in n:
        return "WinPIX GPU event runtime (profiler)"

    if "playfabmultiplayerwin" in n:
        return "PlayFab multiplayer SDK"
    if "partywin" in n:
        return "Xbox Party SDK"
    if "xinput" in n:
        return "XInput (Xbox controller)"
    if n in ("hid.dll", "hidclass.dll"):
        return "Windows HID (input device)"

    if "amd_fidelityfx" in n:
        return "AMD FidelityFX / FSR upscaler"
    if "libxess" in n:
        return "Intel XeSS AI upscaler"

    if "nvspcap" in n:
        return "NVIDIA ShadowPlay / screen capture"
    if "nvgpucomp" in n:
        return "NVIDIA GPU compute user-mode driver"
    if "nvldumd" in n:
        return "NVIDIA DirectX UMD loader"
    if "nvppex" in n:
        return "NVIDIA post-processing extensions"
    if "nvmemmapsto" in n:
        return "NVIDIA memory-mapped storage"
    if "nvmessagebus" in n:
        return "NVIDIA driver message bus (IPC)"

    if "d3d11on12" in n:
        return "D3D11-on-D3D12 compatibility layer"
    if "dxilconv" in n:
        return "DXIL shader bytecode converter"
    if "d3dscache" in n or "d3dscache" in n:
        return "D3D shader cache"

    if "msvcr110" in n or "msvcr120" in n or "msvcr100" in n:
        return "Legacy MSVC C runtime (2010–2013)"

    if "reshade" in n:
        return "ReShade post-processing (D3D hook)"
    if "minhook" in n or "minhook64" in n:
        return "MinHook (function hooking library - possible mod injection)"

    if "crs-client" in n:
        return "Arrowhead crash reporter"

    if n.endswith(".exe"):
        return "Game engine / application code"

    if "game" in n and n.endswith(".dll"):
        return "Game code DLL"

    return ""


def label_thread_purpose(stack_mod_names: list) -> tuple[str, str]:
    mods = set(n.lower() for n in stack_mod_names if n)

    def has(*keywords):
        return any(any(kw in m for kw in keywords) for m in mods)

    if has("crs-client", "crashpad", "sentry", "backtrace"):
        return "Crash reporter", "handler"
    if has("npggnt", "npsc64"):
        return "GameGuard (anti-cheat)", "system"
    if has("easyanticheat"):
        return "EasyAntiCheat", "system"
    if has("battleye", "beclient"):
        return "BattlEye", "system"
    if has("wwise"):
        return "Wwise audio", "audio"
    if has("fmodstudio", "fmod64", "fmodl64"):
        return "FMOD audio", "audio"
    if has("xaudio2", "audioses", "x3daudio"):
        return "XAudio2 audio", "audio"
    if has("windows.media.devices", "mmdevapi"):
        return "Audio device manager", "audio"
    if has("nvwgf2umx", "nvwgf2um", "nvd3dumx", "nvd3dum"):
        return "GPU render (NVIDIA)", "gpu"
    if has("amdxc64", "amdxc32", "amdxx64", "amdxx32", "atidxx64", "atidxx32", "amdcc64", "amdcc"):
        return "GPU render (AMD)", "gpu"
    if has("igd10um", "igdumd64", "igxelpicd64"):
        return "GPU render (Intel)", "gpu"
    if has("igc64", "igdgmm64"):
        return "GPU render (Intel)", "gpu"
    if has("nvmessagebus", "nvgpucomp"):
        return "NVIDIA driver worker", "gpu"
    if has("d3d11on12"):
        return "D3D11-on-D3D12 worker", "gpu"
    if has("dstorage"):
        return "DirectStorage", "dstorage"
    if has("gameinputredist"):
        return "GameInput (controller)", "input"
    if has("xinput"):
        return "XInput (controller)", "input"
    if has("inputhost", "coremessaging"):
        return "Input / UI message pump", "input"
    if has("playfabmultiplayerwin"):
        return "PlayFab multiplayer", "network"
    if has("partywin"):
        return "Xbox Party SDK", "network"
    if has("steam_api", "steamclient"):
        return "Steam", "network"
    if has("winhttp", "urlmon"):
        return "HTTP / telemetry", "network"
    if has("mswsock", "ws2_32", "dnsapi"):
        return "Socket / network", "network"
    if has("crypt32", "ncrypt", "bcryptprimitives"):
        return "Crypto / TLS", "network"
    if has("bink2w64", "bink2w32"):
        return "Bink video decoder", "video"
    if has("helldivers2.exe", "game.dll"):
        return "Game worker thread", "game"

    return "OS thread pool", "system"


def walk_stack(parsed: dict, rsp: int, max_frames: int = 20) -> list:

    modules  = parsed.get("modules", [])
    raw_path = parsed.get("_raw_path")
    if not raw_path or not rsp:
        return []
    try:
        with open(raw_path, "rb") as f:
            raw = f.read()
    except Exception:
        return []

    def read_u64(addr: int):
        for (start, msz, rva) in parsed.get("memory_map", []):
            if start <= addr < start + msz:
                off = addr - start
                if rva + off + 8 <= len(raw):
                    return struct.unpack_from("<Q", raw, rva + off)[0]
        return None

    def addr_to_mod(addr: int):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name, addr - base
            except Exception:
                pass
        return None, 0

    frames = []
    ptr    = rsp
    scanned = 0
    while len(frames) < max_frames and scanned < 0x2000:
        val = read_u64(ptr)
        if val is None:
            break
        mod, off = addr_to_mod(val)
        if mod:
            frames.append((val, mod, off))
        ptr     += 8
        scanned += 8
    return frames

def analyse_threads(parsed: dict) -> list:

    NTDLL_WAITS = {
        0x161B14: ("NtWaitForSingleObject",         "Waiting on event / mutex / semaphore"),
        0x1656E4: ("NtWaitForWorkViaWorkerFactory",  "Thread pool worker - idle"),
        0x1625E4: ("NtDelayExecution",               "Sleeping (Sleep / SleepEx)"),
        0x165744: ("NtRemoveIoCompletion",           "Waiting on I/O completion port"),
        0x162114: ("NtWaitForMultipleObjects",       "Waiting on multiple handles"),
        0x162C44: ("NtSignalAndWaitForSingleObject", "Signal-and-wait (lock handoff)"),
        0x1639E4: ("NtRaiseException",               "Raising exception - crash point"),
        0x160B54: ("NtDelayExecution",               "Sleeping"),
        0x161584: ("NtWaitForSingleObject",          "Waiting on event / mutex / semaphore"),
    }
    CRASH_HANDLER_DLLS = {
        "crs-client.dll":       "Arrowhead crash reporter",
        "crashpad_handler.exe": "Crashpad crash reporter",
        "crashrpt.dll":         "CrashRpt reporter",
        "sentry.dll":           "Sentry crash reporter",
        "backtrace.dll":        "Backtrace crash reporter",
    }

    modules   = parsed.get("modules", [])
    threads   = parsed.get("threads", [])
    crash_tid = (parsed.get("exception") or {}).get("thread_id")

    ntdll_base = None
    for m in modules:
        if PureWindowsPath(m["name"]).name.lower() == "ntdll.dll":
            try:
                ntdll_base = int(m["base"], 16)
            except Exception:
                pass
            break

    def rip_to_module(rip):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= rip < base + m["size"]:
                    return m["name"], PureWindowsPath(m["name"]).name, rip - base
            except Exception:
                pass
        return None, None, 0

    result = []
    for t in threads:
        rip     = t.get("rip", 0)
        suspend = t.get("suspend", 0)
        pri     = t.get("pri", 0)
        tid     = t["tid"]

        full_name, short_name, offset = rip_to_module(rip)
        full_lower = (full_name or "").lower().replace("/", "\\")
        is_system  = "\\windows\\" in full_lower or "\\microsoft" in full_lower
        short_lower = (short_name or "").lower()
        is_handler  = short_lower in CRASH_HANDLER_DLLS
        is_game     = bool(full_name) and not is_system and not is_handler

        wait_label  = None
        wait_detail = None
        if ntdll_base and short_name and "ntdll" in short_lower:
            ntdll_off = rip - ntdll_base
            if ntdll_off in NTDLL_WAITS:
                wait_label, wait_detail = NTDLL_WAITS[ntdll_off]

        is_crashed  = tid == crash_tid
        real_suspend = suspend if 0 < suspend <= 16 else 0

        if is_crashed:
            state = "CRASHED"
        elif is_handler:
            state = "CRASH HANDLER"
        elif real_suspend > 0:
            state = f"SUSPENDED (count={real_suspend})"
        elif wait_label == "NtDelayExecution" or wait_label and "sleeping" in wait_label.lower():
            state = "SLEEPING"
        elif wait_label and "idle" in wait_detail.lower() if wait_detail else False:
            state = "IDLE"
        elif wait_label:
            state = "WAITING"
        elif is_game:
            state = "ACTIVE"
        else:
            state = "WAITING"

        if is_crashed:
            _ex     = parsed.get("exception", {}) or {}
            _code   = int(_ex.get("code", "0"), 16) if _ex else 0
            _params = _ex.get("params", [])
            _suicide = (_code == 0xC0000005 and len(_params) >= 2
                        and _params[0] == "0x1" and _params[1] == "0x0")
            doing = ("Raised the crash exception - engine suicide (intentional write to null)"
                     if _suicide else
                     "Raised the crash exception - see Root Cause tab for details")
        elif is_handler:
            doing = f"{CRASH_HANDLER_DLLS[short_lower]} - byproduct of crash"
        elif wait_detail:
            doing = wait_detail
        elif is_game:
            doing = f"Executing game code in {short_name} +0x{offset:X}"
        elif is_system:
            doing = f"In system call ({short_name} +0x{offset:X})"
        else:
            doing = f"{short_name or 'unknown'} +0x{offset:X}"

        frames = walk_stack(parsed, t.get("rsp", 0), max_frames=16)
        all_frames = [(t.get("rip", 0), short_name or "unknown", offset)] + frames


        all_stack_mods = ([short_name] if short_name else []) + [mod for _, mod, _ in frames]
        purpose, purpose_colour_key = label_thread_purpose(all_stack_mods)

        if is_crashed:
            purpose = ""

        result.append({
            "tid":               tid,
            "state":             state,
            "doing":             doing,
            "purpose":           purpose,
            "purpose_colour_key":purpose_colour_key,
            "module":            short_name or "unknown",
            "offset":            f"+0x{offset:X}",
            "rip":               f"0x{rip:016X}",
            "priority":          pri,
            "suspend":           suspend,
            "is_crashed":        is_crashed,
            "is_game":           is_game,
            "is_handler":        is_handler,
            "is_system":         is_system,
            "wait_label":        wait_label,
            "frames":            all_frames,
        })

    def sort_key(t):
        if t["is_crashed"]:   return 0
        if t["is_game"]:      return 1
        if t["is_handler"]:   return 2
        return 3

    result.sort(key=sort_key)
    return result



def _detect_recursion(parsed: dict) -> str:
    ex        = parsed.get("exception", {}) or {}
    ex_regs   = ex.get("regs", {})
    crash_rsp = ex_regs.get("rsp", 0)
    modules   = parsed.get("modules", [])
    raw_path  = parsed.get("_raw_path")
    memory_map = parsed.get("memory_map", [])

    if not crash_rsp or not raw_path:
        return ("Could be: infinite recursion in Lua or C++, extremely deep call chain during level load, "
                "or a very large stack allocation inside a function.")
    try:
        with open(raw_path, "rb") as f:
            raw = f.read()
    except Exception:
        return "Could not read dump memory to detect recursion pattern."

    def read_u64(addr):
        return _read_u64_mem(raw, memory_map, addr)

    def addr_to_mod(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name, addr - base
            except Exception:
                pass
        return None, 0

    addr_counts: dict = {}
    ptr = crash_rsp
    for _ in range(1024):
        val = read_u64(ptr)
        if val is None:
            break
        mod, off = addr_to_mod(val)
        if mod and off > 0:
            key = (mod, off)
            addr_counts[key] = addr_counts.get(key, 0) + 1
        ptr += 8

    if not addr_counts:
        return ("Stack overflow - no readable stack data. "
                "Likely infinite recursion but could not identify the function.")

    top = sorted(addr_counts.items(), key=lambda x: x[1], reverse=True)
    (top_mod, top_off), top_count = top[0]

    if top_count >= 3:
        pattern_desc = ""
        if len(top) >= 2:
            (second_mod, second_off), second_count = top[1]
            if second_count >= 2:
                pattern_desc = (f" The recursion involves at least two frames: "
                                f"{top_mod}+0x{top_off:X} (×{top_count}) "
                                f"calling back to {second_mod}+0x{second_off:X} (×{second_count}).")

        return (f"Infinite recursion detected - {top_mod}+0x{top_off:X} appears {top_count} times "
                f"on the stack, indicating a function calling itself repeatedly.{pattern_desc} "
                f"The module and offset are shown above - share this dump with the development team for resolution.")
    else:
        most_common = f"{top_mod}+0x{top_off:X}" if top_mod else "unknown"
        return (f"Stack overflow - no single function dominates the stack (most common frame: "
                f"{most_common} ×{top_count}). "
                f"May be an extremely deep call chain rather than circular recursion, "
                f"or a very large stack-allocated buffer inside a function. "
                f"Check the Threads tab for the crash thread's full stack.")


def _find_dll_init_suspect(parsed: dict) -> str:
    ex       = parsed.get("exception", {}) or {}
    modules  = parsed.get("modules", [])
    ex_addr  = int(ex.get("address", "0"), 16) if ex else 0

    if ex_addr:
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= ex_addr < base + m["size"]:
                    name = PureWindowsPath(m["name"]).name
                    off  = ex_addr - base
                    return (f"The crash address (0x{ex_addr:016X}) landed inside {name} +0x{off:X}. "
                            f"This is the DLL whose DllMain failed or threw an exception. "
                            f"Common causes: missing dependency DLL, corrupted installation, "
                            f"incompatible Visual C++ redistributable version, or a DLL that "
                            f"calls into another DLL that isn\'t loaded yet.")
            except Exception:
                pass

    mod_names_lower = {PureWindowsPath(m["name"]).name.lower() for m in modules}

    missing = []
    if "msvcp140.dll" not in mod_names_lower and "vcruntime140.dll" not in mod_names_lower:
        missing.append("MSVCP140.dll / VCRUNTIME140.dll (Visual C++ 2015-2022 Redistributable)")
    if "ucrtbase.dll" not in mod_names_lower:
        missing.append("ucrtbase.dll (Windows Universal CRT - may need Windows Update)")

    if missing:
        return (f"No specific DLL was identified from the crash address. "
                f"However, the following expected runtime DLLs are absent from the module list: "
                f"{', '.join(missing)}. "
                f"A missing dependency is a common cause of DLL_INIT_FAILED - the game DLL loads "
                f"but its imports can\'t be resolved because a required DLL isn\'t present. "
                f"Install the Visual C++ 2015-2022 Redistributable and run Windows Update.")

    suspicious = []
    for m in modules:
        path = m["name"].lower().replace("/", "\\")
        name = PureWindowsPath(m["name"]).name.lower()
        if "\\temp\\" in path or "\\downloads\\" in path:
            suspicious.append(PureWindowsPath(m["name"]).name)

    if suspicious:
        return (f"Suspicious DLL load paths detected: {', '.join(suspicious)}. "
                f"DLLs loaded from Temp or Downloads during game init suggest a corrupted "
                f"or tampered installation. Verify game files and reinstall if the issue persists.")

    return (f"Could not identify the specific failing DLL from dump data alone. "
            f"Common causes: corrupted game file, missing Visual C++ Redistributable, "
            f"incompatible third-party DLL injected at startup, or a Windows Update "
            f"that broke a system DLL dependency. "
            f"Check the Windows Event Log (Application) for DLL load failure entries "
            f"that occurred at the same time as the crash.")


def parse_dred_log(path: str) -> dict:
    import re

    result = {
        "removal_reason_code": None,
        "removal_reason_name": None,
        "removal_reason_desc": None,
        "removal_reason_fix":  None,
        "queues":              [],
        "page_fault_addr":     None,
        "page_fault_ambiguous": False,
        "_raw_path": path,
    }

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        result["_error"] = str(e)
        return result

    if lines:
        m = re.search(r"reason:\s*(\S+)\s*\((?:0x)?([0-9A-Fa-f]+)\)", lines[0])
        if m:
            result["removal_reason_name"] = m.group(1).rstrip(".")
            result["removal_reason_code"] = "0x" + m.group(2).upper()
            entry = DXGI_REMOVAL_REASONS.get(result["removal_reason_code"], (None, None, None))
            result["removal_reason_desc"] = entry[1] or "Unknown device removed reason."
            result["removal_reason_fix"]  = entry[2] or (
                "This DXGI error code isn't in the analyzer's reference table yet. "
                "Share this log with the development team for investigation."
            )

    if lines:
        m = re.search(r"DRED page fault address\s+([0-9A-Fa-f]+)", lines[-1])
        if m:
            addr_str = m.group(1)
            addr_int = int(addr_str, 16)
            result["page_fault_addr"] = f"0x{addr_int:016X}"
            result["page_fault_ambiguous"] = (addr_int == 0)

    dred_api_errors = []
    for line in lines:
        m = re.search(r"Failed to get DRED\s+(.+?):\s*(?:0x)?([0-9A-Fa-f]+)", line, re.IGNORECASE)
        if m:
            what_failed = m.group(1).strip().rstrip(".")
            err_code = "0x" + m.group(2).upper()
            dred_api_errors.append({"what": what_failed, "code": err_code})
    if dred_api_errors:
        result["dred_api_errors"] = dred_api_errors

    queue_idx    = -1
    current_q    = None
    QUEUE_RE     = re.compile(
        r"^Queue:.*last crumb:\s*[0-9A-Fa-f]+=(\d+)\.\s*"
        r"Crumb count=(\d+),\s*Context count=(\d+)"
    )
    CRUMB_RE     = re.compile(r"^\tCrumb:\s*(\d+)\s*\|\s*(\d+)")
    CONTEXT_RE   = re.compile(r"^\tCrumb index context:\s*(\d+)\s*\|\s*(.+)")

    for line in lines[1:]:
        mq = QUEUE_RE.match(line)
        if mq:
            if current_q is not None:
                result["queues"].append(current_q)
            queue_idx += 1
            current_q = {
                "index":          queue_idx,
                "last_completed": int(mq.group(1)),
                "crumb_count":    int(mq.group(2)),
                "context_count":  int(mq.group(3)),
                "crumbs":         [],
                "contexts":       {},
                "incomplete":     False,
                "hang_op_index":  None,
                "hang_op_name":   None,
                "hang_op_context":[],
            }
            continue

        if current_q is None:
            continue

        mc = CRUMB_RE.match(line)
        if mc:
            crumb_idx  = int(mc.group(1))
            opcode_int = int(mc.group(2))
            op_name    = D3D12_BREADCRUMB_OPS.get(opcode_int, f"UNKNOWN_OP_{opcode_int}")
            current_q["crumbs"].append((crumb_idx, opcode_int, op_name))
            continue

        mctx = CONTEXT_RE.match(line)
        if mctx:
            ctx_idx   = int(mctx.group(1))
            ctx_label = mctx.group(2).strip()
            current_q["contexts"].setdefault(ctx_idx, []).append(ctx_label)

    if current_q is not None:
        result["queues"].append(current_q)

    for q in result["queues"]:
        last = q["last_completed"]
        total = q["crumb_count"]
        if total > 0 and last < total - 1:
            q["incomplete"] = True
            hang_idx = last + 1
            q["hang_op_index"] = hang_idx
            for (ci, op_int, op_name) in q["crumbs"]:
                if ci == hang_idx:
                    q["hang_op_name"] = op_name
                    break
            else:
                q["hang_op_name"] = f"op at crumb index {hang_idx}"
            for check_idx in range(hang_idx, -1, -1):
                if check_idx in q["contexts"]:
                    q["hang_op_context"] = q["contexts"][check_idx]
                    break

    return result


def assess_dred(parsed_dred: dict) -> dict:

    queues    = parsed_dred.get("queues", [])
    r_code    = parsed_dred.get("removal_reason_code", "?")
    r_name    = parsed_dred.get("removal_reason_name", "?")
    r_desc    = parsed_dred.get("removal_reason_desc", "")
    r_fix     = parsed_dred.get("removal_reason_fix", "")
    pf_addr   = parsed_dred.get("page_fault_addr")
    pf_ambig  = parsed_dred.get("page_fault_ambiguous", True)

    incomplete = [q for q in queues if q["incomplete"]]
    findings   = []

    findings.append({
        "conf":   "HIGH",
        "title":  f"GPU {r_name} ({r_code})",
        "detail": r_desc,
    })

    if r_fix:
        findings.append({
            "conf":   "HIGH",
            "title":  "How to fix this",
            "detail": r_fix,
        })

    if pf_addr and not pf_ambig:
        findings.append({
            "conf":   "HIGH",
            "title":  f"GPU Page Fault at {pf_addr}",
            "detail": ("The GPU attempted to access a virtual address that was not mapped or had "
                       "been freed. This is equivalent to a CPU null-pointer dereference but on the "
                       "GPU side. Common causes: a shader read/wrote a descriptor pointing to a "
                       "resource that had been released, or a GPU buffer was freed while still in use."),
        })
    elif pf_addr and pf_ambig:
        findings.append({
            "conf":   "LOW",
            "title":  "Page fault address is 0x0 (ambiguous)",
            "detail": ("The DRED page fault address field is zero, which the format itself notes may "
                       "mean either no page fault occurred, or a fault at address 0 (a real null GPU "
                       "virtual address). Without additional D3D12 debug layer output this cannot be "
                       "resolved. Focus on the breadcrumb evidence instead."),
        })

    culprit_queue = None
    culprit_conf  = "LOW"
    if not queues:
        reason_code = parsed_dred.get("removal_reason_code", "")
        dred_errors = parsed_dred.get("dred_api_errors", [])
        has_dred_error = bool(dred_errors)
        
        if reason_code == "0x887A0005":
            culprit_summary = (
                "The GPU was physically removed, powered off, or reset by the OS/driver. "
                "No breadcrumb data is available because DRED captures the last GPU commands "
                "before a HANG - when the GPU is REMOVED (not hung), there are no 'last commands' "
                "to capture. This is expected for DEVICE_REMOVED and confirms the GPU vanished "
                "rather than getting stuck on a command."
            )
            if has_dred_error:
                culprit_summary += (
                    f"\n\nThe DRED API explicitly reported it has no data (error code(s): "
                    f"{', '.join(e['code'] for e in dred_errors)}). This is the DRED API correctly "
                    f"reporting 'nothing to capture for this removal type', NOT an additional error."
                )
            culprit_summary += (
                "\n\nThis is almost certainly a HARDWARE or DRIVER issue, not a game bug. "
                "The GPU disappeared entirely - update drivers, check temps, reseat the card."
            )
        elif reason_code == "0x887A0001":
            culprit_summary = (
                "The game made an invalid D3D12 API call. No breadcrumb data is available "
                "because the device was removed due to an illegal API usage, not a GPU hang. "
                "This points to a game-side bug calling a D3D12 function incorrectly."
            )
        else:
            culprit_summary = (
                "This DRED log contains no breadcrumb queue data at all - the GPU driver didn't record any "
                "in-flight GPU commands at the time of removal. This is normal for some removal reasons "
                "(e.g. an invalid API call, or a clean device loss) and doesn't necessarily mean anything was "
                "stuck. The removal reason above is the main signal in this case."
            )
            if has_dred_error:
                culprit_summary += (
                    f"\n\nDRED API reported no data available (error code(s): "
                    f"{', '.join(e['code'] for e in dred_errors)})."
                )
    else:
        culprit_summary = (
            "All recorded queues completed their work - no incomplete breadcrumbs found. "
            "If the GPU still hung or was removed, the cause likely lies outside what DRED breadcrumbs "
            "capture (e.g. a driver-internal issue, or a hang that occurred between recorded operations)."
        )

    if incomplete:
        def queue_score(q):
            op_risk    = {"HIGH": 3, "MED": 2, "LOW": 1}.get(
                D3D12_HANG_RISK.get(q.get("hang_op_name", ""), "LOW"), 1)
            has_ctx    = 1 if q.get("hang_op_context") else 0
            return (op_risk * 10000 + has_ctx * 5000 + q["crumb_count"])

        ranked = sorted(incomplete, key=queue_score, reverse=True)
        culprit_queue = ranked[0]
        hop  = culprit_queue.get("hang_op_name", "unknown op")
        hctx = culprit_queue.get("hang_op_context", [])
        risk = D3D12_HANG_RISK.get(hop, "LOW")

        ctx_str = f" in the '{hctx[0]}' render pass" if hctx else ""
        no_ctx_note = ""
        if not hctx:
            named_candidates = [q for q in incomplete if q.get("hang_op_context")]
            if named_candidates:
                best_named = max(named_candidates,
                                 key=lambda q: q["crumb_count"])
                bn_ctx = best_named["hang_op_context"][0]
                bn_op  = best_named.get("hang_op_name", "?")
                no_ctx_note = (
                    f" This queue has no render-pass name attached (the engine didn't tag this "
                    f"command list with a debug event/marker), so only the GPU operation type is "
                    f"identifiable here. For reference, the most active NAMED incomplete queue was "
                    f"'{bn_ctx}' (queue {best_named['index']}, {bn_op}) - it scored lower because its "
                    f"operation type is less commonly associated with hangs, but it may still be "
                    f"worth checking if this doesn't reproduce reliably."
                )
            else:
                no_ctx_note = (
                    " None of the incomplete queues in this log have a render-pass name attached - "
                    "the engine didn't tag any of these command lists with debug event/marker names, "
                    "so only the GPU operation type is identifiable, not which part of the frame it "
                    "belongs to."
                )
        last_c  = culprit_queue["last_completed"]
        total_c = culprit_queue["crumb_count"]

        if risk == "HIGH" and len(incomplete) == 1:
            culprit_conf = "HIGH"
            culprit_summary = (
                f"GPU hung during {hop}{ctx_str}. "
                f"This operation type is a common hang source - it runs GPU shader code directly "
                f"and can stall indefinitely if a shader enters an infinite loop, "
                f"or if a fence/barrier dependency is never satisfied. "
                f"Breadcrumbs show {last_c} of {total_c} operations completed in this queue."
                f"{no_ctx_note}"
            )
        elif risk == "HIGH":
            culprit_conf = "MED"
            culprit_summary = (
                f"Most likely queue: GPU hung during {hop}{ctx_str} "
                f"({last_c}/{total_c} ops completed). "
                f"Multiple queues were incomplete - this queue is ranked highest by operation "
                f"type and breadcrumb count, but another queue submitting work concurrently "
                f"may have been the root cause."
                f"{no_ctx_note}"
            )
        elif risk == "MED":
            culprit_conf = "MED"
            culprit_summary = (
                f"GPU appears stuck during {hop}{ctx_str} "
                f"({last_c}/{total_c} ops completed). "
                f"This operation type can hang if a GPU resource is in an unexpected state "
                f"or if a previous operation left the pipeline stalled."
                f"{no_ctx_note}"
            )
        else:
            culprit_conf = "LOW"
            culprit_summary = (
                f"Last operation before hang: {hop}{ctx_str} "
                f"({last_c}/{total_c} ops completed). "
                f"This operation type is unlikely to cause a hang on its own - the real cause "
                f"may be in an earlier operation that stalled the GPU, or in a parallel queue."
                f"{no_ctx_note}"
            )

        findings.append({
            "conf":   culprit_conf,
            "title":  f"Likely hang point: {hop}{ctx_str}",
            "detail": culprit_summary,
        })

        if hctx:
            ctx_lower = hctx[0].lower()
            settings_hint = None
            if any(k in ctx_lower for k in ("raytrac", "rt_", "_rt", "dxr")):
                settings_hint = ("Try disabling Ray Tracing in graphics settings - ray tracing shaders "
                                 "are among the most likely to hang on driver bugs or edge-case scene data.")
            elif "shadow" in ctx_lower or "cascade" in ctx_lower:
                settings_hint = ("Try lowering Shadow Quality or Shadow Distance in graphics settings - "
                                 "this won't fix the underlying bug but may avoid triggering the specific "
                                 "shadow-map code path that hung.")
            elif "cubemap" in ctx_lower or "reflect" in ctx_lower or "probe" in ctx_lower:
                settings_hint = ("Try lowering Reflection Quality or disabling real-time reflections/"
                                 "environment probes in graphics settings, since this hang happened during "
                                 "a cubemap/reflection capture pass.")
            elif "ssao" in ctx_lower or "ambient" in ctx_lower:
                settings_hint = ("Try disabling Ambient Occlusion (SSAO) in graphics settings.")
            elif "particle" in ctx_lower or "vfx" in ctx_lower:
                settings_hint = ("Try lowering Effects/Particle Quality in graphics settings - this hang "
                                 "happened during a particle/VFX compute pass.")
            elif "water" in ctx_lower:
                settings_hint = ("Try lowering Water/Ocean Quality in graphics settings.")
            elif "dispatch" in hop.lower() or "DISPATCH" in hop:
                settings_hint = ("This was a compute shader dispatch - if a specific graphics setting "
                                 "correlates with this render pass name, lowering it may avoid the hang "
                                 "as a temporary workaround.")

            if settings_hint:
                findings.append({
                    "conf":   "MED",
                    "title":  "Workaround to try",
                    "detail": settings_hint + " This is a workaround, not a fix - report the render pass "
                              "name and this DRED log to the development team so the underlying cause "
                              "can be addressed.",
                })

        others = [q for q in ranked[1:] if q["incomplete"]]
        if others:
            lines_out = []
            for q in others:
                hop2  = q.get("hang_op_name", "?")
                hctx2 = q.get("hang_op_context", [])
                ctx2  = f" in '{hctx2[0]}'" if hctx2 else ""
                lines_out.append(
                    f"Queue {q['index']}: {hop2}{ctx2} "
                    f"({q['last_completed']}/{q['crumb_count']} ops completed)"
                )
            findings.append({
                "conf":   "LOW",
                "title":  f"{len(others)} additional incomplete queue(s)",
                "detail": ("These queues also had unfinished work at the time of the hang, "
                           "suggesting multiple command lists were in flight simultaneously. "
                           "Full list:\n" + "\n".join(lines_out)),
            })

    return {
        "reason_code":      r_code,
        "reason_name":      r_name,
        "reason_desc":      r_desc,
        "reason_fix":       r_fix,
        "culprit_queue":    culprit_queue,
        "culprit_conf":     culprit_conf,
        "culprit_summary":  culprit_summary,
        "incomplete_queues": incomplete,
        "all_queues":       queues,
        "page_fault_addr":  pf_addr,
        "page_fault_ambiguous": pf_ambig,
        "findings":         findings,
    }


def quick_patterns(parsed: dict) -> list[tuple[str, str, str, str]]:

    hints = []
    modules   = parsed.get("modules", [])
    all_names = " ".join(PureWindowsPath(m["name"]).name.lower() for m in modules)

    has_dstorage = "dstorage" in all_names


    GPU_DRIVER_DLLS = {
        "amdxc64.dll":    "AMD GPU driver (DX12 shader compiler)",
        "amdxx64.dll":    "AMD GPU driver (DX11 runtime)",
        "amdihk64.dll":   "AMD GPU driver (hook layer)",
        "atidxx64.dll":   "AMD GPU driver (legacy DX)",
        "nvwgf2umx.dll":  "NVIDIA GPU driver (DX12/DX11 UMD)",
        "nvd3dumx.dll":   "NVIDIA GPU driver (DX UMD)",
        "nvoglv64.dll":   "NVIDIA OpenGL driver",
        "igdumd64.dll":   "Intel GPU driver",
        "igdumdim64.dll": "Intel GPU driver (media)",
        "igxelpicd64.dll":"Intel Arc GPU driver",
        "igd10um64gen11.dll": "Intel GPU driver (Gen11)",
        "igd10iumd64.dll":"Intel GPU driver (media UMD)",
        "igdgmm64.dll":   "Intel GPU memory manager",
        "igc64.dll":      "Intel GPU shader compiler",
        "igd12dxva64.dll":"Intel GPU DXVA (video accel)",
        "nvgpucomp64.dll":"NVIDIA GPU compute UMD",
        "nvldumdx.dll":   "NVIDIA DX UMD loader",
        "nvppex.dll":     "NVIDIA post-processing extensions",
        "amdcc64.dll":    "AMD GPU driver (Chill/Crossfire/Compute)",
        "amdcc.dll":      "AMD GPU driver (Chill/Crossfire/Compute)",
    }
    GPU_RUNTIME_DLLS = {
        "d3d12.dll":      "Direct3D 12 runtime",
        "d3d12core.dll":  "Direct3D 12 core runtime",
        "d3d11.dll":      "Direct3D 11 runtime",
        "dxgi.dll":       "DXGI (swap chain / display)",
        "dxcore.dll":     "DXCore adapter enumeration",
        "d3d12sdklayers.dll": "D3D12 debug/validation layer",
    }
    DXGI_ERRORS = {
        0x887A0005: ("DXGI_ERROR_DEVICE_HUNG",    "GPU stopped responding - driver TDR or infinite shader loop"),
        0x887A0006: ("DXGI_ERROR_DEVICE_REMOVED",  "GPU device was removed - driver crash, overheat, or hardware fault"),
        0x887A0007: ("DXGI_ERROR_DEVICE_RESET",    "GPU was reset by the driver - likely TDR recovery"),
        0x887A0020: ("DXGI_ERROR_DRIVER_INTERNAL_ERROR", "Internal driver error - update or reinstall GPU drivers"),
        0x80004005: ("E_FAIL in D3D context",      "Generic D3D failure - bad draw call, invalid resource, or OOM"),
    }

    ex = parsed.get("exception")

    crash_in_driver  = None
    crash_in_runtime = None
    if ex:
        try:
            ca = int(ex["address"], 16)
            for m in modules:
                base = int(m["base"], 16)
                if base <= ca < base + m["size"]:
                    n = PureWindowsPath(m["name"]).name.lower()
                    if n in GPU_DRIVER_DLLS:
                        crash_in_driver = (PureWindowsPath(m["name"]).name, GPU_DRIVER_DLLS[n], ca - base)
                    elif n in GPU_RUNTIME_DLLS:
                        crash_in_runtime = (PureWindowsPath(m["name"]).name, GPU_RUNTIME_DLLS[n], ca - base)
                    break
        except Exception:
            pass

    dxgi_error = None
    if ex:
        try:
            code_int = int(ex["code"], 16)
            if code_int in DXGI_ERRORS:
                name, desc = DXGI_ERRORS[code_int]
                dxgi_error = (name, desc)
        except Exception:
            pass

    gpu_vendor = None
    for n in all_names.split():
        if any(k in n for k in ("amdxc", "amdxx", "atidag", "atidxx")):
            gpu_vendor = "AMD"; break
        if any(k in n for k in ("nvwgf", "nvd3d", "nvcuda")):
            gpu_vendor = "NVIDIA"; break
        if any(k in n for k in ("igdumd", "igxelp")):
            gpu_vendor = "Intel"; break

    if dxgi_error:
        name, desc = dxgi_error
        hints.insert(0, (
            f"⚠ GPU ERROR: {name}",
            f"Exception code is a DXGI error - {desc}",
            PURPLE,
            f"The GPU itself reported this error to the D3D runtime. "
            f"Common causes: overheating GPU, unstable overclock, driver bug, or corrupted VRAM. "
            f"{'AMD driver detected - try DDU + clean driver install.' if gpu_vendor == 'AMD' else ''}"
            f"{'NVIDIA driver detected - try DDU + clean driver install.' if gpu_vendor == 'NVIDIA' else ''}"
            f" Check GPU temps and Event Viewer for driver timeout (TDR) entries."
        ))

    if crash_in_driver:
        dll, desc, offset = crash_in_driver
        hints.insert(0, (
            f"⚠ CRASH INSIDE GPU DRIVER: {dll}",
            f"{desc} - crash at +0x{offset:X}",
            PURPLE,
            f"The crash address landed directly inside the {gpu_vendor or 'GPU'} driver. "
            f"This is almost certainly a driver bug or driver-hardware mismatch. "
            f"Recommended: use DDU (Display Driver Uninstaller) to fully remove the driver, "
            f"then install the latest stable release. "
            f"Also check for GPU overheating or unstable overclocks."
        ))
    elif crash_in_runtime:
        dll, desc, offset = crash_in_runtime
        hints.append((
            f"Crash inside {dll}",
            f"{desc} - crash at +0x{offset:X}",
            PURPLE,
            f"The crash happened inside the D3D/DXGI runtime, not the game code directly. "
            f"Could be: invalid draw call arguments, a resource used after being freed, "
            f"swap chain resize during rendering, or GPU device lost. "
            f"Check for DXGI_ERROR_DEVICE_REMOVED in the engine log."
        ))

    if ex:
        try:
            crash_addr = int(ex["address"], 16)
            for m in modules:
                try:
                    base = int(m["base"], 16)
                    if not (base <= crash_addr < base + m["size"]):
                        continue
                    mod_name = PureWindowsPath(m["name"]).name.lower()
                    offset   = crash_addr - base
                    for kw, (label, colour, could_be) in STINGRAY_PATTERNS.items():
                        if kw in mod_name:
                            hints.append((
                                label,
                                f"Crash address landed inside {PureWindowsPath(m['name']).name}  +0x{offset:X}",
                                colour,
                                could_be,
                            ))
                    break
                except Exception:
                    continue
        except Exception:
            pass

    if ex:
        code = ex["code"].lower()
        try:
            code_int = int(ex["code"], 16)
        except Exception:
            code_int = -1
        if code_int == 0xC0000005 and has_dstorage:
            try:
                crash_addr = int(ex["address"], 16)
                for m in parsed.get("modules", []):
                    mname = PureWindowsPath(m["name"]).name.lower()
                    if "dstorage" in mname:
                        base = int(m["base"], 16)
                        if base <= crash_addr < base + m["size"]:
                            hints.insert(0, (
                                "⚠ DIRECTSTORAGE FAILURE",
                                f"Crash address landed inside {PureWindowsPath(m['name']).name} - DirectStorage itself crashed.",
                                PURPLE,
                                "The crash occurred inside the DirectStorage runtime, not just near it. "
                                "This points directly at a DS failure: GPU decompression error, "
                                "invalid read request, or corrupt streaming data. "
                                "Check .log for IO/streaming errors, update GPU drivers, and verify game files.",
                            ))
                            break
            except Exception:
                pass
        if code_int == 0xC0000005:
            hints.insert(0, (
                "⚠ ENGINE SUICIDE - FALSE FLAG",
                "0xC0000005: Stingray intentionally killed itself after detecting an internal error. "
                "This exception is NOT the root cause. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs.",
                YELLOW,
                "To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs "
                "Common triggers: failed resource load, violated engine assertion, out-of-memory, or corrupted game state.",
            ))
        if "c0000005" in code and code_int != 0xC0000005:
            hints.append(("Access Violation", "Classic null/bad-pointer dereference or out-of-bounds write", RED,
                "Could be: null pointer dereference, use-after-free, buffer overrun writing past array end, "
                "or a dangling pointer to a destroyed object still being accessed."))
        if "c00000fd" in code:
            recursion_detail = _detect_recursion(parsed)
            hints.append(("Stack Overflow", "Likely infinite recursion or very deep call stack", RED,
                recursion_detail))
        if "c0000374" in code:
            hints.append(("Heap Corruption", "Memory stomped before crash – use heap profiler", RED,
                "Could be: buffer overrun corrupting heap metadata, double-free, "
                "or a use-after-free that stomped an allocator's internal freelist."))
        if "e06d7363" in code:
            hints.append(("Unhandled C++ Exception", "Exception thrown but not caught – check throw sites", YELLOW,
                "Could be: std::bad_alloc (out of memory), std::out_of_range, "
                "or a custom engine exception thrown in a codepath with no try/catch."))
        if "c0000142" in code:
            dll_suspect = _find_dll_init_suspect(parsed)
            hints.insert(0, ("DLL Initialisation Failed (0xC0000142)",
                "A DLL failed to initialise during process startup - game never reached main()", RED,
                dll_suspect))
        if "80000003" in code:
            hints.append(("Breakpoint in Release Build", "__debugbreak() or assert left in shipping code", YELLOW,
                "Could be: a debug assert accidentally shipped, an __debugbreak() in error handling code, "
                "or an anti-cheat / DRM trigger firing incorrectly."))
        if "80000004" in code:
            hints.append(("Single-Step Trap (Not a Real Crash)",
                "0x80000004: the CPU's trap flag fired after executing one instruction - "
                "this is what a debugger does, not what a fault looks like", YELLOW,
                "This is a debugger trap, not an engine or game error. The CPU executed exactly one "
                "instruction and then raised this exception because the trap (single-step) flag was set - "
                "that flag is set by a debugger when stepping through code, not by anything the game itself "
                "can trigger from a bug. "
                "Three likely explanations: (1) a debugger such as WinDbg, x64dbg, or Visual Studio was "
                "attached to the process and a step/breakpoint action produced this dump; "
                "(2) an anti-cheat or anti-tamper system (EasyAntiCheat, BattlEye, or a custom Stingray "
                "anti-debug check) detected single-stepping/tracing - a common technique used by cheats and "
                "reverse-engineering tools - and force-terminated the process, capturing this dump as evidence; "
                "(3) a debugger was attached and then detached uncleanly, leaving a stale trap flag that fired "
                "on the next instruction. "
                "Check the module list for anti-cheat components (EasyAntiCheat.dll, BEService.exe) and check "
                "whether a debugger or trainer/cheat tool was running at the time. The register values and "
                "call chain captured in this dump describe whatever instruction happened to execute next - "
                "they are not evidence of a bug and should not be treated as a crash site."))

    return hints

def _null_registers_at_crash(parsed: dict) -> dict:
    ex   = parsed.get("exception", {}) or {}
    regs = ex.get("regs", {})
    if not regs:
        return {"null": {}, "near_null": {}}
    return {
        "null":     {k.upper(): v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and v == 0},
        "near_null":{k.upper(): v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and 0 < v < 0x1000},
    }



STINGRAY_GAME_EXES = {
    "helldivers2.exe",
}

def _is_stingray_suicide(parsed: dict) -> tuple:
    ex = parsed.get("exception", {}) or {}
    if not ex:
        return (False, "")
    try:
        ex_code = int(ex.get("code", "0"), 16)
    except (ValueError, TypeError):
        return (False, "")
    if ex_code != 0xC0000005:
        return (False, "")
    try:
        ex_addr = int(ex.get("address", "0"), 16)
    except (ValueError, TypeError):
        return (False, "")

    modules = parsed.get("modules", [])
    crash_mod_name = None
    crash_mod_path = None
    for m in modules:
        try:
            base = int(m["base"], 16)
            if base <= ex_addr < base + m["size"]:
                crash_mod_name = PureWindowsPath(m["name"]).name
                crash_mod_path = m["name"]
                break
        except Exception:
            pass

    if not crash_mod_name:
        return (False, "")

    if crash_mod_name.lower() in STINGRAY_GAME_EXES:
        return (True, f"crash module {crash_mod_name} is a known Stingray game executable")

    has_crs_client = any(
        PureWindowsPath(m["name"]).name.lower() == "crs-client.dll"
        for m in modules
    )
    if has_crs_client and crash_mod_name.lower().endswith(".exe"):
        crs_path = next(
            (m["name"] for m in modules
             if PureWindowsPath(m["name"]).name.lower() == "crs-client.dll"),
            ""
        )
        if crs_path and crash_mod_path:
            crs_dir = str(PureWindowsPath(crs_path).parent).lower()
            crash_dir = str(PureWindowsPath(crash_mod_path).parent).lower()
            if crs_dir == crash_dir:
                return (True, f"crash module {crash_mod_name} is alongside crs-client.dll (Arrowhead crash reporter)")

    return (False, "")


def _identify_bad_register(decoded_instr: dict, null_regs: dict, fault_addr: int) -> "str | None":
    if not decoded_instr or not null_regs:
        return None
    instr = decoded_instr.get("instruction", "")
    mem_m = re.search(r'\[([^\]]+)\]', instr)
    if not mem_m:
        return None
    operand = mem_m.group(1)
    base_m = re.match(r'(R(?:[A-Z]{2}|[0-9]+)|E[A-Z]{2})', operand)
    if base_m:
        base = base_m.group(1)
        if base in null_regs:
            return base
    for reg in sorted(null_regs, key=len, reverse=True):
        if re.search(r'\b' + reg + r'\b', operand):
            return reg
    return None



def _read_mem(raw: bytes, memory_map: list, addr: int, size: int) -> "bytes | None":
    for (start, msz, rva) in memory_map:
        if start <= addr < start + msz:
            off = addr - start
            avail = min(size, msz - off)
            chunk = raw[rva + off: rva + off + avail]
            return chunk if len(chunk) == size else None
    return None

def _read_u32_mem(raw: bytes, memory_map: list, addr: int) -> "int | None":
    b = _read_mem(raw, memory_map, addr, 4)
    return struct.unpack_from("<I", b)[0] if b else None

def _read_u64_mem(raw: bytes, memory_map: list, addr: int) -> "int | None":
    b = _read_mem(raw, memory_map, addr, 8)
    return struct.unpack_from("<Q", b)[0] if b else None

def _load_pdata(raw: bytes, memory_map: list, mod_base: int) -> "list | None":
    try:
        e_lfanew_b = _read_mem(raw, memory_map, mod_base + 0x3C, 4)
        if not e_lfanew_b:
            return None
        pe_off = mod_base + struct.unpack_from("<I", e_lfanew_b)[0]

        sig = _read_mem(raw, memory_map, pe_off, 4)
        if not sig or sig != b"PE\0\0":
            return None

        magic_b = _read_mem(raw, memory_map, pe_off + 0x18, 2)
        if not magic_b or struct.unpack_from("<H", magic_b)[0] != 0x20B:
            return None

        exc_dir_addr = pe_off + 0x18 + 0x70 + 3 * 8
        rva_b   = _read_mem(raw, memory_map, exc_dir_addr,     4)
        size_b  = _read_mem(raw, memory_map, exc_dir_addr + 4, 4)
        if not rva_b or not size_b:
            return None

        exc_rva  = struct.unpack_from("<I", rva_b)[0]
        exc_size = struct.unpack_from("<I", size_b)[0]
        if exc_rva == 0 or exc_size == 0:
            return None

        n_entries = exc_size // 12
        if n_entries == 0 or n_entries > 500_000:
            return None

        pdata_va = mod_base + exc_rva
        pdata_bytes = _read_mem(raw, memory_map, pdata_va, exc_size)
        if not pdata_bytes or len(pdata_bytes) < 12:
            return None

        entries = []
        for i in range(min(n_entries, len(pdata_bytes) // 12)):
            off = i * 12
            begin = struct.unpack_from("<I", pdata_bytes, off)[0]
            end   = struct.unpack_from("<I", pdata_bytes, off + 4)[0]
            if begin < end and end < 0x10000000:
                entries.append((begin, end))

        return entries if entries else None
    except Exception:
        return None

def _is_valid_return_address(addr: int, mod_base: int, pdata: "list | None") -> bool:
    if pdata is None:
        return True

    rva = addr - mod_base
    for delta in (1, 2, 3, 5, 6):
        candidate = rva - delta
        if candidate <= 0:
            continue
        lo, hi = 0, len(pdata) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            begin, end = pdata[mid]
            if begin <= candidate < end:
                return True
            elif candidate < begin:
                hi = mid - 1
            else:
                lo = mid + 1
    return False


def _reconstruct_call_chain(parsed: dict, max_frames: int = 16) -> list:
    ex        = parsed.get("exception", {}) or {}
    ex_regs   = ex.get("regs", {})
    crash_rip = int(ex.get("address", "0"), 16) if ex else 0
    crash_rsp = ex_regs.get("rsp", 0)
    modules   = parsed.get("modules", [])
    raw_path  = parsed.get("_raw_path")
    memory_map = parsed.get("memory_map", [])

    if not crash_rsp or not raw_path:
        return []

    SKIP_NAMES = {
        "gameoverlayrenderer64.dll", "gameoverlayrenderer.dll",
        "npggnt64.des", "npsc64.des",
        "crs-client.dll", "crashpad_handler.exe", "sentry.dll", "backtrace.dll",
        "easyanticheat.dll", "easyanticheat_launcher.dll",
    }
    SKIP_PATH_FRAGMENTS = ("\\windows\\", "\\gameguard\\", "gameoverlayrenderer")

    def is_engine_frame(mod_name: str, full_path: str) -> bool:
        if not mod_name:
            return False
        nl = mod_name.lower()
        fl = full_path.lower().replace("/", "\\")
        if nl in SKIP_NAMES or nl.endswith(".des"):
            return False
        return not any(frag in fl for frag in SKIP_PATH_FRAGMENTS)

    def addr_to_mod(addr: int):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name, addr - base, m["name"], base
            except Exception:
                pass
        return None, 0, "", 0

    try:
        with open(raw_path, "rb") as f:
            raw = f.read()
    except Exception:
        return []

    pdata_cache: dict = {}
    for m in modules:
        try:
            base = int(m["base"], 16)
            name = PureWindowsPath(m["name"]).name
            full = m["name"].lower().replace("/", "\\")
            if is_engine_frame(name, full):
                pdata_cache[base] = _load_pdata(raw, memory_map, base)
        except Exception:
            pass

    def read_u64(addr: int) -> "int | None":
        return _read_u64_mem(raw, memory_map, addr)

    chain = []
    pdata_confirmed_count = 0
    heuristic_count = 0

    mod, off, full, base = addr_to_mod(crash_rip)
    if is_engine_frame(mod, full):
        chain.append((crash_rip, mod, off, True))

    ptr     = crash_rsp
    scanned = 0
    prev    = None
    while len(chain) < max_frames and scanned < 0xC000:
        val = read_u64(ptr)
        if val is None:
            break
        ptr     += 8
        scanned += 8
        if val == 0:
            continue

        mod, off, full, mod_base = addr_to_mod(val)
        if not mod or off == 0:
            continue
        if not is_engine_frame(mod, full):
            continue
        if (val, mod, off) == prev:
            continue

        pdata = pdata_cache.get(mod_base)
        verified = _is_valid_return_address(val, mod_base, pdata)
        if pdata is not None and not verified:
            continue

        chain.append((val, mod, off, verified))
        prev = (val, mod, off)
        if pdata is not None:
            pdata_confirmed_count += 1
        else:
            heuristic_count += 1

    parsed["_stack_unwind"] = {
        "pdata_confirmed": pdata_confirmed_count,
        "heuristic":       heuristic_count,
        "pdata_modules":   sum(1 for v in pdata_cache.values() if v is not None),
        "total_modules":   len(pdata_cache),
    }

    parsed["_stack_chain_extended"] = chain
    return [(a, m, o) for a, m, o, _ in chain]


def _active_game_threads_at_crash(parsed: dict) -> list:
    ex        = parsed.get("exception", {}) or {}
    crash_tid = ex.get("thread_id")
    modules   = parsed.get("modules", [])
    SKIP_HANDLERS = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                     "sentry.dll", "backtrace.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    def addr_to_mod(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    full = m["name"].lower().replace("/", "\\")
                    return PureWindowsPath(m["name"]).name, addr - base, full
            except Exception:
                pass
        return None, 0, ""

    result = []
    for t in parsed.get("threads", []):
        if t.get("tid") == crash_tid:
            continue
        rip = t.get("rip", 0)
        mod, off, full = addr_to_mod(rip)
        if not mod:
            continue
        if mod.lower() in SKIP_HANDLERS:
            continue
        if any(full.startswith(p) for p in SYSTEM_PREFIXES):
            continue
        result.append({
            "tid":    t["tid"],
            "module": mod,
            "offset": off,
            "rcx":    t.get("rcx", 0),
        })
    return result

def assess_root_cause(parsed: dict) -> list[tuple[str, str, str]]:

    findings = []

    ex      = parsed.get("exception") or {}
    modules = parsed.get("modules", [])
    threads = parsed.get("threads", [])

    CRASH_HANDLERS  = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                        "sentry.dll", "backtrace.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    def mod_for_addr(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    n = PureWindowsPath(m["name"]).name
                    return n, addr - base, m["name"]
            except Exception:
                pass
        return None, 0, None

    crash_tid = ex.get("thread_id")

    active_game_threads = []
    for t in threads:
        if t["tid"] == crash_tid:
            continue
        rip = t.get("rip", 0)
        mod, off, full = mod_for_addr(rip)
        if not mod:
            continue
        full_lower = (full or "").lower().replace("/", "\\")
        is_sys     = "\\windows\\" in full_lower or "\\microsoft" in full_lower
        is_handler = mod.lower() in CRASH_HANDLERS
        if not is_sys and not is_handler:
            active_game_threads.append((t, mod, off, full))

    try:
        ex_code = int(ex.get("code", "0"), 16)
        params  = ex.get("params", [])
        ex_addr = int(ex.get("address", "0"), 16)

        fault_addr   = None
        _pre_decoded = None
        try:
            _imem = read_virtual_memory(parsed, ex_addr, 16)
            if _imem:
                _pre_decoded = decode_crash_instruction(_imem, ex_addr)
        except Exception as e:
            pass

        if ex_code == 0xC0000005 and len(params) >= 2:
            op          = "write" if params[0] == "0x1" else "read"
            fault_addr  = int(params[1], 16)

            _suicide_check, _suicide_reason = _is_stingray_suicide(parsed)

            decoded_instr = None
            instr_mem = read_virtual_memory(parsed, ex_addr, 16)
            if instr_mem:
                decoded_instr = decode_crash_instruction(instr_mem, ex_addr)
            else:
                size_mb = parsed.get("size_mb", 0)
                if size_mb and size_mb < 10:
                    findings.append({"conf": "LOW",
                        "title": "Small minidump - detailed instruction analysis unavailable",
                        "detail": (f"This dump is {size_mb}MB and doesn't include memory at the crash address. "
                                   f"Full memory dumps (100MB+) or the engine log file (.log) provide detailed analysis. "
                                   f"The exception parameters and register analysis below may still indicate the root cause."),
                        "link": None,
                    })

            is_vtable_dispatch = False
            vtable_slot = None
            if instr_mem and len(instr_mem) >= 6:
                ib = list(instr_mem)
                if (len(ib) >= 6 and ib[0] in (0x48, 0x49, 0x4C, 0x4D)
                        and ib[1] == 0x8B
                        and (ib[2] >> 6) == 0
                        and ib[3] == 0xFF
                        and ib[4] in (0x50, 0x90)):
                    disp = ib[5]
                    slot = disp // 8
                    is_vtable_dispatch = True
                    vtable_slot = slot

            ex_regs = ex.get("regs", {})
            crash_rcx = ex_regs.get("rcx", None)
            crash_rax = ex_regs.get("rax", None)

            if decoded_instr and decoded_instr["is_suicide"]:
                findings.append({"conf": "HIGH",
                    "title": f"Engine suicide instruction confirmed: {decoded_instr['instruction']}",
                    "detail": (decoded_instr["explanation"] +
                               " The null pointer access is intentional - look at the engine log and "
                               "the active game thread for the real trigger."),
                    "link": None,
                })
            elif _suicide_check:
                instr_str = decoded_instr["instruction"] if decoded_instr else "instruction unavailable"
                findings.append({"conf": "HIGH",
                    "title": f"Engine suicide (Stingray) - crash instruction: {instr_str}",
                    "detail": (
                        f"The Stingray engine intentionally terminated the process. "
                        f"The crash instruction ({instr_str}) is the engine's suicide MECHANISM, "
                        f"not a real null-deref bug. "
                        f"The engine deliberately executed this instruction with a null pointer to "
                        f"terminate after detecting an internal error.\n\n"
                        f"Detection: {_suicide_reason}.\n"
                        f"Do NOT treat the null pointer as the root cause. "
                        f"To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs Then check the active game thread."
                    ),
                    "link": None,
                })
            elif is_vtable_dispatch and fault_addr == 0 and crash_rcx == 0:
                findings.append({"conf": "HIGH",
                    "title": f"Virtual method called on null 'this' pointer - vtable dispatch crashed",
                    "detail": (
                        f"The crash instruction is MOV RAX, [RCX] followed by CALL [RAX+0x{ib[5]:02X}] "
                        f"- the standard x64 C++ virtual dispatch sequence. "
                        f"RCX ('this' pointer) was 0x0 at crash time, so loading the vtable from [RCX] "
                        f"faulted immediately. Virtual function at vtable slot {vtable_slot} "
                        f"(offset +0x{ib[5]:02X}) was the intended target. "
                        f"The object was never initialised, was already destroyed, or a function "
                        f"returned null and the caller didn't check before calling a method on it."
                    ),
                    "link": None,
                })
            elif fault_addr == 0:
                findings.append({"conf": "HIGH",
                    "title": f"Null pointer {op} at 0x0",
                    "detail": (f"The engine attempted to {op} address 0x0. "
                               f"In Stingray this typically means an object pointer was never initialized, "
                               f"or an object was destroyed and its pointer was not cleared before use. "
                               + (decoded_instr["explanation"] if decoded_instr else
                                  "A write to null is often a destroyed object still being updated." if op == "write"
                                  else "A read from null is often a missing resource or uninitialized component.")
                               + (f" RCX=0x{crash_rcx:016X}" if crash_rcx is not None else "")),
                    "link": None,
                })
            elif fault_addr < 0x100:
                findings.append({"conf": "HIGH",
                    "title": f"Near-null {op} at offset +{fault_addr} (0x{fault_addr:X})",
                    "detail": (f"The engine tried to {op} to address 0x{fault_addr:X} - "
                               f"a struct member access on a null pointer (field at byte offset {fault_addr}). "
                               f"Something returned a null object and the caller didn't check before accessing field +{fault_addr}. "
                               + (decoded_instr["explanation"] if decoded_instr else "")),
                    "link": None,
                })
            elif fault_addr > 0x00007F0000000000:
                findings.append({"conf": "HIGH",
                    "title": f"Out-of-bounds {op} at very high address 0x{fault_addr:016X}",
                    "detail": ("The faulting address is in kernel/guard territory. "
                               "This usually indicates stack overflow, a corrupted stack pointer, or a bad function pointer."),
                    "link": None,
                })
            else:
                findings.append({"conf": "MED",
                    "title": f"Bad pointer {op} at 0x{fault_addr:016X}",
                    "detail": ("The faulting address is not null but is invalid - possible use-after-free "
                               "(freed memory reused), bad array index, or a corrupted pointer. "
                               + (decoded_instr["explanation"] if decoded_instr else "")),
                    "link": None,
                })

            fault_mod, fault_off, _ = mod_for_addr(ex_addr)
            if fault_mod:
                findings.append({"conf": "HIGH",
                    "title": f"Faulting instruction in {fault_mod} +0x{fault_off:X}",
                    "detail": (f"The CPU instruction that caused the {op} fault was at this location. "
                               f"This is the code that dereferenced the bad pointer - not necessarily where the pointer went bad. "
                               f"Click to inspect in Modules tab."),
                    "link": {"tab": "modules", "module": fault_mod},
                })

    except (ValueError, KeyError, TypeError, AttributeError) as e:
        findings.append({"conf": "LOW",
            "title": f"Exception analysis incomplete ({type(e).__name__})",
            "detail": (f"The dump is missing data needed for detailed crash analysis ({type(e).__name__}). "
                       f"This often happens with small minidumps that don't capture full memory. "
                       f"Check the exception code and registers above, or to get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs"),
            "link": None,
        })
    except Exception as e:
        import sys as _sys
        print(f"assess_root_cause unexpected error: {type(e).__name__}: {e}", file=_sys.stderr)
        findings.append({"conf": "LOW",
            "title": f"Analysis pipeline error: {type(e).__name__}",
            "detail": (f"The root-cause analysis hit an unexpected error ({type(e).__name__}: {e}). "
                       f"Some findings may be missing. The exception code and registers above "
                       f"are still valid. Share the .dmp and .log with the dev team for full analysis."),
            "link": None,
        })

    for t, mod, off, full in active_game_threads:
        rcx       = t.get("rcx", 0)
        rax       = t.get("rax", 0)
        rdx       = t.get("rdx", 0)
        this_null = rcx < 0x1000
        findings.append({"conf": "MED" if not this_null else "HIGH",
            "title": f"Active game thread in {mod} +0x{off:X}",
            "detail": (f"This thread was executing game code when the crash occurred - "
                       f"it is the most likely location of the root cause. "
                       + (f"RCX (likely 'this' pointer) = 0x{rcx:016X} - near zero, "
                          f"suggesting a virtual call on a null/destroyed object. "
                          if this_null else
                          f"RCX=0x{rcx:016X}  RDX=0x{rdx:016X}  RAX=0x{rax:016X}. ")
                       + f"Click to inspect in Threads tab."),
            "link": {"tab": "threads", "tid": t["tid"]},
        })

    null_info = _null_registers_at_crash(parsed)
    null_regs  = null_info["null"]
    near_nulls = null_info["near_null"]

    if null_regs:
        bad_reg = (_identify_bad_register(_pre_decoded, null_regs, fault_addr)
                   if _pre_decoded and fault_addr is not None else None)
        if len(null_regs) == 1:
            reg, val = next(iter(null_regs.items()))
            confirmed_str = (" This matches the base register in the crash instruction - "
                            f"confirmed: {bad_reg} was the null pointer." if bad_reg and bad_reg == reg else "")
            findings.append({"conf": "HIGH",
                "title": f"Register {reg} was null at crash time (ExceptionStream confirmed)",
                "detail": (f"{reg} = 0x{val:016X} - captured at the exact CPU state of the fault "
                           f"before any exception handler ran.{confirmed_str} "
                           f"{reg} held a null pointer that was dereferenced or called."),
                "link": None,
            })
        elif len(null_regs) <= 4:
            reg_list = ", ".join(null_regs.keys())
            bad_str  = f" Instruction analysis points to {bad_reg} as the base pointer." if bad_reg else ""
            findings.append({"conf": "MED",
                "title": f"Multiple null registers at crash: {reg_list}",
                "detail": (f"Registers {reg_list} were all zero at crash time (ExceptionStream).{bad_str} "
                           f"Multiple nulls can indicate an uninitialised struct, "
                           f"a use-after-free where the freed block was zeroed, "
                           f"or a C++ object whose constructor never ran."),
                "link": None,
            })
        else:
            reg_list = ", ".join(list(null_regs.keys())[:6]) + (f" +{len(null_regs)-6} more" if len(null_regs) > 6 else "")
            findings.append({"conf": "MED",
                "title": f"{len(null_regs)} GPRs were null at crash - likely uninitialized or zeroed memory",
                "detail": (f"Null registers: {reg_list}. "
                           f"Having this many zero registers at fault time suggests the code was "
                           f"executing in a freshly-zeroed or corrupted stack/heap frame. "
                           f"Could indicate a use-after-free, stack smash, or calling a method "
                           f"on a default-constructed (zero-initialised) object."),
                "link": None,
            })

    if near_nulls:
        nr_list = ", ".join(f"{r}=0x{v:X}" for r, v in near_nulls.items())
        findings.append({"conf": "LOW",
            "title": f"Near-null registers: {nr_list}",
            "detail": ("These registers held small non-zero values - "
                       "they may be array indices, loop counters, or enum values "
                       "rather than null pointers. Low signal on their own."),
            "link": None,
        })

    chain = _reconstruct_call_chain(parsed, max_frames=12)
    if chain:
        unwind_info = parsed.get("_stack_unwind", {})
        extended    = parsed.get("_stack_chain_extended", [])
        pdata_mods  = unwind_info.get("pdata_modules", 0)
        total_mods  = unwind_info.get("total_modules", 0)
        confirmed   = unwind_info.get("pdata_confirmed", 0)
        heuristic   = unwind_info.get("heuristic", 0)

        if pdata_mods > 0:
            quality = (f"pdata-verified ({confirmed} frames confirmed via PE exception directory, "
                       f"{heuristic} heuristic fallback, "
                       f".pdata available for {pdata_mods}/{total_mods} engine modules)")
            conf = "MED"
        else:
            quality = "heuristic only - .pdata not available in this dump, frames may include noise"
            conf = "LOW"

        chain_lines = []
        for i, (addr, mod, off) in enumerate(chain):
            prefix   = "CRASH → " if i == 0 else f"  ← #{i:02d}  "
            verified = extended[i][3] if i < len(extended) else False
            vtag     = "" if i == 0 else (" [pdata✓]" if verified else " [heuristic]")
            chain_lines.append(f"{prefix}0x{addr:016X}  {mod} +0x{off:X}{vtag}")

        findings.append({"conf": conf,
            "title": f"Crash thread call chain ({len(chain)} engine frames - {quality})",
            "detail": ("Stack walk from crash-time RSP (ExceptionStream ground truth). "
                       "Frames marked [pdata✓] are validated against the PE exception directory "
                       "and are real return addresses. Frames marked [heuristic] are unverified - "
                       "treat them as candidates, not certainties. "
                       "Addresses are shown as module + hex offset - share this dump with the development team for full analysis.\n"
                       + "\n".join(chain_lines)),
            "link": None,
        })

    stingray_suicide, suicide_reason = _is_stingray_suicide(parsed)
    if stingray_suicide:
        active_game = _active_game_threads_at_crash(parsed)
        trigger_lines = []
        for t in active_game[:8]:
            trigger_lines.append(
                "  TID {:6d}  {}+0x{:X}{}".format(
                    t["tid"], t["module"], t["offset"],
                    "  <- RCX null (null object)" if t["rcx"] < 0x1000 else "")
            )
        suicide_detail = (
            f"The Stingray engine intentionally terminated the process by deliberately "
            f"dereferencing a null pointer. This is NOT a real null-deref bug - it is the "
            f"engine's crash handler responding to an internal error. "
            f"Detection signal: {suicide_reason}.\n\n"
            f"The null pointer access you see in the crash instruction is the engine's "
            f"suicide MECHANISM, not the root CAUSE. The real trigger is what made the "
            f"engine decide to call its crash routine.\n\n"
            f"To find the real trigger:\n"
            f"  1. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs \n"
            f"  2. Look at the active game thread(s) below - one of them caused the engine\n"
            f"     to detect an internal error\n"
            f"  3. The call chain leading INTO the suicide instruction shows which engine\n"
            f"     subsystem invoked the crash handler\n"
        )
        if active_game:
            suicide_detail += (
                f"\nActive game thread(s) at crash time ({len(active_game)} found):\n"
                + "\n".join(trigger_lines)
            )
        findings.insert(0, {"conf": "HIGH",
            "title": "Engine suicide instruction confirmed (Stingray engine)",
            "detail": suicide_detail,
            "link": None,
        })

    try:
        if ex_code == 0xC0000142:
            dll_suspect = _find_dll_init_suspect(parsed)
            findings.insert(0, {"conf": "HIGH",
                "title": "DLL Initialisation Failed - game crashed before main()",
                "detail": (
                    "Exception 0xC0000142 (DLL_INIT_FAILED) means a DLL's DllMain returned FALSE "
                    "or threw an exception during process startup. The game executable never ran. "
                    + dll_suspect
                ),
                "link": None,
            })
        if ex_code == 0x80000004:
            anticheat_names = ("easyanticheat", "beclient", "beservice", "battleye")
            found_anticheat = [PureWindowsPath(m["name"]).name for m in modules
                               if any(n in m["name"].lower() for n in anticheat_names)]
            if found_anticheat:
                ac_detail = (
                    f"Anti-cheat component(s) present in the module list: {', '.join(found_anticheat)}. "
                    "Single-step traps are a known technique anti-cheat systems use to detect debuggers "
                    "and tracing tools - this dump may have been captured at the moment the anti-cheat "
                    "force-terminated the process after detecting tampering."
                )
            else:
                ac_detail = (
                    "No anti-cheat component found in the module list, so this is more likely an "
                    "externally-attached debugger (WinDbg, x64dbg, Visual Studio) stepping through the "
                    "process, or a stale trap flag left over from a debugger that detached uncleanly."
                )
            findings.insert(0, {"conf": "HIGH",
                "title": "Not a real crash - single-step debugger trap (0x80000004)",
                "detail": (
                    "This exception code means the CPU's trap flag was set and fired after exactly one "
                    "instruction executed - that is what a debugger does when stepping through code, not "
                    "something a game bug can trigger. The register values and call chain captured here "
                    "describe whatever instruction happened to run next, not a fault site. " + ac_detail
                ),
                "link": None,
            })
    except Exception:
        pass

    if not findings:
        findings.append({"conf": "LOW",
            "title": "Could not determine root cause from dump alone",
            "detail": ("No active game threads found and no clear signal from the exception parameters. "
                       "To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs"),
            "link": None,
        })

    return findings

def build_summary(parsed: dict) -> str:

    lines = []

    ex_early = parsed.get("exception")
    if ex_early:
        try:
            if int(ex_early["code"], 16) == 0xC0000005:
                lines.append("╔═════════════════════════════════════════════════════╗")
                lines.append("║         FALSE FLAG - ENGINE SUICIDE                 ║")
                lines.append("║  0xC0000005: Stingray killed itself intentionally.  ║")
                lines.append("║  This is NOT the root cause of the crash.           ║")
                lines.append("║  To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs instead.    ║")
                lines.append("╚═════════════════════════════════════════════════════╝")
                lines.append("")
        except Exception:
            pass

    lines.append(f"File      : {parsed['file']}")
    lines.append(f"Size      : {parsed.get('size_mb', '?')} MB")
    lines.append(f"Version   : {parsed.get('version', '?')}")
    lines.append(f"Timestamp : {parsed.get('timestamp', '?')}")
    lines.append(f"Streams   : {parsed.get('stream_count', 0)}")
    lines.append(f"Threads   : {len(parsed.get('threads', []))}")
    if "process_id" in parsed:
        lines.append(f"PID       : {parsed['process_id']}")

    si = parsed.get("system_info", {})
    if si:
        lines.append("")
        lines.append("── SYSTEM INFO ─────────────────────────────────────")
        lines.append(f"  Architecture : {si.get('arch', '?')}")
        lines.append(f"  CPU count    : {si.get('cpu_count', '?')}")
        lines.append(f"  OS version   : {si.get('os_version', '?')}")

    ex = parsed.get("exception")
    if ex:
        lines.append("")
        lines.append("── EXCEPTION ───────────────────────────────────────")
        lines.append(f"  Code    : {ex['code']}")
        lines.append(f"  Meaning : {ex['code_desc']}")
        lines.append(f"  Address : {ex['address']}")
        lines.append(f"  Thread  : {ex['thread_id']}")
        if ex.get("params"):
            lines.append(f"  Params  : {', '.join(ex['params'])}")
        try:
            crash_addr = int(ex["address"], 16)
            crash_mod  = None
            for m in parsed.get("modules", []):
                base = int(m["base"], 16)
                if base <= crash_addr < base + m["size"]:
                    crash_mod = f"{PureWindowsPath(m['name']).name}  +0x{crash_addr - base:X}"
                    break
            lines.append(f"  In      : {crash_mod or '(address outside all known modules)'}")
        except Exception:
            pass
        regs = ex.get("regs", {})
        if regs:
            lines.append("")
            lines.append("── REGISTERS AT CRASH (ExceptionStream - ground truth) ─")
            null_regs = {k: v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and v == 0}
            near_null = {k: v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and 0 < v < 0x1000}
            for name, val in regs.items():
                if name == "_xmm" or not isinstance(val, int):
                    continue
                flag = "  ← NULL" if val == 0 else (f"  ← near-null (0x{val:X})" if val < 0x1000 else "")
                if flag:
                    lines.append(f"  {name.upper():<5} = 0x{val:016X}{flag}")
            if not null_regs and not near_null:
                lines.append("  (no null/near-null registers at crash time)")
    else:
        lines.append("")
        lines.append("── EXCEPTION : none found ──────────────────────────")

    mods = parsed.get("modules", [])
    if mods:
        lines.append("")
        lines.append(f"── MODULES ({len(mods)}) ──────────────────────────────────")
        for m in mods[:30]:
            name = PureWindowsPath(m["name"]).name if m["name"] else "?"
            lines.append(f"  {name:<40} base={m['base']}  size={m['size']:,}")
        if len(mods) > 30:
            lines.append(f"  … and {len(mods)-30} more")

    if parsed.get("parse_errors"):
        lines.append("")
        lines.append("── PARSE ERRORS ────────────────────────────────────")
        for e in parsed["parse_errors"]:
            lines.append(f"  ⚠  {e}")

    try:
        rootcause = assess_root_cause(parsed)
        if rootcause:
            lines.append("")
            lines.append("── ROOT CAUSE ASSESSMENT (quick summary) ───────────")
            conf_icons = {"HIGH": "🔴", "MED": "🟡", "LOW": "⚪"}
            for i, rc in enumerate(rootcause[:3]):
                conf_icon = conf_icons.get(rc["conf"], "?")
                lines.append(f"  {conf_icon} [{rc['conf']}] {rc['title']}")
            if len(rootcause) > 3:
                lines.append(f"  … and {len(rootcause)-3} more findings (see Root Cause tab for details)")
    except Exception:
        pass

    return "\n".join(lines)

def read_virtual_memory(parsed: dict, addr: int, size: int = 128) -> "bytes | None":
    raw = parsed.get("_raw_bytes")
    if raw is None:
        raw_data_path = parsed.get("_raw_path")
        if not raw_data_path:
            return None
        try:
            with open(raw_data_path, "rb") as f:
                raw = f.read()
            parsed["_raw_bytes"] = raw
        except Exception:
            return None
    for (start, msz, rva) in parsed.get("memory_map", []):
        if start <= addr < start + msz:
            off   = addr - start
            avail = min(size, msz - off)
            return raw[rva + off: rva + off + avail]
    return None

def format_hex_dump(data: bytes, base_addr: int, highlight_addr: "int | None" = None) -> list:

    rows = []
    for i in range(0, len(data), 16):
        chunk     = data[i:i+16]
        row_addr  = base_addr + i
        is_hi     = highlight_addr is not None and row_addr <= highlight_addr < row_addr + 16
        hex_part  = " ".join(f"{b:02X}" for b in chunk)
        ascii_part= "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append((f"0x{row_addr:016X}", hex_part, ascii_part, is_hi))
    return rows

_REG_NAMES_EXT = {
    0: "AX",  1: "CX",  2: "DX",  3: "BX",
    4: "SP",  5: "BP",  6: "SI",  7: "DI",
    8: "R8",  9: "R9",  10: "R10", 11: "R11",
    12: "R12", 13: "R13", 14: "R14", 15: "R15",
}

def _decode_vex_instruction(b: list, idx: int, vex: dict, crash_addr: int) -> dict:
    if idx >= len(b):
        return {"is_suicide": False, "instruction": "VEX ...", "explanation": "VEX-prefixed instruction (short read)", "confidence": "LOW"}

    opcode = b[idx]; idx += 1
    vex_r = vex.get("r", 0)
    vex_v = vex.get("v", 0)
    vex_L = vex.get("L", 0)
    vex_pp = vex.get("pp", 0)
    vex_m = vex.get("m", 1) if vex.get("vex3") else 1

    vec_prefix = "YMM" if vex_L else "XMM"

    v_reg = f"{vec_prefix}{vex_v}"

    if idx >= len(b):
        return {"is_suicide": False, "instruction": f"VEX {opcode:02X}", "explanation": "VEX-prefixed instruction (no ModRM)", "confidence": "LOW"}

    modrm = b[idx]; idx += 1
    mod = (modrm >> 6) & 0x3
    reg = (modrm >> 3) & 0x7
    rm  = modrm & 0x7

    actual_reg = reg + (8 if not vex_r else 0)
    reg_name = f"{vec_prefix}{actual_reg}"

    vex_b = vex.get("b", 1) if vex.get("vex3") else 1
    vex_x = vex.get("x", 1) if vex.get("vex3") else 1

    AVX_OPS_0F = {
        0x10: ("VMOVUPS",   "load",  ""),
        0x11: ("VMOVUPS",   "store", ""),
        0x28: ("VMOVAPS",   "load",  "aligned"),
        0x29: ("VMOVAPS",   "store", "aligned"),
        0x6F: ("VMOVDQA",   "load",  "aligned"),
        0x7F: ("VMOVDQA",   "store", "aligned"),
        0x6E: ("VMOVD",     "load",  ""),
        0x7E: ("VMOVQ",     "load",  ""),
        0x58: ("VADDPS",    "arith", ""),
        0x59: ("VMULPS",    "arith", ""),
        0x54: ("VANDPS",    "logic", ""),
        0x55: ("VANDNPS",   "logic", ""),
        0x56: ("VORPS",     "logic", ""),
        0x57: ("VXORPS",    "logic", ""),
        0x74: ("VPCMPEQB",  "compare", ""),
        0x76: ("VPCMPEQD",  "compare", ""),
        0xD7: ("VPMOVMSKB", "extract", ""),
    }

    mnemonic = None
    op_type = None
    align_note = ""

    if vex_m == 1:
        pp_prefixes = {0: "", 1: "66 ", 2: "F3 ", 3: "F2 "}
        pp_str = pp_prefixes.get(vex_pp, "")

        if opcode in AVX_OPS_0F:
            base_mnemonic, op_type, align_flag = AVX_OPS_0F[opcode]

            if opcode == 0x10 and vex_pp == 1: mnemonic = "VMOVUPD"
            elif opcode == 0x10 and vex_pp == 2: mnemonic = "VMOVSS"
            elif opcode == 0x11 and vex_pp == 1: mnemonic = "VMOVUPD"
            elif opcode == 0x11 and vex_pp == 2: mnemonic = "VMOVSS"
            elif opcode == 0x28 and vex_pp == 1: mnemonic = "VMOVAPD"
            elif opcode == 0x29 and vex_pp == 1: mnemonic = "VMOVAPD"
            elif opcode == 0x6F and vex_pp == 1: mnemonic = "VMOVDQA"
            elif opcode == 0x6F and vex_pp == 2: mnemonic = "VMOVDQU"
            elif opcode == 0x7F and vex_pp == 1: mnemonic = "VMOVDQA"
            elif opcode == 0x7F and vex_pp == 2: mnemonic = "VMOVDQU"
            elif opcode == 0x58 and vex_pp == 1: mnemonic = "VADDPD"
            elif opcode == 0x59 and vex_pp == 1: mnemonic = "VMULPD"
            elif opcode == 0x54 and vex_pp == 1: mnemonic = "VANDPD"
            elif opcode == 0x55 and vex_pp == 1: mnemonic = "VANDNPD"
            elif opcode == 0x56 and vex_pp == 1: mnemonic = "VORPD"
            elif opcode == 0x57 and vex_pp == 1: mnemonic = "VXORPD"
            elif opcode == 0x7E and vex_pp == 2: mnemonic = "VMOVQ"
            elif opcode == 0x6E and vex_pp == 1: mnemonic = "VMOVQ"
            else: mnemonic = base_mnemonic

            if align_flag == "aligned":
                align_note = " VMOVAPS/VMOVDQA require 16/32-byte alignment - misalignment also causes this crash."
        elif opcode == 0x18:
            mnemonic = "VBROADCASTSS" if not vex_L else "VBROADCASTPS"
            op_type = "broadcast"
        elif opcode == 0x1C:
            mnemonic = "VBROADCASTSS"
            op_type = "broadcast"
    elif vex_m == 2:
        if opcode == 0x17:
            mnemonic = "VPTEST"
            op_type = "test"
        elif opcode == 0x2B:
            mnemonic = "VPACKUSDW"
            op_type = "pack"
    elif vex_m == 3:
        pass

    if mnemonic is None:
        return {
            "is_suicide": False,
            "instruction": f"VEX {vex_m:X} {opcode:02X} ...",
            "explanation": f"AVX/AVX2 instruction (VEX-prefixed, map {vex_m}, opcode 0x{opcode:02X}). Manual analysis needed.",
            "confidence": "LOW",
        }

    has_sib = (rm == 4 and mod != 3)
    mem_op = ""
    base_reg_name = ""

    if mod == 3:
        actual_rm = rm + (8 if not vex_b else 0)
        mem_op = f"{vec_prefix}{actual_rm}"
        op_type = "reg"
    else:
        if has_sib and idx < len(b):
            sib = b[idx]; idx += 1
            sib_base = sib & 0x7
            sib_index = (sib >> 3) & 0x7
            sib_scale = (sib >> 6) & 0x3
            actual_base = sib_base + (8 if not vex_b else 0)
            actual_index = sib_index + (8 if not vex_x else 0)
            b_name = _REG_NAMES_EXT.get(actual_base, f"r{actual_base}")
            i_name = _REG_NAMES_EXT.get(actual_index, f"r{actual_index}")
            b_pfx = "" if actual_base > 7 else "R"
            i_pfx = "" if actual_index > 7 else "R"
            scale_str = f"*{1 << sib_scale}" if sib_scale > 0 else ""
            if sib_base == 5 and mod == 0 and idx + 4 <= len(b):
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4
                mem_op = f"[0x{disp & 0xFFFFFFFF:08X}+{i_pfx}{i_name}{scale_str}]"
                base_reg_name = f"absolute"
            elif sib_index == 4:
                mem_op = f"[{b_pfx}{b_name}]"
                base_reg_name = f"{b_pfx}{b_name}"
            else:
                mem_op = f"[{b_pfx}{b_name}+{i_pfx}{i_name}{scale_str}]"
                base_reg_name = f"{b_pfx}{b_name}"
        elif mod == 0 and rm == 5 and idx + 4 <= len(b):
            disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4
            mem_op = f"[RIP+0x{disp:X}]"
            base_reg_name = "RIP"
        else:
            actual_rm = rm + (8 if not vex_b else 0)
            rm_pfx = "" if actual_rm > 7 else "R"
            base_str = _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")
            base_reg_name = f"{rm_pfx}{base_str}"

            if mod == 1 and idx < len(b):
                disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]; idx += 1
                mem_op = f"[{rm_pfx}{base_str}+0x{disp:X}]" if disp >= 0 else f"[{rm_pfx}{base_str}-0x{abs(disp):X}]"
            elif mod == 2 and idx + 4 <= len(b):
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4
                mem_op = f"[{rm_pfx}{base_str}+0x{disp:X}]"
            else:
                mem_op = f"[{rm_pfx}{base_str}]"

    if op_type == "load":
        instr = f"{mnemonic} {v_reg}, {mem_op}"
        explanation = (f"AVX load from {mem_op}. "
                       f"If {base_reg_name} was null or misaligned at crash time, this is a "
                       f"null pointer read or alignment fault in a SIMD operation.{align_note}")
    elif op_type == "store":
        instr = f"{mnemonic} {mem_op}, {v_reg}"
        explanation = (f"AVX store to {mem_op}. "
                       f"If {base_reg_name} was null or misaligned at crash time, this is a "
                       f"null pointer write or alignment fault in a SIMD operation.{align_note}")
    elif op_type == "arith":
        instr = f"{mnemonic} {v_reg}, {reg_name}, {mem_op}"
        explanation = f"AVX arithmetic operation. If {base_reg_name} was null, the memory operand caused the fault.{align_note}"
    elif op_type == "logic":
        instr = f"{mnemonic} {v_reg}, {reg_name}, {mem_op}"
        explanation = f"AVX logical operation. If {base_reg_name} was null, the memory operand caused the fault.{align_note}"
    elif op_type == "compare":
        instr = f"{mnemonic} {v_reg}, {reg_name}, {mem_op}"
        explanation = f"AVX compare operation. If {base_reg_name} was null, the memory operand caused the fault.{align_note}"
    elif op_type == "broadcast":
        instr = f"{mnemonic} {v_reg}, {mem_op}"
        explanation = f"AVX broadcast from {mem_op}. If {base_reg_name} was null, the source address caused the fault.{align_note}"
    elif op_type == "reg":
        instr = f"{mnemonic} {v_reg}, {mem_op}"
        explanation = f"AVX register-to-register operation (no memory access - crash may be elsewhere)."
    else:
        instr = f"{mnemonic} {v_reg}, {mem_op}"
        explanation = f"AVX instruction. If {base_reg_name} was null or misaligned, the memory operand caused the fault.{align_note}"

    return {
        "is_suicide": False,
        "instruction": instr,
        "explanation": explanation,
        "confidence": "HIGH",
    }


def decode_crash_instruction(mem: bytes, crash_addr: int) -> dict:

    if not mem or len(mem) < 4:
        return {"is_suicide": False, "instruction": "?", "explanation": "Could not read instruction bytes", "confidence": "LOW"}

    b = list(mem[:10])
    idx = 0

    rex = 0
    if 0x40 <= b[idx] <= 0x4F:
        rex = b[idx]; idx += 1

    if idx >= len(b):
        return {"is_suicide": False, "instruction": "?", "explanation": "Short read", "confidence": "LOW"}

    vex = None
    if b[idx] == 0xC5 and idx + 1 < len(b):
        v1 = b[idx + 1]
        vex = {
            "r":     (v1 >> 7) & 1,
            "v":     ((~v1 >> 3) & 0xF),
            "L":     (v1 >> 2) & 1,
            "pp":    v1 & 3,
            "vex3":  False,
        }
        idx += 2
    elif b[idx] == 0xC4 and idx + 2 < len(b):
        v1 = b[idx + 1]
        v2 = b[idx + 2]
        vex = {
            "r":     (v1 >> 7) & 1,
            "x":     (v1 >> 6) & 1,
            "b":     (v1 >> 5) & 1,
            "m":     v1 & 0x1F,
            "w":     (v2 >> 7) & 1,
            "v":     ((~v2 >> 3) & 0xF),
            "L":     (v2 >> 2) & 1,
            "pp":    v2 & 3,
            "vex3":  True,
        }
        idx += 3

    if vex:
        return _decode_vex_instruction(b, idx, vex, crash_addr)

    opcode = b[idx]; idx += 1

    if opcode == 0x89 and idx < len(b):
        modrm = b[idx]; idx += 1
        mod = (modrm >> 6) & 0x3
        reg = (modrm >> 3) & 0x7
        rm  = modrm & 0x7

        rex_w = (rex >> 3) & 0x1
        rex_r = (rex >> 2) & 0x1
        rex_x = (rex >> 1) & 0x1
        rex_b = (rex >> 0) & 0x1

        src_idx = reg + (8 if rex_r else 0)
        src_pfx = "" if src_idx > 7 else ("R" if rex_w else "E")
        src_reg = src_pfx + _REG_NAMES_EXT.get(src_idx, f"r{src_idx}")

        if mod == 0 and rm == 4 and idx < len(b):
            sib_peek = b[idx]
            sib_base_peek = sib_peek & 0x7
            if sib_base_peek == 5 and idx + 5 <= len(b):
                sib = b[idx]; idx += 1
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]
                target = disp & 0xFFFFFFFF
                if target == 0:
                    return {
                        "is_suicide": True,
                        "instruction": f"MOV [0x{target:08X}], {src_reg}",
                        "explanation": (
                            f"The engine explicitly wrote to absolute address 0x0 using a hardcoded address. "
                            f"This encoding (MOV [imm32], reg) cannot happen by accident - "
                            f"the crash address is burned into the instruction itself. "
                            f"This is the Stingray engine suicide pattern."
                        ),
                        "confidence": "HIGH",
                    }
                else:
                    return {
                        "is_suicide": False,
                        "instruction": f"MOV [0x{target:08X}], {src_reg}",
                        "explanation": f"Write to hardcoded address 0x{target:08X} - unusual but not necessarily accidental.",
                        "confidence": "MED",
                    }

        def _decode_mem_op_89(mod, rm, idx):
            has_sib  = (rm == 4 and mod != 3)
            disp     = 0
            base_str = ""

            if has_sib and idx < len(b):
                sib       = b[idx]; idx += 1
                sib_scale = (sib >> 6) & 0x3
                sib_index = (sib >> 3) & 0x7
                sib_base  = sib & 0x7
                scale_val = 1 << sib_scale

                actual_base  = sib_base  + (8 if rex_b else 0)
                actual_index = sib_index + (8 if rex_x else 0)

                no_base  = (sib_base == 5 and mod == 0)
                no_index = (sib_index == 4)

                b_name    = _REG_NAMES_EXT.get(actual_base,  f"r{actual_base}")
                i_name    = _REG_NAMES_EXT.get(actual_index, f"r{actual_index}")
                b_pfx     = "" if actual_base  > 7 else "R"
                i_pfx     = "" if actual_index > 7 else "R"
                scale_str = f"*{scale_val}" if scale_val > 1 else ""

                if no_base and no_index:
                    disp32   = struct.unpack_from("<I", bytes(b[idx:idx+4]))[0] if idx+4 <= len(b) else 0
                    idx     += 4
                    base_str = f"0x{disp32:X}"
                elif no_base:
                    disp32   = struct.unpack_from("<I", bytes(b[idx:idx+4]))[0] if idx+4 <= len(b) else 0
                    idx     += 4
                    base_str = f"0x{disp32:X}+{i_pfx}{i_name}{scale_str}"
                elif no_index:
                    base_str = f"{b_pfx}{b_name}"
                else:
                    base_str = f"{b_pfx}{b_name}+{i_pfx}{i_name}{scale_str}"
            else:
                actual_rm = rm + (8 if rex_b else 0)
                if mod == 0 and rm == 5:
                    base_str = "RIP"
                else:
                    rm_pfx   = "" if actual_rm > 7 else "R"
                    base_str = rm_pfx + _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")

            if mod == 1 and idx < len(b):
                disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]; idx += 1
            elif mod == 2 and idx + 4 <= len(b):
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4

            if disp > 0:
                operand = f"[{base_str}+0x{disp:X}]"
            elif disp < 0:
                operand = f"[{base_str}-0x{abs(disp):X}]"
            else:
                operand = f"[{base_str}]"
            return operand, idx, base_str

        operand, idx, base_str = _decode_mem_op_89(mod, rm, idx)
        return {
            "is_suicide": False,
            "instruction": f"MOV {operand}, {src_reg}",
            "explanation": (
                f"Write through {operand}. "
                f"The base address ({base_str}) was null or near-null at crash time - "
                f"the object pointer was null, already freed, or never initialised."
            ),
            "confidence": "HIGH",
        }

    if opcode == 0x8B and idx < len(b):
        modrm = b[idx]; idx += 1
        mod = (modrm >> 6) & 0x3
        reg = (modrm >> 3) & 0x7
        rm  = modrm & 0x7

        rex_w = (rex >> 3) & 0x1
        rex_r = (rex >> 2) & 0x1
        rex_x = (rex >> 1) & 0x1
        rex_b = (rex >> 0) & 0x1

        dst_idx = reg + (8 if rex_r else 0)
        dst_pfx = "" if dst_idx > 7 else ("R" if rex_w else "E")
        dst_reg = dst_pfx + _REG_NAMES_EXT.get(dst_idx, f"r{dst_idx}")

        def _decode_mem_op(mod, rm, idx):
            has_sib  = (rm == 4 and mod != 3)
            disp     = 0
            base_str = ""

            if has_sib and idx < len(b):
                sib       = b[idx]; idx += 1
                sib_scale = (sib >> 6) & 0x3
                sib_index = (sib >> 3) & 0x7
                sib_base  = sib & 0x7
                scale_val = 1 << sib_scale

                actual_base  = sib_base  + (8 if rex_b else 0)
                actual_index = sib_index + (8 if rex_x else 0)

                no_base  = (sib_base == 5 and mod == 0)
                no_index = (sib_index == 4)

                b_name    = _REG_NAMES_EXT.get(actual_base,  f"r{actual_base}")
                i_name    = _REG_NAMES_EXT.get(actual_index, f"r{actual_index}")
                b_pfx     = "" if actual_base  > 7 else "R"
                i_pfx     = "" if actual_index > 7 else "R"
                scale_str = f"*{scale_val}" if scale_val > 1 else ""

                if no_base and no_index:
                    disp32   = struct.unpack_from("<I", bytes(b[idx:idx+4]))[0] if idx+4 <= len(b) else 0
                    idx     += 4
                    base_str = f"0x{disp32:X}"
                elif no_base:
                    disp32   = struct.unpack_from("<I", bytes(b[idx:idx+4]))[0] if idx+4 <= len(b) else 0
                    idx     += 4
                    base_str = f"0x{disp32:X}+{i_pfx}{i_name}{scale_str}"
                elif no_index:
                    base_str = f"{b_pfx}{b_name}"
                else:
                    base_str = f"{b_pfx}{b_name}+{i_pfx}{i_name}{scale_str}"
            else:
                actual_rm = rm + (8 if rex_b else 0)
                if mod == 0 and rm == 5:
                    base_str = "RIP"
                else:
                    rm_pfx   = "" if actual_rm > 7 else "R"
                    base_str = rm_pfx + _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")

            if mod == 1 and idx < len(b):
                disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]; idx += 1
            elif mod == 2 and idx + 4 <= len(b):
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4

            if disp > 0:
                operand = f"[{base_str}+0x{disp:X}]"
            elif disp < 0:
                operand = f"[{base_str}-0x{abs(disp):X}]"
            else:
                operand = f"[{base_str}]"
            return operand, idx, base_str

        operand, idx, base_str = _decode_mem_op(mod, rm, idx)
        return {
            "is_suicide": False,
            "instruction": f"MOV {dst_reg}, {operand}",
            "explanation": (
                f"Read through {operand}. "
                f"The base address ({base_str}) was null or near-null at crash time - "
                f"the object pointer was null, already freed, or never initialised."
            ),
            "confidence": "HIGH",
        }

    if opcode == 0xFF and idx < len(b):
        modrm = b[idx]
        reg = (modrm >> 3) & 0x7
        if reg == 2:
            return {
                "is_suicide": False,
                "instruction": "CALL [reg]",
                "explanation": "Indirect call through a null/invalid function pointer - vtable corruption or destroyed object.",
                "confidence": "HIGH",
            }

    if opcode == 0xCC:
        return {
            "is_suicide": True,
            "instruction": "INT3",
            "explanation": "Explicit breakpoint/trap instruction - engine triggered an intentional crash.",
            "confidence": "HIGH",
        }
    if opcode == 0x0F and idx < len(b) and b[idx] == 0x0B:
        return {
            "is_suicide": True,
            "instruction": "UD2",
            "explanation": "Undefined instruction - engine triggered an intentional illegal instruction fault.",
            "confidence": "HIGH",
        }

    if opcode == 0xC7 and idx < len(b):
        modrm = b[idx]; idx += 1
        mod = (modrm >> 6) & 0x3
        rm  = modrm & 0x7
        is_abs_null = (mod == 0 and rm == 4 and idx < len(b) and
                       b[idx] == 0x25 and idx + 5 <= len(b) and
                       struct.unpack_from("<I", bytes(b[idx+1:idx+5]))[0] == 0)
        if is_abs_null:
            return {
                "is_suicide": True,
                "instruction": "MOV [0x00000000], imm32",
                "explanation": (
                    "The engine explicitly wrote to absolute address 0x0 using MOV [imm32], imm32. "
                    "The destination is hardcoded as null - this is an intentional Stingray engine suicide."
                ),
                "confidence": "HIGH",
            }
        REG_NAMES = {0:"AX",1:"CX",2:"DX",3:"BX",4:"SP",5:"BP",6:"SI",7:"DI"}
        rex_b = (rex >> 0) & 0x1
        actual_rm = rm + (8 if rex_b else 0)
        base_str = _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")
        pfx = "" if actual_rm > 7 else "R"
        if mod == 1 and idx < len(b):
            disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]; idx += 1
            operand = f"[{pfx}{base_str}+0x{disp:X}]" if disp >= 0 else f"[{pfx}{base_str}-0x{abs(disp):X}]"
        elif mod == 2 and idx + 4 <= len(b):
            disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]; idx += 4
            operand = f"[{pfx}{base_str}+0x{disp:X}]" if disp >= 0 else f"[{pfx}{base_str}-0x{abs(disp):X}]"
        else:
            operand = f"[{pfx}{base_str}]"
        return {
            "is_suicide": False,
            "instruction": f"MOV {operand}, imm32",
            "explanation": (
                f"Immediate value written to {operand}. "
                f"If {pfx}{base_str} was null at crash time this is a null pointer write - "
                f"a struct member assignment on a null or destroyed object."
            ),
            "confidence": "HIGH",
        }

    if opcode == 0x83 and idx < len(b):
        modrm = b[idx]; idx += 1
        mod = (modrm >> 6) & 0x3
        op3 = (modrm >> 3) & 0x7
        rm  = modrm & 0x7
        OP3_NAMES = {0:"ADD",1:"OR",2:"ADC",3:"SBB",4:"AND",5:"SUB",6:"XOR",7:"CMP"}
        op_name = OP3_NAMES.get(op3, f"op{op3}")
        rex_b = (rex >> 0) & 0x1
        actual_rm = rm + (8 if rex_b else 0)
        base_str = _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")
        pfx = "" if actual_rm > 7 else "R"
        if mod == 1 and idx < len(b):
            disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]; idx += 1
            operand = f"[{pfx}{base_str}+0x{disp:X}]" if disp >= 0 else f"[{pfx}{base_str}-0x{abs(disp):X}]"
        elif mod == 0:
            operand = f"[{pfx}{base_str}]"
        else:
            operand = f"[{pfx}{base_str}+...]"
        imm = b[idx] if idx < len(b) else 0
        return {
            "is_suicide": False,
            "instruction": f"{op_name} {operand}, 0x{imm:02X}",
            "explanation": (
                f"Arithmetic operation ({op_name}) on memory at {operand}. "
                f"If {pfx}{base_str} was null at crash time, this is a field access "
                f"on a null or destroyed object."
            ),
            "confidence": "HIGH",
        }

    if opcode == 0x0F and idx < len(b):
        ext = b[idx]; idx += 1
        SSE_MOVES = {0x28: "MOVAPS", 0x29: "MOVAPS", 0x10: "MOVUPS", 0x11: "MOVUPS"}
        if ext in SSE_MOVES:
            mnemonic = SSE_MOVES[ext]
            is_store = ext in (0x29, 0x11)
            if idx < len(b):
                modrm = b[idx]; idx += 1
                mod = (modrm >> 6) & 0x3
                reg = (modrm >> 3) & 0x7
                rm  = modrm & 0x7
                rex_r = (rex >> 2) & 0x1
                rex_b = (rex >> 0) & 0x1
                xmm_idx = reg + (8 if rex_r else 0)
                xmm_reg = f"XMM{xmm_idx}"
                actual_rm = rm + (8 if rex_b else 0)
                pfx = "" if actual_rm > 7 else "R"
                base_str = _REG_NAMES_EXT.get(actual_rm, f"r{actual_rm}")
                if mod == 1 and idx < len(b):
                    disp = struct.unpack_from("<b", bytes(b[idx:idx+1]))[0]
                    mem_op = f"[{pfx}{base_str}+0x{disp:X}]" if disp >= 0 else f"[{pfx}{base_str}-0x{abs(disp):X}]"
                elif mod == 0:
                    mem_op = f"[{pfx}{base_str}]"
                else:
                    mem_op = f"[{pfx}{base_str}+...]"
                instr = f"{mnemonic} {mem_op}, {xmm_reg}" if is_store else f"{mnemonic} {xmm_reg}, {mem_op}"
                align_note = " MOVAPS requires 16-byte alignment - misalignment also causes this crash." if "MOVAPS" in mnemonic else ""
                return {
                    "is_suicide": False,
                    "instruction": instr,
                    "explanation": (
                        f"SSE {'store to' if is_store else 'load from'} {mem_op}. "
                        f"If {pfx}{base_str} was null at crash time, this is a null pointer "
                        f"{'write' if is_store else 'read'} in a SIMD operation.{align_note}"
                    ),
                    "confidence": "HIGH",
                }
        return {
            "is_suicide": False,
            "instruction": f"0F {ext:02X} ...",
            "explanation": "Two-byte instruction at crash site - manual analysis needed.",
            "confidence": "LOW",
        }

    if opcode in (0xF3, 0xF2) and idx < len(b):
        rep_name = "REP" if opcode == 0xF3 else "REPNE"
        next_op = b[idx]
        STRING_OPS = {0xA4:"MOVSB", 0xA5:"MOVSD/Q", 0xA6:"CMPSB", 0xA7:"CMPSD/Q",
                      0xAA:"STOSB", 0xAB:"STOSD/Q", 0xAE:"SCASB", 0xAF:"SCASD/Q"}
        inner_op = STRING_OPS.get(next_op, f"op 0x{next_op:02X}")
        is_copy  = next_op in (0xA4, 0xA5)
        is_set   = next_op in (0xAA, 0xAB)
        if is_copy:
            detail = "Memory copy (memcpy equivalent). RSI=source, RDI=destination, RCX=count. One of these was null."
        elif is_set:
            detail = "Memory set (memset equivalent). RDI=destination, RCX=count. Destination was null."
        else:
            detail = "String/memory operation. Check RSI, RDI, RCX registers for null pointer."
        return {
            "is_suicide": False,
            "instruction": f"{rep_name} {inner_op}",
            "explanation": detail,
            "confidence": "HIGH",
        }

    return {
        "is_suicide": False,
        "instruction": f"opcode 0x{opcode:02X} ...",
        "explanation": f"Unknown instruction at crash site - manual analysis needed.",
        "confidence": "LOW",
    }

def detect_mods(parsed: dict) -> dict:

    modules = parsed.get("modules", [])
    indicators = []

    game_root = None
    game_drive = "c:"
    for m in modules:
        name = m["name"]
        nl   = name.lower().replace("/", "\\")
        p = PureWindowsPath(name)
        if p.suffix.lower() != ".exe":
            continue
        parts = p.parts
        if len(parts) < 2:
            continue
        game_drive = parts[0].lower().rstrip("\\")
        for j, part in enumerate(parts):
            if part.lower() in ("bin", "binaries", "win64", "win32", "x64", "shipping"):
                game_root = str(PureWindowsPath(*parts[:j])).lower()
                break
        if not game_root:
            game_root = str(p.parent).lower()
        break

    SAFE_PREFIXES = [
        "\\windows\\",
        "\\programdata\\",
        "\\program files (x86)\\steam\\",
        "\\program files\\steam\\",
        "\\steamapps\\",
        "\\program files\\nvidia corporation\\",
        "\\program files (x86)\\nvidia corporation\\",
        "\\programdata\\nvidia\\",
        "\\programdata\\nvidia corporation\\",
        "\\program files\\amd\\",
        "\\program files (x86)\\amd\\",
        "\\program files\\intel\\",
        "\\program files (x86)\\intel\\",
        "\\program files\\microsoft visual c++",
        "\\program files (x86)\\microsoft visual c++",
        "\\program files\\common files\\microsoft shared\\",
        "\\program files (x86)\\common files\\microsoft shared\\",
        "\\program files\\obs-studio\\",
        "\\program files (x86)\\obs-studio\\",
        "\\program files\\nvidia geforce experience\\",
        "\\program files (x86)\\nvidia geforce experience\\",
        "\\program files\\fraps\\",
        "\\program files (x86)\\msi afterburner\\",
        "\\program files\\msi afterburner\\",
        "\\program files\\rivatuner statistics server\\",
        "\\program files (x86)\\rivatuner statistics server\\",
        "\\program files\\playnite\\",
    ]
    if game_root:
        SAFE_PREFIXES.append(game_root)
    if game_drive and game_drive != "c:":
        SAFE_PREFIXES.extend([
            f"{game_drive}\\windows\\",
            f"{game_drive}\\programdata\\",
        ])

    NVIDIA_DLLS = {
        "nvd3dumx.dll", "nvwgf2umx.dll", "nvwgf2um.dll",
        "nvcuda.dll", "nvcuvid.dll", "nvfatbinaryloader.dll",
        "nvoglv64.dll", "nvoglv32.dll",
        "nvtelemetry.dll", "nvspcap64.dll", "nvspcap.dll",
        "nvppex.dll", "nvmemmapmapstoragex.dll", "nvmessagebus.dll",
        "nvgpucomp64.dll", "nvldumdx.dll",
        "nvgamefeatures.dll", "nvshadowplay.dll",
        "nvsmartmaxapp.dll", "nvcpl.dll",
        "nvngx.dll", "nvngx_dlss.dll", "nvngx_dlssg.dll",
        "nvngx_dlssd.dll", "sl.common.dll", "sl.dlss.dll",
        "sl.dlss_g.dll", "sl.reflex.dll", "sl.nis.dll",
        "nvapi64.dll", "nvapi.dll",
        "nvsdk_ngx_s.dll", "nvlatencysdk.dll",
        "gfe3.dll", "nggamefeatures.dll",
    }
    AMD_DLLS = {
        "amd_ags_x64.dll", "amd_ags_x86.dll",
        "amdvulkan64.dll", "amdvulkan32.dll",
        "amfrt64.dll", "amfrt32.dll",
        "amd_fidelityfx_upscaler_dx12.dll", "amd_fidelityfx_upscaler_dx11.dll",
        "amdpsp.dll", "atiuxpag.dll",
    }
    INTEL_DLLS = {
        "igdumdim64.dll", "igdumdim32.dll",
        "intc_app_api.dll", "intcigs.dll",
        "libxess.dll", "xess.dll",
    }
    SYSTEM_CAPTURE_DLLS = {
        "graphics-hook64.dll", "graphics-hook32.dll",
        "obsover64.dll", "obsover32.dll",
        "rtsshooks64.dll", "rtsshooks.dll",
        "gamebarftics.dll", "gamebarpresencewriter.dll",
    }

    KNOWN_GAME_DLLS = (
        NVIDIA_DLLS | AMD_DLLS | INTEL_DLLS | SYSTEM_CAPTURE_DLLS | {
        "lua51.dll", "game.dll",
        "steam_api64.dll", "steam_api.dll", "gameoverlayrenderer64.dll",
        "steamclient64.dll", "vstdlib_s64.dll", "tier0_s64.dll",
        "bink2w64.dll", "bink2w32.dll",
        "libcurl.dll", "libcurl-x64.dll",
        "dstorage.dll", "dstoragecore.dll",
        "winpixeventruntime.dll",
        "playfabmultiplayerwin.dll", "partywin.dll",
        "crs-client.dll",
        "npggnt64.des", "npsc64.des",
        "wwise_pluginw64_release.dll", "wwise_pluginw64_debug.dll",
        "auroheadphone_w64r.dll", "akorthographicverb_w64r.dll",
        "fmodstudio64.dll", "fmodstudiol64.dll", "fmod64.dll", "fmodl64.dll",
        "physxdevice64.dll", "physx3_x64.dll", "physx3common_x64.dll",
        "nvphysxgpu64.dll",
        "level_generation_pluginw64_release.dll",
        "level_generation_pluginw64_debug.dll",
        "easyanticheat.dll", "easyanticheat_launcher.dll",
        "dxcompiler.dll", "dxil.dll", "d3d12core.dll",
        "xaudio2_9.dll", "xaudio2_8.dll", "xaudio2_7.dll", "x3daudio1_7.dll",
        "mfplat.dll", "mfreadwrite.dll",
        "concrt140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
        "vcruntime140_1.dll",
        "d3d11on12.dll", "dxilconv.dll", "d3dscache.dll", "dxcore.dll",
        "msvcr110.dll", "msvcr120.dll", "msvcr100.dll",
        "sentry.dll", "backtrace.dll", "crashpad_handler.exe",
        "battleye.dll", "bedaisy.sys",
        "discord_game_sdk.dll", "discordrpc.dll",
        "vivoxsdk.dll", "ortp.dll",
        "telemetry2_x64.dll", "rad_telemetry.dll",
    })

    MOD_MANAGER_PATHS = {
        "vortex":           "Vortex mod manager",
        "nexusmods":        "Nexus Mods",
        "mod organizer":    "Mod Organizer",
        "modengine":        "ModEngine",
        "elden mod loader": "Elden Mod Loader",
        "dinput8.dll":      None,
        "\\mods\\":         "Mods folder",
        "\\mod\\":          "Mod folder",
        "\\workshop\\":     "Steam Workshop mod",
        "\\addons\\":       "Addons folder",
        "\\override\\":     "Override folder (Stingray mod path)",
        "\\patch\\":         "Patch folder (common mod override location)",
        "\\content\\":       "Content override folder",
        "\\custom\\":        "Custom content folder",
        "modengine2":       "ModEngine2 (Souls modding framework)",
        "reshade":          "ReShade (post-processing / D3D hook)",
        "minhook":          "MinHook (function hooking - common mod injection vector)",
        "\\xinput\\":        "XInput hook (common mod injection point)",
    }

    PROXY_SYSTEM_DLLS: dict[str, str] = {
        "dxgi.dll":       "DXGI proxy - likely ReShade or another D3D post-process hook",
        "d3d12.dll":      "D3D12 proxy - likely ReShade or a D3D12 hook",
        "d3d11.dll":      "D3D11 proxy - likely ReShade or a D3D11 hook",
        "d3d10.dll":      "D3D10 proxy - likely ReShade or a D3D10 hook",
        "d3d9.dll":       "D3D9 proxy - likely ReShade, ENB, or a D3D9 hook",
        "opengl32.dll":   "OpenGL proxy - likely an OpenGL hook or injector",
        "dinput8.dll":    "DInput8 proxy - classic mod injection vector",
        "dinput.dll":     "DInput proxy - classic mod injection vector",
        "winmm.dll":      "WinMM proxy - common mod injection vector (used by many mod loaders)",
        "version.dll":    "Version proxy - common lightweight mod injection vector",
        "wsock32.dll":    "WinSock proxy - network hook (uncommon in games, suspicious)",
        "xinput1_3.dll":  "XInput 1.3 proxy - controller hook or mod injection vector",
        "xinput1_4.dll":  "XInput 1.4 proxy - controller hook or mod injection vector",
        "dsound.dll":     "DirectSound proxy - audio hook or legacy mod injection",
    }

    for m in modules:
        name  = m["name"]
        nl    = name.lower().replace("/", "\\")
        sn    = PureWindowsPath(name).name
        snl   = sn.lower()

        is_safe = any(
            (p.startswith("\\") and p in nl) or
            nl.startswith(p)
            for p in SAFE_PREFIXES
        )
        is_known_dll = snl in {k.lower() for k in KNOWN_GAME_DLLS}
        is_plugin = "\\plugins\\" in nl

        is_exe = PureWindowsPath(name).suffix.lower() == ".exe"
        if not is_safe and not is_known_dll and not is_plugin and not is_exe:
            indicators.append({
                "type":   "unknown_dll",
                "path":   name,
                "detail": f"DLL loaded from unexpected location: {name}",
            })

        _proxy_name = name.replace("\\", "/").split("/")[-1].lower()
        if _proxy_name in PROXY_SYSTEM_DLLS:
            is_in_system32 = ("\\windows\\" in nl or "\\system32\\" in nl
                               or "\\syswow64\\" in nl or "\\winsxs\\" in nl)
            if not is_in_system32:
                indicators.append({
                    "type":   "proxy_dll",
                    "path":   name,
                    "detail": f"Proxy DLL in game folder: {_proxy_name} - {PROXY_SYSTEM_DLLS[_proxy_name]}",
                })

        for sig, label in MOD_MANAGER_PATHS.items():
            if sig in nl:
                if sig == "dinput8.dll" and is_safe:
                    continue
                detail = f"{label}: {name}" if label else f"Possible mod hook via {sn}: {name}"
                indicators.append({
                    "type":   "mod_manager",
                    "path":   name,
                    "detail": detail,
                })

        if "appdata" in nl and "\\local\\" in nl and game_root and game_root not in nl:
            indicators.append({
                "type":   "appdata_mod",
                "path":   name,
                "detail": f"File loaded from AppData (possible mod config): {name}",
            })

    seen = set()
    unique = []
    for ind in indicators:
        if ind["detail"] not in seen:
            seen.add(ind["detail"])
            unique.append(ind)

    has_mods = len(unique) > 0

    SEVERITY = {
        "proxy_dll":   "HIGH",
        "mod_manager": "HIGH",
        "unknown_dll": "HIGH",
        "appdata_mod": "MED",
    }
    severities = [SEVERITY.get(i["type"], "LOW") for i in unique]
    confidence = ("HIGH" if "HIGH" in severities else
                  "MED"  if "MED"  in severities else
                  "LOW"  if severities else "LOW")

    for ind in unique:
        ind["severity"] = SEVERITY.get(ind["type"], "LOW")

    return {
        "has_mods":   has_mods,
        "confidence": confidence,
        "game_root":  game_root,
        "indicators": unique,
    }

PATTERN_FILE = resource_path("crash_patterns.json")

def _load_pattern_file() -> dict:

    if not PATTERN_FILE.exists():
        return {"builtin_patterns": [], "patterns": []}
    try:
        with open(PATTERN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not load crash_patterns.json: {e}")
        return {"builtin_patterns": [], "patterns": []}

def load_custom_patterns() -> list:

    data = _load_pattern_file()
    return [p for p in data.get("patterns", []) if p.get("enabled", True)]

def get_builtin_override(pattern_id: str) -> "dict | None":

    data = _load_pattern_file()
    for p in data.get("builtin_patterns", []):
        if p.get("id") == pattern_id:
            if not p.get("enabled", True):
                return None
            return p
    return None

def _match_custom_patterns(parsed: dict, decoded_instr: "dict | None",
                           mods: dict) -> "dict | None":
    all_matches = _match_all_custom_patterns(parsed, decoded_instr, mods)
    return all_matches[0] if all_matches else None


def _match_all_custom_patterns(parsed: dict, decoded_instr: "dict | None",
                               mods: dict) -> list:

    patterns = load_custom_patterns()
    if not patterns:
        return []

    ex       = parsed.get("exception") or {}
    modules  = parsed.get("modules", [])
    threads  = parsed.get("threads", [])
    ex_code  = int(ex.get("code", "0"), 16) if ex else 0
    params   = ex.get("params", [])
    fault_addr = int(params[1], 16) if len(params) >= 2 else 0
    ex_addr  = int(ex.get("address", "0"), 16) if ex else 0
    all_mods = " ".join(PureWindowsPath(m["name"]).name.lower() for m in modules)
    CRASH_HANDLERS = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    def mod_for_addr(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name
            except Exception:
                pass
        return None

    crash_mod  = mod_for_addr(ex_addr) or ""
    is_suicide = bool(decoded_instr and decoded_instr.get("is_suicide"))

    active_mods = []
    for t in threads:
        rip = t.get("rip", 0)
        mod = mod_for_addr(rip)
        if mod:
            full = next((m["name"] for m in modules if PureWindowsPath(m["name"]).name == mod), "")
            fl   = full.lower().replace("/", "\\")
            if "\\windows\\" not in fl and mod.lower() not in CRASH_HANDLERS:
                active_mods.append((mod.lower(), 0))
        rsp = t.get("rsp", 0)
        if rsp:
            for depth, (addr, smod, soff) in enumerate(walk_stack(parsed, rsp, max_frames=8), start=1):
                if not smod: continue
                full = next((m["name"] for m in modules if PureWindowsPath(m["name"]).name == smod), "")
                fl   = full.lower().replace("/", "\\")
                if "\\windows\\" not in fl and smod.lower() not in CRASH_HANDLERS:
                    active_mods.append((smod.lower(), depth))

    results = []
    for p in patterns:
        m = p.get("match", {})
        try:
            if "ex_code" in m:
                if ex_code != int(m["ex_code"], 16): continue
            if "fault_addr_max" in m:
                if fault_addr > int(m["fault_addr_max"]): continue
            if "fault_addr_min" in m:
                if fault_addr < int(m["fault_addr_min"]): continue
            if "is_suicide" in m:
                if bool(m["is_suicide"]) != is_suicide: continue
            if "crash_mod_contains" in m:
                if m["crash_mod_contains"].lower() not in crash_mod.lower(): continue
            if "crash_offset" in m:
                try:
                    target_off = int(m["crash_offset"], 16) if isinstance(m["crash_offset"], str) else int(m["crash_offset"])
                except Exception:
                    continue
                actual_off = None
                for mm in modules:
                    try:
                        base = int(mm["base"], 16)
                        if base <= ex_addr < base + mm["size"]:
                            actual_off = ex_addr - base
                            break
                    except Exception:
                        pass
                if actual_off != target_off:
                    continue
            if "stack_contains" in m:
                kw         = m["stack_contains"].lower()
                max_depth  = int(m.get("stack_contains_depth", 9999))
                if not any(kw in mod and depth <= max_depth for mod, depth in active_mods): continue
            if "module_loaded" in m:
                if m["module_loaded"].lower() not in all_mods: continue
            if "module_not_loaded" in m:
                if m["module_not_loaded"].lower() in all_mods: continue
            if "active_thread_mod_contains" in m:
                kw = m["active_thread_mod_contains"].lower()
                if not any(kw in mod for mod, _ in active_mods): continue
        except Exception:
            continue

        results.append({
            "id":             p.get("id", "CUSTOM"),
            "name":           p.get("name", "Custom pattern"),
            "player_message": p.get("player_message", ""),
            "fix":            p.get("fix", []),
            "dev_note":       p.get("dev_note", ""),
            "confidence":     p.get("confidence", "MED"),
            "is_custom":      True,
        })
    return results


def _builtin(pattern_id: str, default: dict) -> "dict | None":

    override = get_builtin_override(pattern_id)
    if override is None and _load_pattern_file().get("builtin_patterns"):
        return default
    if override is None:
        return default
    merged = dict(default)
    for key in ("name", "player_message", "fix", "dev_note", "confidence"):
        if key in override:
            merged[key] = override[key]
    return merged

def _match_all_patterns(parsed: dict, decoded_instr: "dict | None",
                        mods: dict, rootcause: list) -> list:
    custom_matches = _match_all_custom_patterns(parsed, decoded_instr, mods)
    custom_ids     = {c["id"] for c in custom_matches}

    builtin = _match_patterns(parsed, decoded_instr, mods, rootcause)
    combined = list(custom_matches)
    if builtin and builtin["id"] not in custom_ids:
        combined.append(builtin)

    conf_rank = {"HIGH": 0, "MED": 1, "LOW": 2}
    combined.sort(key=lambda p: conf_rank.get(p.get("confidence", "LOW"), 3))
    return combined


def _match_patterns(parsed: dict, decoded_instr: "dict | None",
                    mods: dict, rootcause: list) -> "dict | None":

    custom = _match_custom_patterns(parsed, decoded_instr, mods)
    if custom:
        return custom

    ex       = parsed.get("exception") or {}
    modules  = parsed.get("modules", [])
    threads  = parsed.get("threads", [])

    ex_code    = int(ex.get("code",  "0"), 16) if ex else 0
    params     = ex.get("params", [])
    fault_addr = int(params[1], 16) if len(params) >= 2 else 0
    ex_addr    = int(ex.get("address", "0"), 16) if ex else 0
    all_mods   = " ".join(PureWindowsPath(m["name"]).name.lower() for m in modules)

    CRASH_HANDLERS  = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                       "sentry.dll", "backtrace.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    GPU_DRIVER_FRAGMENTS = (
        "amdxc64", "amdxc32", "amdxx64", "amdxx32",
        "atidxx64", "atidxx32", "amdihk64",
        "nvwgf2umx", "nvwgf2um", "nvd3dumx", "nvd3dum",
        "nvgpucomp64", "nvldumdx", "nvppex",
        "amdcc64", "amdcc",
        "igdumd64", "igdumd32", "igxelpicd64",
        "igd10um64", "igd10iumd64", "igc64", "igdgmm64",
        "igd12dxva64",
    )

    def mod_for_addr(addr: int) -> "str | None":
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name
            except Exception:
                pass
        return None

    def full_path_for_mod(mod_name: str) -> str:
        return next((m["name"] for m in modules
                     if PureWindowsPath(m["name"]).name == mod_name), "").lower().replace("/", "\\")

    def is_game_mod(mod_name: str) -> bool:

        if not mod_name:
            return False
        if mod_name.lower() in CRASH_HANDLERS:
            return False
        full = full_path_for_mod(mod_name)
        return not any(full.startswith(p) for p in SYSTEM_PREFIXES)

    def build_active_subsystems() -> dict:
        subsystems = {}

        def record(mod_name, depth, source):
            key = mod_name.lower()
            if key in CRASH_HANDLERS:
                return
            entry = subsystems.setdefault(
                key, {"min_depth": depth, "source": source, "hits": 0}
            )
            entry["hits"] += 1
            if source == "crash_chain" and entry["source"] != "crash_chain":
                entry["source"] = "crash_chain"
                entry["min_depth"] = depth
            elif depth < entry["min_depth"]:
                entry["min_depth"] = depth

        chain = parsed.get("_stack_chain_extended", [])
        for depth, entry in enumerate(chain):
            if len(entry) == 4:
                _, mod_name, _, _ = entry
            elif len(entry) == 3:
                _, mod_name, _ = entry
            else:
                mod_name = None
            if mod_name:
                record(mod_name, depth, "crash_chain")

        for t in _active_game_threads_at_crash(parsed):
            mod_name = t.get("module", "")
            if mod_name:
                record(mod_name, 999, "other_thread")

        return subsystems

    AUDIO_ENGINE_DLLS = {
        "wwise_pluginw64_release.dll", "wwise_pluginw64_debug.dll",
        "aksoundengine.dll", "akorthographicverb_w64r.dll",
        "auroheadphone_w64r.dll",
        "fmodstudio64.dll", "fmodstudiol64.dll", "fmod64.dll", "fmodl64.dll",
        "xaudio2_9.dll", "xaudio2_8.dll", "xaudio2_7.dll", "x3daudio1_7.dll",
        "mfplat.dll", "mfreadwrite.dll",
    }
    UI_DLLS = {
        "hud.dll", "ui.dll", "widget.dll", "scaleform.dll",
        "hud_ui.dll", "ui_system.dll", "uisystem.dll",
    }

    _CONF_RANK = {"HIGH": 0, "MED": 1, "LOW": 2}

    def subsystem_match(active: dict, keywords: list, known_names: set = None,
                        near_frames: int = 4, min_hits_if_deep: int = 2):
        best = None
        for mod, info in active.items():
            matched = False
            if known_names and mod in known_names:
                matched = True
            elif not known_names:
                for kw in keywords:
                    if re.search(rf"{re.escape(kw)}", mod):
                        matched = True
                        break
            if not matched:
                continue

            if info["source"] == "crash_chain" and info["min_depth"] <= near_frames:
                conf = "HIGH"
            elif info["source"] == "crash_chain" and info["hits"] >= min_hits_if_deep:
                conf = "MED"
            elif info["source"] == "crash_chain":
                conf = "LOW"
            else:
                conf = "LOW"

            if best is None or _CONF_RANK[conf] < _CONF_RANK[best[0]]:
                best = (conf, f"{mod} (depth {info['min_depth']}, "
                               f"{info['hits']}x, {info['source']})")
        return best or (None, None)

    crash_mod  = mod_for_addr(ex_addr)
    crash_mod_l = (crash_mod or "").lower()
    is_suicide  = bool(decoded_instr and decoded_instr.get("is_suicide"))
    if not is_suicide:
        stingray_suicide, _ = _is_stingray_suicide(parsed)
        if stingray_suicide:
            is_suicide = True

    if is_suicide:
        active = build_active_subsystems()

        conf, evidence = subsystem_match(active, ["dstorage", "dstoragecore"])
        if conf:
            return _builtin("SUICIDE_DSTORAGE", {
                "id": "SUICIDE_DSTORAGE",
                "name": "Engine suicide during DirectStorage streaming",
                "player_message": (
                    "The game detected an internal error while loading assets via DirectStorage "
                    "and shut itself down. This is often caused by outdated GPU drivers that "
                    "don't properly support DirectStorage."
                ),
                "fix": [
                    "Update your GPU drivers to the latest version",
                    "If on AMD: use DDU (Display Driver Uninstaller) to fully clean old drivers first",
                    "Verify game files through Steam",
                    "If the crash persists, disable DirectStorage in game settings if available",
                ],
                "dev_note": f"Engine suicide with DirectStorage on active stack ({evidence}) - likely DS decompression or IO error",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["lua"])
        if conf:
            return _builtin("SUICIDE_LUA", {
                "id": "SUICIDE_LUA",
                "name": "Engine suicide from Lua scripting error",
                "player_message": (
                    "The game detected a scripting error and shut itself down. "
                    "This can be caused by mods that modify game scripts, or a bug in a game update."
                ),
                "fix": [
                    "If you have mods installed, remove them and try again",
                    "Verify game files through Steam",
                    "Check the game log file for a Lua error message",
                ],
                "dev_note": f"Engine suicide with Lua on active stack ({evidence}) - check Lua stack and recent script changes",
                "confidence": conf,
            })

        gpu_present = any(any(frag in s for frag in GPU_DRIVER_FRAGMENTS) for s in active)
        d3d12core_present = any("d3d12core" in s for s in active)
        conf, evidence = subsystem_match(active, [], known_names=AUDIO_ENGINE_DLLS)
        if conf and not gpu_present and not d3d12core_present:
            return _builtin("SUICIDE_AUDIO", {
                "id": "SUICIDE_AUDIO",
                "name": "Engine suicide during audio playback",
                "player_message": (
                    "The game detected an error in the audio system and shut itself down. "
                    "This can happen with certain audio devices or driver configurations."
                ),
                "fix": [
                    "Try setting your audio output to stereo instead of surround sound",
                    "Update your audio drivers",
                    "Try disabling audio enhancements in Windows sound settings",
                    "Check the game log for audio error messages",
                ],
                "dev_note": f"Engine suicide with Wwise/audio on active stack ({evidence}) - check audio event / bank loading",
                "confidence": conf,
            })

        if gpu_present:
            gpu_mod = next((s for s in active if any(frag in s for frag in GPU_DRIVER_FRAGMENTS)), "GPU driver")
            gpu_info = active.get(gpu_mod, {"min_depth": 999, "hits": 0, "source": "unknown"})
            if gpu_info["source"] == "crash_chain" and gpu_info["min_depth"] <= 4:
                gpu_conf = "HIGH"
            elif gpu_info["source"] == "crash_chain":
                gpu_conf = "MED"
            else:
                gpu_conf = "LOW"
            return _builtin("SUICIDE_GPU", {
                "id": "SUICIDE_GPU",
                "name": "Engine suicide during GPU rendering",
                "player_message": (
                    "The game detected an error in the graphics system and shut itself down. "
                    "This is most commonly caused by outdated or unstable GPU drivers, "
                    "or a GPU hardware issue."
                ),
                "fix": [
                    "Update your GPU drivers to the latest version",
                    "If overclocking your GPU, revert to stock settings",
                    "Try lowering graphics settings, especially ray tracing",
                    "Check GPU temperature - overheating can cause this",
                ],
                "dev_note": f"Engine suicide with GPU driver ({gpu_mod}, depth {gpu_info['min_depth']}, {gpu_info['hits']}x) on active stack - device lost or driver timeout",
                "confidence": gpu_conf,
            })

        conf, evidence = subsystem_match(active, ["network", "enet", "raknet"])
        if conf:
            return _builtin("SUICIDE_NETWORK", {
                "id":   "SUICIDE_NETWORK",
                "name": "Engine suicide during network operation",
                "player_message": (
                    "The game detected a network error and shut itself down. "
                    "This can happen during connection drops, host migration, "
                    "or if the game server sends unexpected data."
                ),
                "fix": [
                    "Check your internet connection stability",
                    "Try a wired connection instead of Wi-Fi",
                    "Check the game log for network error messages",
                    "Try again - intermittent network issues often resolve themselves",
                ],
                "dev_note": f"Engine suicide with network on active stack ({evidence}) - packet error or RPC on dead object",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["physx", "physics", "nvphys"])
        if conf:
            return _builtin("SUICIDE_PHYSICS", {
                "id":   "SUICIDE_PHYSICS",
                "name": "Engine suicide during physics simulation",
                "player_message": (
                    "The game detected a physics simulation error and shut itself down. "
                    "This can happen with unusual in-game configurations or collisions."
                ),
                "fix": [
                    "Check the game log for physics error messages",
                    "Verify game files through Steam",
                    "Note what was happening in-game (large explosion? ragdoll?)",
                ],
                "dev_note": f"Engine suicide with PhysX on active stack ({evidence}) - NaN transform or destroyed actor",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["savegame", "save_game", "gamesave"])
        if conf:
            return _builtin("SUICIDE_SAVEGAME", {
                "id":   "SUICIDE_SAVEGAME",
                "name": "Engine suicide during save/load operation",
                "player_message": (
                    "The game detected an error while saving or loading and shut itself down. "
                    "This can happen with corrupted save data, version mismatches, or "
                    "async save operations completing after level unload."
                ),
                "fix": [
                    "Check if your save file is corrupted - try loading an earlier save",
                    "Verify game files through Steam",
                    "Check the game log for save/load error messages",
                    "If the crash happens on load, the save file may be from an incompatible game version",
                ],
                "dev_note": f"Engine suicide with savegame on active stack ({evidence}) - save version mismatch or async save after unload",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["level", "streaming", "world"])
        if conf:
            return _builtin("SUICIDE_LEVEL_STREAMING", {
                "id":   "SUICIDE_LEVEL_STREAMING",
                "name": "Engine suicide during level streaming",
                "player_message": (
                    "The game detected an error while streaming level data and shut itself down. "
                    "This can happen when a level fails to load, or objects in an unloading level "
                    "are still being accessed."
                ),
                "fix": [
                    "Verify game files through Steam - the level data may be corrupted",
                    "Check the game log for streaming/load errors",
                    "Note which level or area you were entering when it crashed",
                    "Try lowering texture/streaming settings if available",
                ],
                "dev_note": f"Engine suicide with level/streaming on active stack ({evidence}) - level unload race or missing level data",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["anim", "skeleton", "blend"])
        if conf:
            return _builtin("SUICIDE_ANIMATION", {
                "id":   "SUICIDE_ANIMATION",
                "name": "Engine suicide during animation update",
                "player_message": (
                    "The game detected an error in the animation system and shut itself down. "
                    "This can happen with mismatched skeletons, deleted animation states, "
                    "or bone index out of range."
                ),
                "fix": [
                    "Check the game log for animation error messages",
                    "Verify game files through Steam",
                    "Note what your character was doing when it crashed (loading screen? combat?)",
                ],
                "dev_note": f"Engine suicide with animation on active stack ({evidence}) - mismatched skeleton or deleted anim state",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["hud", "widget", "scaleform"], known_names=UI_DLLS)
        if conf:
            return _builtin("SUICIDE_UI", {
                "id":   "SUICIDE_UI",
                "name": "Engine suicide during UI/HUD update",
                "player_message": (
                    "The game detected an error in the UI system and shut itself down. "
                    "This can happen when a UI widget accesses a destroyed entity, or "
                    "a font/texture atlas is not loaded when the HUD draws."
                ),
                "fix": [
                    "Check the game log for UI/HUD error messages",
                    "Verify game files through Steam",
                    "Note what was on screen when it crashed (menu? HUD element?)",
                ],
                "dev_note": f"Engine suicide with UI/HUD on active stack ({evidence}) - widget accessing destroyed entity or missing atlas",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["entity", "unit"])
        if conf:
            return _builtin("SUICIDE_ENTITY", {
                "id":   "SUICIDE_ENTITY",
                "name": "Engine suicide during entity/unit update",
                "player_message": (
                    "The game detected an error in the entity system and shut itself down. "
                    "This can happen when a component is accessed on a destroyed entity, "
                    "or an entity ID is reused before all references were cleared."
                ),
                "fix": [
                    "Check the game log for entity/unit error messages",
                    "Verify game files through Steam",
                    "Note what was happening in-game (spawning? mission event? enemy death?)",
                ],
                "dev_note": f"Engine suicide with entity/unit on active stack ({evidence}) - use-after-free or stale entity ID",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["resource", "package", "bundle"])
        if conf:
            return _builtin("SUICIDE_RESOURCE", {
                "id":   "SUICIDE_RESOURCE",
                "name": "Engine suicide during resource loading",
                "player_message": (
                    "The game detected an error while loading a resource (texture, model, sound) "
                    "and shut itself down. This is often caused by corrupted or missing game files."
                ),
                "fix": [
                    "Verify game files through Steam - a resource file may be corrupted or missing",
                    "Check the game log for resource loading errors",
                    "Note which level or area you were entering when it crashed",
                    "If modded, remove mods that replace game assets",
                ],
                "dev_note": f"Engine suicide with resource_manager/package on active stack ({evidence}) - corrupted or missing resource",
                "confidence": conf,
            })

        conf, evidence = subsystem_match(active, ["shader", "dxcompiler", "d3dcompiler"])
        if conf:
            return _builtin("SUICIDE_SHADER", {
                "id":   "SUICIDE_SHADER",
                "name": "Engine suicide during shader compilation",
                "player_message": (
                    "The game detected an error during shader compilation and shut itself down. "
                    "This is usually caused by outdated GPU drivers that don't support the "
                    "required shader model."
                ),
                "fix": [
                    "Update your GPU drivers to the latest version",
                    "If on a very old GPU, it may not support the required shader model",
                    "Check the game log for shader compilation errors",
                    "Try lowering graphics settings, especially shader-heavy features",
                ],
                "dev_note": f"Engine suicide with shader/dxcompiler on active stack ({evidence}) - shader permutation compile failure",
                "confidence": conf,
            })

        return _builtin("SUICIDE_GENERIC", {
            "id": "SUICIDE_GENERIC",
            "name": "Engine detected an internal error and shut down",
            "player_message": (
                "The game detected something unexpected internally and safely shut itself down "
                "rather than continuing in a broken state. The engine log file contains "
                "the actual error message."
            ),
            "fix": [
                "Enable logging with Steam launch option --log-to-file, then check %APPDATA%\\Arrowhead\\Helldivers 2\\logs for the engine log",
                "Verify game files through Steam",
                "Share the .log AND .dmp files with the 418th",
            ],
            "dev_note": "Generic engine suicide - no subsystem matched in crash chain. Check engine log for trigger.",
            "confidence": "MED",
        })

    _has_nvidia = any("nvwgf" in m or "nvgpucomp" in m or "nvd3d" in m
                      for m in all_mods.split())
    _has_intel_igpu = any("igd10um" in m or "igc64" in m or "igdgmm" in m
                          for m in all_mods.split())

    if crash_mod and any(frag in crash_mod_l for frag in GPU_DRIVER_FRAGMENTS):
        if (_has_nvidia and _has_intel_igpu
                and ex_code == 0xC0000005
                and not is_suicide):
            return _builtin("DUAL_GPU_DRIVER_CRASH", {
                "id":   "DUAL_GPU_DRIVER_CRASH",
                "name": "GPU driver crash on dual-GPU system (NVIDIA + Intel iGPU)",
                "player_message": (
                    "Your system has both an NVIDIA dedicated GPU and an Intel integrated GPU. "
                    "The game crashed inside a GPU driver. On dual-GPU systems this is often "
                    "caused by the game running on the wrong GPU, or a conflict between the two drivers."
                ),
                "fix": [
                    "Open NVIDIA Control Panel -> Manage 3D Settings -> Program Settings "
                    "-> add Helldivers 2 -> set preferred GPU to your NVIDIA card",
                    "Update both your NVIDIA and Intel GPU drivers",
                    "In Windows Display Settings, set the NVIDIA card as the primary GPU",
                    "If on a laptop, disable the Intel iGPU in Device Manager and test",
                    "Update your NVIDIA drivers - use DDU for a clean install if issues persist",
                ],
                "dev_note": (
                    "Crash in GPU driver DLL on dual-GPU system (NVIDIA + Intel iGPU both loaded). "
                    "Check which adapter D3D12 is selecting at runtime - possible iGPU fallback."
                ),
                "confidence": "HIGH",
            })

        vendor = "AMD"    if any(k in crash_mod_l for k in ("amd", "ati")) else \
                 "NVIDIA" if any(k in crash_mod_l for k in ("nvwgf", "nvd3d", "nvgpucomp", "nvldumdx", "nvppex")) else \
                 "Intel"
        return _builtin("GPU_DRIVER_CRASH", {
            "id":   "GPU_DRIVER_CRASH",
            "name": f"{vendor} GPU driver crashed",
            "player_message": (
                f"The {vendor} graphics driver crashed inside the game. "
                f"This is almost always a driver bug or hardware issue, not a game bug."
            ),
            "fix": [
                f"Update your {vendor} GPU drivers to the latest version",
                "Use DDU (Display Driver Uninstaller) to fully clean old drivers first",
                "If overclocking your GPU or VRAM, revert to stock settings",
                "Check GPU temperature under load",
                "If on a laptop, make sure the game is using the dedicated GPU, not the integrated one",
            ],
            "dev_note": f"Crash address inside {crash_mod} - GPU driver fault, not engine code",
            "confidence": "HIGH",
        })

    if ex_code in (0x887A0005, 0x887A0006, 0x887A0007, 0x887A0020):
        DXGI_NAMES = {
            0x887A0005: "GPU stopped responding (TDR)",
            0x887A0006: "GPU device removed",
            0x887A0007: "GPU device reset",
            0x887A0020: "GPU driver internal error",
        }
        return _builtin("DXGI_DEVICE_LOST", {
            "id":   "DXGI_DEVICE_LOST",
            "name": f"GPU error: {DXGI_NAMES.get(ex_code, 'DXGI error')}",
            "player_message": (
                "The GPU stopped responding to the game. This is almost always a driver, "
                "hardware, or overheating issue - not a game bug."
            ),
            "fix": [
                "Update GPU drivers",
                "Check GPU temperature - use HWiNFO64 or GPU-Z while gaming",
                "Revert any GPU overclock",
                "If the problem persists, run a GPU stress test (FurMark) to check hardware stability",
            ],
            "dev_note": f"DXGI error {ex_code:#x} - TDR or device lost",
            "confidence": "HIGH",
        })

    if ex_code == 0xC00000FD:
        return _builtin("STACK_OVERFLOW", {
            "id":   "STACK_OVERFLOW",
            "name": "Stack overflow",
            "player_message": (
                "The game ran out of call stack space. This is a game bug, not a hardware issue. "
                "It typically means a function called itself too many times in a loop."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note exactly what you were doing in-game when it crashed",
                "Check if it happens consistently in the same situation",
            ],
            "dev_note": "Stack overflow - look for infinite recursion in the crashing thread",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000374:
        return _builtin("HEAP_CORRUPTION", {
            "id":   "HEAP_CORRUPTION",
            "name": "Memory corruption detected",
            "player_message": (
                "The game detected that its memory was corrupted. "
                "This is a game bug. It can be hard to reproduce consistently "
                "because the corruption may happen before the crash."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed - especially any unusual sequences of actions",
                "If you have mods, try without them first",
            ],
            "dev_note": "Heap corruption - use heap debug allocator to find the stomper",
            "confidence": "HIGH",
        })

    _PROXY_NAMES_SET = {"dxgi.dll","d3d12.dll","d3d11.dll","d3d10.dll","d3d9.dll",
                        "opengl32.dll","dinput8.dll","winmm.dll","version.dll","dsound.dll"}
    _SYS_PATH_FRAGS  = ("\\windows\\", "\\system32\\", "\\syswow64\\", "\\winsxs\\")

    def _mod_basename(path):
        return path.replace("\\", "/").split("/")[-1].lower()

    def _is_proxy(mod_dict):
        n  = _mod_basename(mod_dict["name"])
        fl = mod_dict["name"].lower().replace("/", "\\")
        return n in _PROXY_NAMES_SET and not any(f in fl for f in _SYS_PATH_FRAGS)

    _crash_in_proxy_mod = None
    for m in modules:
        try:
            b = int(m["base"], 16)
            if b <= ex_addr < b + m["size"] and _is_proxy(m):
                _crash_in_proxy_mod = m
                break
        except Exception:
            pass

    if _crash_in_proxy_mod:
        _pname = _mod_basename(_crash_in_proxy_mod["name"])
        return _builtin("RESHADE_DIRECT_CRASH", {
            "id":   "RESHADE_DIRECT_CRASH",
            "name": f"Crash inside proxy DLL: {_pname} (ReShade / D3D hook)",
            "player_message": (
                f"The crash happened inside {_pname} which is in your game folder "
                f"instead of Windows\\System32. This is a ReShade, ENB, or other D3D hook. "
                f"The hook itself crashed - this is not a game bug."
            ),
            "fix": [
                f"Remove {_pname} from the game folder and test without it",
                "If using ReShade: update to the latest version for this game",
                "Try disabling ReShade shaders one by one to find the culprit",
                "Verify game files through Steam after removing the proxy DLL",
            ],
            "dev_note": (
                f"Crash addr inside {_pname} loaded from game folder (proxy/hook DLL). "
                f"Not engine code - report to ReShade/ENB developers."
            ),
            "confidence": "HIGH",
        })

    _D3D_RUNTIME_NAMES = {"d3d12.dll","d3d11.dll","dxgi.dll","d3d12core.dll","dxcore.dll"}
    _proxy_indicators   = [i for i in mods.get("indicators", []) if i.get("type") == "proxy_dll"]
    if _proxy_indicators:
        _crash_in_real_d3d = False
        for m in modules:
            try:
                b = int(m["base"], 16)
                if b <= ex_addr < b + m["size"]:
                    n  = _mod_basename(m["name"])
                    fl = m["name"].lower().replace("/", "\\")
                    if n in _D3D_RUNTIME_NAMES and any(f in fl for f in _SYS_PATH_FRAGS):
                        _crash_in_real_d3d = True
                    break
            except Exception:
                pass
        if _crash_in_real_d3d:
            _proxy_str = ", ".join(
                _mod_basename(i["path"]) for i in _proxy_indicators[:3]
            )
            return _builtin("RESHADE_D3D_CORRUPTION", {
                "id":   "RESHADE_D3D_CORRUPTION",
                "name": f"D3D runtime crash with proxy DLL present ({_proxy_str})",
                "player_message": (
                    f"The crash happened inside the DirectX runtime while {_proxy_str} "
                    f"was loaded from your game folder. "
                    f"A D3D hook (likely ReShade) probably corrupted the graphics state, "
                    f"causing the D3D runtime itself to crash."
                ),
                "fix": [
                    f"Remove {_proxy_str} from the game folder and test without it",
                    "If the crash disappears without the proxy DLL, it is the cause",
                    "Update ReShade to the latest version if you need it",
                    "Verify game files through Steam after removing proxy DLLs",
                ],
                "dev_note": (
                    f"Crash in System32 D3D with proxy DLL ({_proxy_str}) present. "
                    f"Proxy likely corrupted D3D state. Not a vanilla crash."
                ),
                "confidence": "MED",
            })

    proxy_dlls = [i for i in mods.get("indicators", []) if i.get("type") == "proxy_dll"]
    reshade_mods = [i for i in mods.get("indicators", [])
                    if i.get("type") in ("mod_manager", "unknown_dll")
                    and any(k in i.get("detail","").lower()
                            for k in ("reshade","minhook","enb","dinput"))]
    all_proxy_hits = proxy_dlls + reshade_mods
    if all_proxy_hits:
        proxy_names = ", ".join(
            i["path"].replace("\\","/").split("/")[-1] for i in all_proxy_hits[:3]
        )
        return _builtin("PROXY_DLL_CRASH", {
            "id":   "PROXY_DLL_CRASH",
            "name": f"Crash with D3D/input proxy DLL detected ({proxy_names})",
            "player_message": (
                f"A proxy DLL was found in your game folder: {proxy_names}. "
                "This is almost certainly ReShade, ENB, or another post-processing/mod tool "
                "that replaces a system DLL to hook into the game's rendering or input. "
                "Proxy DLLs intercept D3D calls and can cause crashes, especially after "
                "game or driver updates."
            ),
            "fix": [
                f"Remove {proxy_names} from the game's folder and test without it",
                "If using ReShade: check for a ReShade update compatible with this game version",
                "If you need ReShade, try reinstalling it after verifying game files",
                "Verify game files through Steam after removing any proxy DLLs",
            ],
            "dev_note": (
                f"Proxy DLL(s) in game folder: {proxy_names}. "
                "These replace system DLLs and hook D3D/input - high confidence this "
                "contributed to the crash. Not a vanilla crash."
            ),
            "confidence": "HIGH",
        })

    if mods.get("has_mods") and mods.get("confidence") == "HIGH":
        return _builtin("MOD_CRASH", {
            "id":   "MOD_CRASH",
            "name": "Crash with mods detected",
            "player_message": (
                "Mods were detected in this crash. Mods can cause crashes that "
                "wouldn't otherwise occur. Before reporting this as a game bug, "
                "please verify the crash happens without mods installed."
            ),
            "fix": [
                "Remove all mods and verify the crash still happens",
                "If the crash goes away without mods, the mod is the cause",
                "If it still crashes without mods, please share the new dump with the 418th",
            ],
            "dev_note": "Mods detected with HIGH confidence - verify crash is reproducible in vanilla",
            "confidence": "MED",
        })

    if ex_code == 0xE06D7363:
        return _builtin("CPP_EXCEPTION", {
            "id":   "CPP_EXCEPTION",
            "name": "Unhandled game error",
            "player_message": (
                "The game encountered an internal error it didn't know how to handle. "
                "This is a game bug. Check the engine log for the error message."
            ),
            "fix": [
                "To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs for the error message",
                "Share both the .log and .dmp with the 418th",
                "Note what you were doing when it crashed",
            ],
            "dev_note": "Unhandled C++ exception - check exception type and message in log",
            "confidence": "HIGH",
        })

    if ex_code == 0xC000001D:
        return _builtin("ILLEGAL_INSTR", {
            "id":   "ILLEGAL_INSTR",
            "name": "Illegal CPU instruction",
            "player_message": (
                "The game tried to execute an instruction your CPU doesn't support, "
                "or the game code itself was corrupted. "
                "This can also happen if the game requires a CPU feature you don't have."
            ),
            "fix": [
                "Verify game files through Steam",
                "Check if your CPU meets the minimum requirements",
                "Update Windows and your BIOS/UEFI firmware",
                "If using an emulator or VM, switch to native hardware",
            ],
            "dev_note": "ILLEGAL_INSTRUCTION (0xC000001D) - often __debugbreak/assert or AVX mismatch",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000135:
        return _builtin("DLL_NOT_FOUND", {
            "id":   "DLL_NOT_FOUND",
            "name": "Required DLL not found",
            "player_message": (
                "The game could not find a required system or middleware DLL. "
                "This is usually a missing Visual C++ or DirectX runtime."
            ),
            "fix": [
                "Install the latest Visual C++ Redistributable (both x64 and x86) from Microsoft",
                "Install DirectX End-User Runtime from Microsoft",
                "Verify game files through Steam",
                "Check Windows Event Viewer for the exact DLL name that failed to load",
            ],
            "dev_note": "STATUS_DLL_NOT_FOUND - check Event Viewer for the missing DLL name",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000142:
        return _builtin("DLL_INIT_FAILED", {
            "id":   "DLL_INIT_FAILED",
            "name": "DLL failed to initialise",
            "player_message": (
                "A required library failed to start up. "
                "This is often caused by a corrupted install or a missing dependency."
            ),
            "fix": [
                "Verify game files through Steam",
                "Reinstall Visual C++ Redistributables",
                "Try a clean boot (disable startup programs) to rule out conflicts",
                "Temporarily disable antivirus and try again",
            ],
            "dev_note": "STATUS_DLL_INIT_FAILED - DllMain returned FALSE; check dep chain",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000006:
        return _builtin("IN_PAGE_ERROR", {
            "id":   "IN_PAGE_ERROR",
            "name": "Disk read failure (corrupt install or failing drive)",
            "player_message": (
                "Windows could not read a game file from disk when it was needed. "
                "This usually means corrupted game files or a failing storage device."
            ),
            "fix": [
                "Verify game files through Steam",
                "Run chkdsk on your drive (chkdsk C: /f in admin cmd)",
                "Check your drive health with CrystalDiskInfo",
                "If on an HDD, consider moving the game to an SSD",
            ],
            "dev_note": "STATUS_IN_PAGE_ERROR - page fault on a memory-mapped file; likely disk I/O error",
            "confidence": "HIGH",
        })

    _purecall_mods = {"vcruntime140.dll", "ucrtbase.dll", "msvcrt.dll"}
    if crash_mod and crash_mod.lower() in _purecall_mods and ex_code == 0xC0000005:
        return _builtin("PURE_VIRTUAL_CALL", {
            "id":   "PURE_VIRTUAL_CALL",
            "name": "Pure virtual function call (C++ object destroyed too early)",
            "player_message": (
                "The game tried to call a function on an object that was already destroyed. "
                "This is a game bug - a C++ object was used after its lifetime ended."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed (especially rapid state changes)",
                "Check if it happens consistently",
            ],
            "dev_note": "Crash in vcruntime/_purecall with AV - pure virtual call on destroyed object",
            "confidence": "HIGH",
        })


    if (ex_code == 0xC0000005 and len(params) >= 2
            and params[0] == "0x0"
            and fault_addr == 0
            and not is_suicide):
        return _builtin("NULL_DEREF_READ", {
            "id":   "NULL_DEREF_READ",
            "name": "Null pointer read - object was null or already destroyed",
            "player_message": (
                "The game tried to read from a null pointer. "
                "This means an object that was expected to exist was null - "
                "it was never created, already destroyed, or a function returned null "
                "and the caller didn't check before using it."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file with the 418th",
                "Note exactly what you were doing when it crashed",
                "Check if it happens consistently or randomly",
            ],
            "dev_note": (
                "AV read from 0x0 - the base pointer itself was null (not a field offset). "
                "Instruction is typically MOV reg, [RCX] or similar. "
                "Check the active game thread for what passed the null pointer."
            ),
            "confidence": "HIGH",
        })

    if (ex_code == 0xC0000005 and len(params) >= 2
            and params[0] == "0x0"
            and 0 < fault_addr < 0x1000
            and not is_suicide):
        return _builtin("NEAR_NULL_READ", {
            "id":   "NEAR_NULL_READ",
            "name": f"Null pointer read at struct offset +{fault_addr} (0x{fault_addr:X})",
            "player_message": (
                f"The game tried to read a field at byte offset +{fault_addr} from a null pointer. "
                f"This means an object pointer was null - the object was never created, was already "
                f"destroyed, or a function returned null and the caller didn't check before accessing "
                f"field +{fault_addr}."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file",
                "Note exactly what you were doing when it crashed",
                "Check if it happens consistently or randomly",
            ],
            "dev_note": (
                f"AV read from 0x{fault_addr:X} - struct member access on a null pointer. "
                f"Instruction is typically MOV reg, [RCX+0x{fault_addr:X}] or MOV reg, [RAX+0x{fault_addr:X}]. "
                f"The base register was 0 at crash time. Check the active game thread for what passed the null pointer."
            ),
            "confidence": "HIGH",
        })

    if (ex_code == 0xC0000005 and len(params) >= 2
            and params[0] == "0x1"
            and fault_addr < 0x10000
            and not is_suicide):
        return _builtin("NULL_DEREF_WRITE", {
            "id":   "NULL_DEREF_WRITE",
            "name": "Null pointer write - destroyed or uninitialised object",
            "player_message": (
                "The game tried to write to memory through a null or invalid pointer. "
                "This is a game bug - an object was used after being destroyed, "
                "or was never properly initialised."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file",
                "Note exactly what you were doing when it crashed",
            ],
            "dev_note": "AV write to near-null address - use-after-free or uninit pointer write",
            "confidence": "HIGH",
        })

    _has_nvidia = any("nvwgf" in m or "nvgpucomp" in m or "nvd3d" in m
                      for m in all_mods.split())
    _has_intel_igpu = any("igd10um" in m or "igc64" in m or "igdgmm" in m
                          for m in all_mods.split())
    if (_has_nvidia and _has_intel_igpu
            and ex_code == 0xC0000005
            and not is_suicide
            and crash_mod
            and any(frag in crash_mod_l for frag in GPU_DRIVER_FRAGMENTS)):
        return _builtin("DUAL_GPU_DRIVER_CRASH", {
            "id":   "DUAL_GPU_DRIVER_CRASH",
            "name": "GPU driver crash on dual-GPU system (NVIDIA + Intel iGPU)",
            "player_message": (
                "Your system has both an NVIDIA dedicated GPU and an Intel integrated GPU. "
                "The game crashed inside a GPU driver. On dual-GPU systems this is often "
                "caused by the game running on the wrong GPU, or a conflict between the two drivers."
            ),
            "fix": [
                "Open NVIDIA Control Panel → Manage 3D Settings → Program Settings "
                "→ add Helldivers 2 → set preferred GPU to your NVIDIA card",
                "Update both your NVIDIA and Intel GPU drivers",
                "In Windows Display Settings, set the NVIDIA card as the primary GPU",
                "If on a laptop, disable the Intel iGPU in Device Manager and test",
                "Update your NVIDIA drivers - use DDU for a clean install if issues persist",
            ],
            "dev_note": (
                "Crash in GPU driver DLL on dual-GPU system (NVIDIA + Intel iGPU both loaded). "
                "Check which adapter D3D12 is selecting at runtime - possible iGPU fallback."
            ),
            "confidence": "HIGH",
        })


    if ex_code == 0xC0000094:
        return _builtin("INT_DIVIDE_BY_ZERO", {
            "id":   "INT_DIVIDE_BY_ZERO",
            "name": "Integer division by zero",
            "player_message": (
                "The game crashed because it tried to divide a number by zero. "
                "This is a game bug - a calculation didn't check for zero before dividing."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file",
                "Note exactly what you were doing when it crashed",
                "Check if it happens consistently or randomly",
            ],
            "dev_note": "STATUS_INTEGER_DIVIDE_BY_ZERO - check for unguarded division, often in damage/ratio calculations",
            "confidence": "HIGH",
        })

    if ex_code == 0xC000008E:
        return _builtin("FLOAT_DIVIDE_BY_ZERO", {
            "id":   "FLOAT_DIVIDE_BY_ZERO",
            "name": "Floating-point division by zero",
            "player_message": (
                "The game crashed due to a floating-point division by zero. "
                "This is a game bug - usually a normalization or ratio calculation "
                "with a zero-length vector or zero denominator."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file",
                "Note what was happening (combat? movement? physics interaction?)",
            ],
            "dev_note": "STATUS_FLOAT_DIVIDE_BY_ZERO - often vec3.normalize() on a zero vector, or distance/ratio calc",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000090:
        return _builtin("FLOAT_INVALID", {
            "id":   "FLOAT_INVALID",
            "name": "Invalid floating-point operation",
            "player_message": (
                "The game crashed due to an invalid floating-point operation. "
                "This usually means a NaN (Not a Number) value was produced and "
                "propagated through the engine. This is a game bug."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Share both the .dmp and the .log file",
                "Note what was happening (physics? animation? rendering?)",
            ],
            "dev_note": "STATUS_FLOAT_INVALID_OPERATION - check for NaN in transforms, sqrt of negative, or acos/asin out of range",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000095:
        return _builtin("INT_OVERFLOW", {
            "id":   "INT_OVERFLOW",
            "name": "Integer overflow",
            "player_message": (
                "The game crashed due to an integer overflow. This is a game bug - "
                "a calculation produced a number too large for its data type."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing (large resource count? long play session?)",
            ],
            "dev_note": "STATUS_INTEGER_OVERFLOW - check for unguarded arithmetic, often in inventory/score/counters",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000096:
        return _builtin("PRIVILEGED_INSTR", {
            "id":   "PRIVILEGED_INSTR",
            "name": "Privileged CPU instruction executed",
            "player_message": (
                "The game tried to execute a CPU instruction that requires kernel privileges. "
                "This usually means game code was corrupted in memory, or a JIT/codegen bug "
                "produced invalid code."
            ),
            "fix": [
                "Verify game files through Steam - game code may be corrupted",
                "Run a memory diagnostic (Windows Memory Diagnostic or MemTest86)",
                "Check for malware that might be injecting code",
                "Update your BIOS/UEFI firmware",
            ],
            "dev_note": "STATUS_PRIVILEGED_INSTRUCTION - corrupted code pointer, JIT bug, or memory stomp overwriting code",
            "confidence": "HIGH",
        })

    if ex_code == 0xC000008C:
        return _builtin("ARRAY_BOUNDS", {
            "id":   "ARRAY_BOUNDS",
            "name": "Array bounds exceeded",
            "player_message": (
                "The game accessed an array element outside its valid range. "
                "This is a game bug - an index wasn't checked before use."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing (inventory access? loading screen? multiplayer?)",
            ],
            "dev_note": "STATUS_ARRAY_BOUNDS_EXCEEDED - unguarded array index, often in container/array access",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000008:
        return _builtin("INVALID_HANDLE", {
            "id":   "INVALID_HANDLE",
            "name": "Invalid handle (use-after-close)",
            "player_message": (
                "The game tried to use a system handle (file, event, mutex) that had "
                "already been closed. This is a game bug - a handle was used after "
                "its lifetime ended."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing (loading? saving? multiplayer?)",
            ],
            "dev_note": "STATUS_INVALID_HANDLE - use-after-close on a kernel handle, check handle lifecycle management",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000353:
        return _builtin("INVALID_CRT_PARAM", {
            "id":   "INVALID_CRT_PARAM",
            "name": "C runtime invalid parameter",
            "player_message": (
                "The C runtime detected an invalid parameter passed to a standard "
                "library function. This is a game bug - a function was called with "
                "an argument it doesn't accept."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed",
            ],
            "dev_note": "STATUS_INVALID_CRUNTIME_PARAMETER - _invalid_parameter fired, check string/format/buffer args",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000022:
        return _builtin("ACCESS_DENIED", {
            "id":   "ACCESS_DENIED",
            "name": "Access denied (permissions error)",
            "player_message": (
                "The game was denied access to a file or registry key. "
                "This is often caused by antivirus software, Windows UAC, or "
                "incorrect file permissions."
            ),
            "fix": [
                "Add the game folder to your antivirus exclusions",
                "Run the game as administrator",
                "Check that your user account has read/write access to the game folder",
                "If the game is in Program Files, try moving it to a different location",
            ],
            "dev_note": "STATUS_ACCESS_DENIED - file/registry permission failure, often AV or UAC blocking access",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000017:
        return _builtin("OUT_OF_MEMORY", {
            "id":   "OUT_OF_MEMORY",
            "name": "Out of memory",
            "player_message": (
                "The game ran out of memory. This can happen if the game has a memory leak, "
                "if you're running too many applications, or if your page file is too small."
            ),
            "fix": [
                "Close other applications before launching the game",
                "Increase your Windows page file size",
                "Lower in-game graphics settings (especially texture quality)",
                "If you have less than 16GB RAM, consider upgrading",
                "Check for memory leaks in the game log",
            ],
            "dev_note": "STATUS_NO_MEMORY - virtual address space exhaustion or pagefile full, check for leak",
            "confidence": "HIGH",
        })

    if ex_code == 0xC000001A:
        return _builtin("NOT_MAPPED", {
            "id":   "NOT_MAPPED",
            "name": "Access to unmapped memory",
            "player_message": (
                "The game tried to access a memory region that was never mapped. "
                "This is a game bug - a pointer pointed to memory that was never allocated."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed",
            ],
            "dev_note": "STATUS_NOT_MAPPED_VIEW - pointer to never-allocated memory, often a garbage/uninitialized pointer",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000420:
        return _builtin("ASSERTION_FAILURE", {
            "id":   "ASSERTION_FAILURE",
            "name": "Assertion failure in release build",
            "player_message": (
                "An assertion check in the game's release build failed. "
                "This is a game bug - the developers shipped an assert that caught "
                "an unexpected condition."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed",
                "Check if it happens consistently or randomly",
            ],
            "dev_note": "STATUS_ASSERTION_FAILURE - assert() fired in release build, check the assert message in log",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000409:
        return _builtin("STACK_BUFFER_OVERRUN", {
            "id":   "STACK_BUFFER_OVERRUN",
            "name": "Stack buffer overrun detected",
            "player_message": (
                "The game's compiler security check (/GS) detected a stack buffer overrun. "
                "This is a game bug - code wrote past the end of a local array or buffer, "
                "corrupting the stack."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing (string formatting? file parsing? network packet?)",
            ],
            "dev_note": "STATUS_STACK_BUFFER_OVERRUN - /GS cookie check failed, look for unguarded strcpy/sprintf/memcpy",
            "confidence": "HIGH",
        })

    if ex_code == 0x80000001:
        return _builtin("GUARD_PAGE", {
            "id":   "GUARD_PAGE",
            "name": "Guard page violation (near stack overflow)",
            "player_message": (
                "The game hit a guard page, which is an early warning sign of a stack overflow. "
                "The stack came very close to overflowing but was caught before it did."
            ),
            "fix": [
                "This is likely a game bug - the call stack is very deep",
                "Check the game log for error messages",
                "Note what you were doing (deep menu navigation? recursive script?)",
            ],
            "dev_note": "STATUS_GUARD_PAGE_VIOLATION - stack near overflow, check for deep/dead recursion",
            "confidence": "MED",
        })

    if ex_code == 0x80000002:
        return _builtin("MISALIGNMENT", {
            "id":   "MISALIGNMENT",
            "name": "Unaligned memory access",
            "player_message": (
                "The game tried to access memory at an address that wasn't properly aligned "
                "for the data type. This is a game bug - usually caused by a corrupted pointer "
                "or a struct packing error."
            ),
            "fix": [
                "This is a game bug - please report it with the dump file",
                "Note what you were doing when it crashed",
            ],
            "dev_note": "STATUS_DATATYPE_MISALIGNMENT - unaligned SSE/AVX access, often from corrupted pointer or bad cast",
            "confidence": "HIGH",
        })

    if ex_code == 0xC0000139:
        return _builtin("ENTRY_POINT_NOT_FOUND", {
            "id":   "ENTRY_POINT_NOT_FOUND",
            "name": "DLL entry point not found (version mismatch)",
            "player_message": (
                "The game found a DLL but it didn't contain a function the game expected. "
                "This is usually a version mismatch - the DLL is the wrong version."
            ),
            "fix": [
                "Reinstall the Visual C++ Redistributables (both x64 and x86)",
                "Verify game files through Steam",
                "Check for conflicting DLLs in the game folder",
                "If modded, remove mods that ship their own DLLs",
            ],
            "dev_note": "STATUS_ENTRYPOINT_NOT_FOUND - DLL version mismatch, check for partial/old redist install",
            "confidence": "HIGH",
        })


    if crash_mod and crash_mod.lower() == "ntdll.dll" and ex_code in (0xC0000005, 0xC0000374):
        return _builtin("NTDLL_HEAP_FAULT", {
            "id":   "NTDLL_HEAP_FAULT",
            "name": "Crash in ntdll.dll (heap corruption propagated)",
            "player_message": (
                "The crash happened inside ntdll.dll, which is the Windows memory manager. "
                "This usually means heap corruption occurred earlier in the frame and "
                "propagated here. The real cause is in game code, not ntdll."
            ),
            "fix": [
                "This is a game bug - the corruption happened earlier, check the call chain",
                "Share the .dmp and .log with the dev team",
                "Note what you were doing before the crash",
            ],
            "dev_note": "Crash in ntdll heap routines - corruption originated elsewhere, walk the call chain",
            "confidence": "MED",
        })

    if crash_mod and crash_mod.lower() == "kernel32.dll" and ex_code == 0xC0000005:
        return _builtin("KERNEL32_FAULT", {
            "id":   "KERNEL32_FAULT",
            "name": "Crash in kernel32.dll",
            "player_message": (
                "The crash happened inside kernel32.dll. This is unusual and usually means "
                "a corrupted callback pointer, a thread synchronization issue, or heap corruption "
                "that propagated into a kernel32 call."
            ),
            "fix": [
                "This is likely a game bug - check the call chain for the real trigger",
                "Share the .dmp and .log with the dev team",
            ],
            "dev_note": "Crash in kernel32 - corrupted callback, thread sync issue, or propagated heap corruption",
            "confidence": "MED",
        })

    ANTICHEAT_DLLS = {"easyanticheat.dll", "easyanticheat_launcher.dll",
                      "battleye.dll", "bedaisy.sys", "npggnt64.des", "npsc64.des"}
    if crash_mod and crash_mod.lower() in ANTICHEAT_DLLS:
        return _builtin("ANTICHEAT_CRASH", {
            "id":   "ANTICHEAT_CRASH",
            "name": f"Crash inside anti-cheat ({crash_mod})",
            "player_message": (
                f"The crash happened inside {crash_mod}, which is anti-cheat software. "
                f"This is not the game's own code - the anti-cheat itself crashed or "
                f"force-closed the game. This may be an anti-cheat bug or a conflict."
            ),
            "fix": [
                "Update the anti-cheat to the latest version",
                "Verify game files through Steam (this reinstalls the anti-cheat)",
                "Check for conflicting software (overlays, other anti-cheats)",
                "If the issue persists, report to the anti-cheat vendor",
            ],
            "dev_note": f"Crash inside {crash_mod} - anti-cheat fault, not game code",
            "confidence": "HIGH",
        })

    if crash_mod and "bink2w" in crash_mod.lower():
        return _builtin("BINK_VIDEO_CRASH", {
            "id":   "BINK_VIDEO_CRASH",
            "name": "Crash in Bink Video player",
            "player_message": (
                "The crash happened inside the Bink Video player (bink2w64.dll). "
                "This usually means a corrupted video file or a codec issue."
            ),
            "fix": [
                "Verify game files through Steam - a video file may be corrupted",
                "Update your GPU drivers (Bink uses GPU-accelerated decoding)",
                "Try skipping cinematics if possible",
            ],
            "dev_note": "Crash in Bink2 - corrupted video file or codec mismatch",
            "confidence": "HIGH",
        })

    if crash_mod and "steam_api" in crash_mod.lower():
        return _builtin("STEAM_API_CRASH", {
            "id":   "STEAM_API_CRASH",
            "name": "Crash in Steam API",
            "player_message": (
                "The crash happened inside the Steam API. This can be caused by "
                "Steam overlay issues, network problems, or a Steam client bug."
            ),
            "fix": [
                "Restart Steam completely",
                "Disable the Steam overlay and test",
                "Verify game files through Steam",
                "Check your internet connection",
            ],
            "dev_note": "Crash in steam_api64.dll - overlay, network, or Steam client issue",
            "confidence": "MED",
        })

    if crash_mod and "npgg" in crash_mod.lower():
        return _builtin("GAMEGUARD_CRASH", {
            "id":   "GAMEGUARD_CRASH",
            "name": "Crash in GameGuard anti-cheat",
            "player_message": (
                "The crash happened inside GameGuard (npggnt64.des), which is an "
                "anti-cheat system. GameGuard may have detected a conflict or "
                "encountered an internal error."
            ),
            "fix": [
                "Restart the game (GameGuard reinstalls on next launch)",
                "Verify game files through Steam",
                "Close any software GameGuard might flag (debuggers, injectors, overlays)",
                "Check for GameGuard updates",
            ],
            "dev_note": "Crash in GameGuard - anti-cheat conflict or internal error",
            "confidence": "HIGH",
        })

    if crash_mod and ("wwise" in crash_mod.lower() or crash_mod.lower().startswith("ak")):
        return _builtin("WWISE_CRASH", {
            "id":   "WWISE_CRASH",
            "name": "Crash in Wwise audio engine",
            "player_message": (
                "The crash happened inside the Wwise audio engine. This can be caused "
                "by a missing or corrupted sound bank, an invalid audio event, or "
                "an audio driver issue."
            ),
            "fix": [
                "Update your audio drivers",
                "Verify game files through Steam - a sound bank may be corrupted",
                "Try setting audio output to stereo instead of surround",
                "Disable audio enhancements in Windows sound settings",
            ],
            "dev_note": "Crash in Wwise (AkSoundEngine) - invalid event, missing bank, or driver issue",
            "confidence": "HIGH",
        })

    if crash_mod and "fmod" in crash_mod.lower():
        return _builtin("FMOD_CRASH", {
            "id":   "FMOD_CRASH",
            "name": "Crash in FMOD audio engine",
            "player_message": (
                "The crash happened inside the FMOD audio engine. This can be caused "
                "by an audio driver conflict, corrupted sound file, or invalid FMOD event."
            ),
            "fix": [
                "Update your audio drivers",
                "Verify game files through Steam",
                "Try a different audio output device",
                "Disable audio enhancements in Windows sound settings",
            ],
            "dev_note": "Crash in FMOD - driver conflict, corrupted file, or invalid event",
            "confidence": "HIGH",
        })

    if crash_mod and "physx" in crash_mod.lower():
        return _builtin("PHYSX_CRASH", {
            "id":   "PHYSX_CRASH",
            "name": "Crash in PhysX physics engine",
            "player_message": (
                "The crash happened inside the PhysX physics engine. This can be caused "
                "by a NaN transform (invalid position/rotation), a degenerate collision mesh, "
                "or physics simulation on a destroyed actor."
            ),
            "fix": [
                "Update your GPU drivers (PhysX is bundled with NVIDIA drivers)",
                "Verify game files through Steam",
                "Note what was happening (explosion? ragdoll? physics object?)",
                "Try lowering physics simulation quality if available",
            ],
            "dev_note": "Crash in PhysX - NaN transform, degenerate geometry, or destroyed actor",
            "confidence": "HIGH",
        })

    if crash_mod and "lua" in crash_mod.lower():
        return _builtin("LUA_CRASH", {
            "id":   "LUA_CRASH",
            "name": "Crash in Lua scripting runtime",
            "player_message": (
                "The crash happened inside the Lua scripting runtime. This can be caused "
                "by a script bug, a corrupted script file, or a script accessing a "
                "nil/destroyed object."
            ),
            "fix": [
                "If modded, remove script mods and test",
                "Verify game files through Steam",
                "Check the game log for Lua error messages",
                "Note what you were doing (mission? UI? specific game feature?)",
            ],
            "dev_note": "Crash in Lua runtime - script bug, corrupted script, or nil object access",
            "confidence": "HIGH",
        })

    if crash_mod and "dstorage" in crash_mod.lower():
        return _builtin("DSTORAGE_CRASH", {
            "id":   "DSTORAGE_CRASH",
            "name": "Crash in DirectStorage runtime",
            "player_message": (
                "The crash happened inside the DirectStorage runtime itself. "
                "This is usually caused by outdated GPU drivers that don't properly "
                "support DirectStorage, or by corrupted game data being streamed."
            ),
            "fix": [
                "Update your GPU drivers to the latest version",
                "Verify game files through Steam",
                "If the game has a DirectStorage toggle, try disabling it",
                "Check if your GPU supports DirectStorage (RTX 30+ / RX 6600+ recommended)",
            ],
            "dev_note": "Crash in dstorage.dll/dstoragecore.dll - driver support issue or corrupted streaming data",
            "confidence": "HIGH",
        })

    if (ex_code == 0xC0000005 and len(params) >= 2
            and 0x1000 < fault_addr < 0x00007F0000000000
            and not is_suicide
            and decoded_instr and not decoded_instr.get("is_suicide")):
        ex_regs = ex.get("regs", {}) if ex else {}
        regs_at_fault = {k: v for k, v in ex_regs.items()
                        if k != "_xmm" and isinstance(v, int) and (v == fault_addr or (v != 0 and abs(v - fault_addr) < 0x100))}
        if regs_at_fault:
            reg_list = ", ".join(f"{k.upper()}=0x{v:016X}" for k, v in regs_at_fault.items())
            return _builtin("POSSIBLE_USE_AFTER_FREE", {
                "id":   "POSSIBLE_USE_AFTER_FREE",
                "name": f"Possible use-after-free (fault at 0x{fault_addr:016X})",
                "player_message": (
                    f"The game accessed memory at address 0x{fault_addr:016X}, which is a valid-looking "
                    f"heap address but is not currently mapped. This suggests the memory was freed "
                    f"and the pointer is stale - a use-after-free bug. Register(s) {reg_list} "
                    f"held the stale pointer."
                ),
                "fix": [
                    "This is a game bug - please report it with the dump file",
                    "Share both the .dmp and the .log file",
                    "Note what you were doing (object destruction? level transition? combat?)",
                    "Check if it happens consistently or randomly",
                ],
                "dev_note": (
                    f"AV at heap-like address 0x{fault_addr:016X} with register(s) {reg_list} "
                    f"holding the address - likely use-after-free. Check object lifecycle management."
                ),
                "confidence": "MED",
            })

    CRASH_HANDLER_MODS = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                          "sentry.dll", "backtrace.dll"}
    if crash_mod and crash_mod.lower() in CRASH_HANDLER_MODS:
        return _builtin("CRASH_HANDLER_FAULT", {
            "id":   "CRASH_HANDLER_FAULT",
            "name": f"Crash inside crash reporter ({crash_mod})",
            "player_message": (
                f"The crash happened inside {crash_mod}, which is the game's crash reporter. "
                f"This means a crash occurred, and while the crash reporter was trying to "
                f"write the crash dump, it crashed itself. The original crash's data may be "
                f"partially captured."
            ),
            "fix": [
                "The original crash data may be incomplete - share the .dmp and .log",
                "This is likely a game bug, but the crash reporter fault makes it harder to diagnose",
                "Try reproducing the crash to get a cleaner dump",
            ],
            "dev_note": f"Crash inside {crash_mod} - secondary fault in crash handler, original cause may be obscured",
            "confidence": "LOW",
        })

    return None

def build_plain_english(parsed: dict, rootcause: list, mods: dict, pattern: "dict | None",
                        patterns: "list | None" = None) -> dict:

    ex       = parsed.get("exception", {})
    modules  = parsed.get("modules", [])
    threads  = parsed.get("threads", [])

    CRASH_HANDLERS = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                      "sentry.dll", "backtrace.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    def mod_for_addr(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return PureWindowsPath(m["name"]).name, addr - base
            except Exception:
                pass
        return None, 0

    ex_code = int(ex.get("code", "0"), 16) if ex else 0
    params  = ex.get("params", []) if ex else []

    if ex_code == 0xC0000005:
        op = "write" if params and params[0] == "0x1" else "read"
        fa = int(params[1], 16) if len(params) >= 2 else 0

        decoded = None
        try:
            crash_addr = int(ex.get("address", "0"), 16)
            imem = read_virtual_memory(parsed, crash_addr, 10)
            if imem:
                decoded = decode_crash_instruction(imem, crash_addr)
        except Exception:
            pass

        if decoded and decoded["is_suicide"]:
            headline = (f"The engine intentionally killed itself ({decoded['instruction']}) - "
                        f"the real error is elsewhere. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs")
        elif _is_stingray_suicide(parsed)[0]:
            instr_str = decoded["instruction"] if decoded else "a null pointer access"
            headline = (f"The Stingray engine intentionally terminated itself ({instr_str}). "
                        f"This is NOT a game bug - the engine detected an internal error and committed "
                        f"suicide. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs")
        elif fa == 0:
            headline = "The game engine crashed after trying to access memory at address zero"
        elif fa < 0x100:
            headline = f"The game engine crashed after trying to access an object that no longer exists (offset +{fa})"
        else:
            headline = "The game engine crashed after accessing invalid memory"
    elif ex_code == 0xC00000FD:
        headline = "The game crashed due to a stack overflow - likely infinite recursion"
    elif ex_code == 0xC0000374:
        headline = "The game crashed due to heap corruption - memory was overwritten"
    elif ex_code == 0xE06D7363:
        headline = "The game crashed due to an unhandled internal error (C++ exception)"
    elif ex_code == 0xC0000142:
        headline = "The game failed to launch - a required DLL failed to initialise before the game even started running."
    elif ex_code in (0x80000003, 0x80000004):
        anticheat_names = ("easyanticheat", "beclient", "beservice", "battleye")
        found_anticheat = any(any(n in m["name"].lower() for n in anticheat_names)
                              for m in modules)
        trap_kind = "a breakpoint" if ex_code == 0x80000003 else "a single-step trace"
        if found_anticheat:
            headline = (f"This isn't a real crash - {trap_kind} was hit, and an anti-cheat system is present. "
                        f"The anti-cheat likely detected debugging/tracing and force-closed the game.")
        else:
            headline = (f"This isn't a real crash - {trap_kind} was hit, which only happens when a debugger "
                        f"is attached and stepping through the game's code.")
    elif ex_code in EXCEPTION_HEADLINES:
        headline = EXCEPTION_HEADLINES[ex_code]
    elif ex_code:
        headline = f"The game crashed with error code {ex.get('code', '?')}"
    else:
        headline = "The game crashed - exception details not found in dump"

    if patterns:
        headline = patterns[0].get("name", headline)
    elif pattern:
        headline = pattern.get("name", headline)
    elif mods and mods.get("has_mods") and mods.get("confidence") == "HIGH":
        high_indicators = [i for i in mods.get("indicators", []) if i.get("severity") == "HIGH"]
        if high_indicators:
            kind = high_indicators[0].get("type", "mod")
            kind_label = {
                "proxy_dll":   "a proxy DLL commonly used to inject mods",
                "mod_manager": "a mod manager hook",
                "unknown_dll": "an unrecognised DLL placed in the game folder",
            }.get(kind, "a modification")
            headline = f"The game crashed with {kind_label} present - this is likely mod-related, not a game bug"
    else:
        try:
            dll_verify = verify_critical_dlls(parsed)
        except Exception:
            dll_verify = {}
        bad_dll_name  = None
        bad_dll_verdict = None
        m140 = dll_verify.get("msvcp140")
        if m140 and m140.get("verdict") != "OK":
            bad_dll_name, bad_dll_verdict = "MSVCP140.dll", m140.get("verdict")
        if not bad_dll_name:
            for dll_key, r in dll_verify.get("runtime", {}).items():
                if r and r.get("verdict") != "OK":
                    bad_dll_name, bad_dll_verdict = dll_key, r.get("verdict")
                    break
        if not bad_dll_name:
            for dr in dll_verify.get("discord", []):
                if dr.get("verdict") != "OK":
                    bad_dll_name, bad_dll_verdict = dr.get("name", "Discord SDK DLL"), dr.get("verdict")
                    break
        if bad_dll_name:
            if bad_dll_verdict == "LIKELY_TAMPERED":
                headline = f"{bad_dll_name} appears to have been tampered with - this is likely not a game bug"
            else:
                headline = f"{bad_dll_name} failed authenticity verification ({bad_dll_verdict}) - this may not be a game bug"
        else:
            anticheat_names = ("easyanticheat", "beclient", "beservice", "battleye")
            try:
                crash_addr = int(ex.get("address", "0"), 16) if ex else 0
            except Exception:
                crash_addr = 0
            if crash_addr:
                crash_mod_name, _ = mod_for_addr(crash_addr)
                if crash_mod_name and any(n in crash_mod_name.lower() for n in anticheat_names):
                    headline = (f"The crash happened inside {crash_mod_name} (anti-cheat software), "
                               f"not the game's own code - this may be an anti-cheat conflict rather than a game bug")

    crash_tid   = ex.get("thread_id") if ex else None
    active_game = []
    for t in threads:
        if t["tid"] == crash_tid:
            continue
        rip = t.get("rip", 0)
        mod, off = mod_for_addr(rip)
        if not mod:
            continue
        full = next((m["name"] for m in modules
                     if PureWindowsPath(m["name"]).name == mod), "")
        full_lower = full.lower().replace("/", "\\")
        is_sys     = "\\windows\\" in full_lower
        is_handler = mod.lower() in CRASH_HANDLERS
        if not is_sys and not is_handler:
            active_game.append((mod, off))

    SUBSYSTEM_LABELS = {
        "dstorage":     "Asset streaming (DirectStorage)",
        "dstoragecore": "Asset streaming (DirectStorage core)",
        "d3d12":        "DirectX 12 rendering",
        "d3d11":        "DirectX 11 rendering",
        "dxgi":         "Display / swap chain",
        "lua":          "Lua scripting",
        "wwise":        "Wwise audio",
        "fmod":         "FMOD audio",
        "physx":        "PhysX physics",
        "steam_api":    "Steam API",
        "gameoverlayrenderer": "Steam overlay",
        "npggnt":       "GameGuard anti-cheat",
        "easyanticheat":"EasyAntiCheat",
        "amdxc":        "AMD GPU driver",
        "amdxx":        "AMD GPU driver",
        "nvwgf":        "NVIDIA GPU driver",
        "network":      "Game networking",
        "game.dll":     "Game logic",
        "physx":        "PhysX physics",
        "easyanticheat":"EasyAntiCheat anti-cheat",
        "battleye":     "BattlEye anti-cheat",
        "playfab":      "PlayFab online services",
        "partywin":     "Xbox Party SDK",
        "level_generation": "Level generation / proc-gen",
        "wwise_plugin": "Wwise audio plugin",
        "crs-client":   "Arrowhead crash reporter",
        "reshade":      "ReShade post-processing",
        "minhook":      "MinHook (mod injection)",
        "amd_fidelityfx": "AMD FidelityFX / FSR upscaler",
        "libxess":      "Intel XeSS upscaler",
        "nvspcap":      "NVIDIA ShadowPlay capture",
    }

    active_subsystems = []
    seen_labels = set()
    all_mod_names = " ".join(PureWindowsPath(m["name"]).name.lower() for m in modules)
    for kw, label in SUBSYSTEM_LABELS.items():
        if kw in all_mod_names and label not in seen_labels:
            active_subsystems.append(label)
            seen_labels.add(label)

    what_was_doing = "Unknown - no active game thread found at crash time"
    if active_game:
        mod, off = active_game[0]
        ann = annotate_frame(mod, off)
        what_was_doing = ann if ann else f"Executing code in {mod}"

    advice = []
    advice.append("Share this .dmp file with the 418th - they will investigate the crash.")
    advice.append("To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs - it often contains the real error message.")

    if any("amd" in n.lower() for n in all_mod_names.split()):
        advice.append("AMD GPU detected - try updating your AMD graphics drivers via the AMD website.")
    if any("nvwgf" in n.lower() for n in all_mod_names.split()):
        advice.append("NVIDIA GPU detected - try updating your NVIDIA graphics drivers via GeForce Experience or nvidia.com.")
    if "dstorage" in all_mod_names:
        advice.append("DirectStorage is loaded - ensure your GPU drivers are up to date as DS relies on driver support.")
    if any("npggnt" in n.lower() or "gameguard" in n.lower() for n in all_mod_names.split()):
        advice.append("GameGuard anti-cheat is active - a false positive block could cause this crash.")

    if mods.get("has_mods"):
        conf = mods.get("confidence", "LOW")
        if conf == "HIGH":
            advice.append("⚠ Mods detected with high confidence - mods may be causing this crash. Try reproducing without mods.")
        elif conf == "MED":
            advice.append("Possible mods or third-party DLLs detected - try reproducing without mods if possible.")

    return {
        "headline":          headline,
        "what_was_doing":    what_was_doing,
        "active_subsystems": active_subsystems,
        "advice":            advice,
        "rootcause":         rootcause,
        "mods":              mods,
        "pattern":           pattern,
        "patterns":          patterns if patterns is not None else ([pattern] if pattern else []),
    }

BLUE        = "#58a6ff"
ORANGE      = "#db6d28"
GRAY        = "#6e7681"
V_SUICIDE   = ORANGE
V_GAME_BUG  = RED
V_GPU       = PURPLE
V_MOD       = YELLOW
V_INCONCLUSIVE = GRAY
CONF_COLORS = {"HIGH": GREEN, "MED": YELLOW, "LOW": TEXT_DIM}


def compute_verdict(parsed: dict, rootcause: list, mods: dict, pattern: dict,
                    all_patterns: list, decoded_instr: dict = None) -> dict:
    ex = parsed.get("exception", {}) or {}
    modules = parsed.get("modules", [])
    threads = parsed.get("threads", [])

    crash_addr_str = ex.get("address", "0")
    try:
        crash_addr = int(crash_addr_str, 16)
    except (ValueError, TypeError):
        crash_addr = 0
    crash_module = "unknown"
    crash_offset = 0
    for m in modules:
        try:
            base = int(m["base"], 16)
            if base <= crash_addr < base + m["size"]:
                crash_module = PureWindowsPath(m["name"]).name
                crash_offset = crash_addr - base
                break
        except Exception:
            pass

    ex_code_str = ex.get("code", "0x00000000")
    try:
        ex_code = int(ex_code_str, 16)
    except (ValueError, TypeError):
        ex_code = 0


    is_suicide, suicide_reason = _is_stingray_suicide(parsed)
    if decoded_instr and decoded_instr.get("is_suicide"):
        is_suicide = True
        suicide_reason = "instruction-byte pattern matched"

    gpu_driver_frags = (
        "amdxc", "amdxx", "atidxx", "amdihk",
        "nvwgf", "nvd3d", "nvgpucomp", "nvldumdx",
        "igdumd", "igc64", "igdgmm",
    )
    is_gpu = (
        ex_code in (0x887A0005, 0x887A0006, 0x887A0007, 0x887A0020)
        or any(frag in crash_module.lower() for frag in gpu_driver_frags)
    )

    is_mod = (
        mods.get("has_mods") and mods.get("confidence") == "HIGH"
    )

    is_game_bug = False
    if ex_code in (0xC0000374, 0xC00000FD, 0xC0000409):
        is_game_bug = True
    elif ex_code == 0xC0000005 and not is_suicide:
        is_game_bug = True

    if is_suicide:
        verdict = "SUICIDE"
        color = V_SUICIDE
        su_pattern = None
        if all_patterns:
            for p in all_patterns:
                if p.get("id", "").startswith("SUICIDE"):
                    su_pattern = p
                    break
        if su_pattern:
            title = su_pattern.get("name", "Engine suicide")
            explanation = su_pattern.get("player_message", "")
        else:
            title = "Engine suicide (Stingray)"
            explanation = (
                "The Stingray engine intentionally terminated the process after detecting "
                "an internal error. This is NOT a game bug - the crash instruction is the "
                "engine's suicide mechanism. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs"
            )
        confidence = "HIGH"
        actions = [
            {"label": "1. Open .log file", "command": "open_log", "primary": True,
             "description": "Right-click game in Steam > Properties > Launch Options > add --log-to-file > launch and crash > check %APPDATA%\\Arrowhead\\Helldivers 2\\logs"},
            {"label": "2. Export report", "command": "export", "primary": False,
             "description": "Generate a PDF to share with the dev team"},
            {"label": "3. View active game thread", "command": "goto_threads", "primary": False,
             "description": "The thread that was running when suicide fired is the likely trigger"},
        ]

    elif is_gpu:
        verdict = "GPU"
        color = V_GPU
        if ex_code in (0x887A0005, 0x887A0006, 0x887A0007, 0x887A0020):
            dxgi_names = {
                0x887A0005: "GPU device removed",
                0x887A0006: "GPU device hung (TDR)",
                0x887A0007: "GPU device reset",
                0x887A0020: "GPU driver internal error",
            }
            title = dxgi_names.get(ex_code, "GPU error")
        else:
            title = f"GPU driver crash ({crash_module})"
        explanation = (
            "The GPU or GPU driver crashed. This is almost always a driver or hardware issue, "
            "not a game bug. Update GPU drivers, check temperatures, and revert any overclocks."
        )
        confidence = "HIGH"
        actions = [
            {"label": "1. Update GPU drivers", "command": "gpu_guide", "primary": True,
             "description": "Use DDU for a clean install - most GPU crashes are driver bugs"},
            {"label": "2. Export report", "command": "export", "primary": False,
             "description": "Generate a PDF to share with the dev team"},
            {"label": "3. Open GPU log (DRED)", "command": "open_dred", "primary": False,
             "description": "If you have a DRED log, open it for breadcrumb analysis"},
        ]

    elif is_mod:
        verdict = "MOD"
        color = V_MOD
        high_inds = [i for i in mods.get("indicators", []) if i.get("severity") == "HIGH"]
        if high_inds:
            kind = high_inds[0].get("type", "mod")
            if kind == "proxy_dll":
                title = "Proxy DLL detected (ReShade/ENB/mod hook)"
            elif kind == "mod_manager":
                title = "Mod manager detected"
            else:
                title = "Unknown DLL in game folder"
        else:
            title = "Mods detected"
        explanation = (
            "Third-party mods or proxy DLLs were detected. These can cause crashes that "
            "wouldn't occur in the vanilla game. Remove mods and retest before reporting as a bug."
        )
        confidence = "HIGH"
        actions = [
            {"label": "1. Remove mods and retest", "command": "mod_guide", "primary": True,
             "description": "Remove proxy DLLs from the game folder and verify game files"},
            {"label": "2. Export report", "command": "export", "primary": False,
             "description": "Generate a PDF showing the mod indicators found"},
            {"label": "3. View mod details", "command": "goto_mods", "primary": False,
             "description": "See exactly which DLLs and paths were flagged"},
        ]

    elif is_game_bug:
        verdict = "GAME_BUG"
        color = V_GAME_BUG
        if ex_code == 0xC0000005:
            params = ex.get("params", [])
            fault_addr = int(params[1], 16) if len(params) >= 2 else 0
            if fault_addr == 0:
                title = "Null pointer dereference"
            elif fault_addr < 0x1000:
                title = f"Null pointer read at offset +{fault_addr}"
            else:
                title = "Invalid memory access"
        elif ex_code == 0xC0000374:
            title = "Heap corruption"
        elif ex_code == 0xC00000FD:
            title = "Stack overflow (infinite recursion)"
        elif ex_code == 0xC0000409:
            title = "Stack buffer overrun"
        else:
            title = f"Game crash (0x{ex_code:08X})"
        explanation = (
            "This is a game-side bug. The crash happened inside game code due to a null pointer, "
            "memory corruption, or similar error. Report this with the .dmp and .log files."
        )
        confidence = "HIGH"
        actions = [
            {"label": "1. Export report", "command": "export", "primary": True,
             "description": "Generate a PDF to share with the dev team"},
            {"label": "2. Open .log file", "command": "open_log", "primary": False,
             "description": "The engine log may have additional context"},
            {"label": "3. View call chain", "command": "goto_rootcause", "primary": False,
             "description": "See the stack walk leading to the crash"},
        ]

    else:
        verdict = "INCONCLUSIVE"
        color = V_INCONCLUSIVE
        title = "Could not determine root cause"
        explanation = (
            "The dump doesn't contain enough data to determine the root cause. "
            "Check the .log file and share both .dmp and .log with the dev team."
        )
        confidence = "LOW"
        actions = [
            {"label": "1. Open .log file", "command": "open_log", "primary": True,
             "description": "The engine log may have the error message"},
            {"label": "2. Export report", "command": "export", "primary": False,
             "description": "Generate a PDF for the dev team"},
        ]

    sig_input = f"{verdict}|{crash_module}|{crash_offset // 0x1000:04X}|{ex_code_str}"
    signature = hashlib.md5(sig_input.encode()).hexdigest()[:8].upper()
    sig_prefix = {"SUICIDE": "SUI", "GPU": "GPU", "MOD": "MOD", "GAME_BUG": "BUG", "INCONCLUSIVE": "UNK"}[verdict]
    signature = f"{sig_prefix}-{signature}"

    return {
        "verdict": verdict,
        "color": color,
        "title": title,
        "explanation": explanation,
        "confidence": confidence,
        "crash_module": crash_module,
        "crash_offset": crash_offset,
        "crash_address": crash_addr_str,
        "exception_code": ex_code_str,
        "actions": actions,
        "signature": signature,
    }



class VerdictBanner(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG2)
        self._verdict_color = V_INCONCLUSIVE
        self._build()

    def _build(self):
        self._strip = tk.Frame(self, bg=self._verdict_color, height=4)
        self._strip.pack(fill="x")

        content = tk.Frame(self, bg=BG2, padx=20, pady=12)
        content.pack(fill="x")

        left = tk.Frame(content, bg=BG2)
        left.pack(side="left", fill="x", expand=True)

        self._verdict_label = tk.Label(left, text="INCONCLUSIVE", bg=BG2,
                                       fg=self._verdict_color,
                                       font=(UI_FONT, 9, "bold"))
        self._verdict_label.pack(anchor="w")

        self._title_label = tk.Label(left, text="No dump loaded", bg=BG2,
                                     fg=TEXT, font=(UI_FONT, 14, "bold"),
                                     wraplength=700, anchor="w", justify="left")
        self._title_label.pack(anchor="w", pady=(2, 0))

        self._explanation_label = tk.Label(left, text="", bg=BG2, fg=TEXT_DIM,
                                           font=(UI_FONT, 9), wraplength=700,
                                           anchor="w", justify="left")
        self._explanation_label.pack(anchor="w", pady=(2, 0))

        self._location_label = tk.Label(left, text="", bg=BG2, fg=TEXT_DIM,
                                        font=(UI_MONO, 8))
        self._location_label.pack(anchor="w", pady=(4, 0))

        right = tk.Frame(content, bg=BG2)
        right.pack(side="right", fill="y")

        self._conf_label = tk.Label(right, text="", bg=BG2, fg=TEXT_DIM,
                                    font=(UI_FONT, 8, "bold"))
        self._conf_label.pack(anchor="e")

        self._sig_label = tk.Label(right, text="", bg=BG2, fg=TEXT_DIM,
                                   font=(UI_MONO, 8))
        self._sig_label.pack(anchor="e", pady=(2, 0))

    def update_verdict(self, verdict_info: dict):
        color = verdict_info["color"]
        self._verdict_color = color
        self._strip.configure(bg=color)
        self._verdict_label.configure(text=verdict_info["verdict"], fg=color)
        self._title_label.configure(text=verdict_info["title"])
        self._explanation_label.configure(text=verdict_info["explanation"])

        crash_loc = (f"Crash in {verdict_info['crash_module']} +0x{verdict_info['crash_offset']:X}  "
                     f"|  {verdict_info['exception_code']}  "
                     f"|  {verdict_info['crash_address']}")
        self._location_label.configure(text=crash_loc)

        conf = verdict_info["confidence"]
        self._conf_label.configure(text=f"CONFIDENCE: {conf}", fg=CONF_COLORS.get(conf, TEXT_DIM))
        self._sig_label.configure(text=f"SIG: {verdict_info['signature']}")

    def clear(self):
        self._strip.configure(bg=V_INCONCLUSIVE)
        self._verdict_label.configure(text="INCONCLUSIVE", fg=V_INCONCLUSIVE)
        self._title_label.configure(text="No dump loaded")
        self._explanation_label.configure(text="")
        self._location_label.configure(text="")
        self._conf_label.configure(text="")
        self._sig_label.configure(text="")


class ActionPanel(tk.Frame):

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)
        self._controller = controller
        self._buttons = []
        self._build()

    def _build(self):
        tk.Label(self, text="WHAT TO DO NEXT", bg=BG, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", pady=(8, 4))

        self._btn_frame = tk.Frame(self, bg=BG)
        self._btn_frame.pack(fill="x")

    def update_actions(self, actions: list):
        for btn in self._buttons:
            btn.destroy()
        self._buttons = []

        for action in actions:
            is_primary = action.get("primary", False)
            bg_color = ACCENT if is_primary else BG3
            fg_color = "white" if is_primary else TEXT
            font_weight = "bold" if is_primary else "normal"

            btn = tk.Button(self._btn_frame, text=action["label"],
                            command=lambda c=action["command"]: self._controller.execute_action(c),
                            bg=bg_color, fg=fg_color,
                            activebackground=ACCENT2 if is_primary else BORDER,
                            activeforeground="white",
                            relief="flat", padx=16, pady=8,
                            font=(UI_FONT, 9, font_weight),
                            cursor="hand2")
            btn.pack(side="left", padx=(0, 8))
            self._buttons.append(btn)

    def clear(self):
        for btn in self._buttons:
            btn.destroy()
        self._buttons = []


class CrashSummaryCard(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        self._build()

    def _build(self):
        tk.Label(self, text="CRASH SUMMARY", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=16, pady=10).pack(anchor="w")

        self._grid = tk.Frame(self, bg=BG2, padx=16, pady=8)
        self._grid.pack(fill="x", pady=(0, 10))
        self._rows = {}

    def update_summary(self, parsed: dict, verdict_info: dict):
        for w in self._grid.winfo_children():
            w.destroy()
        self._rows.clear()

        ex = parsed.get("exception", {}) or {}
        si = parsed.get("system_info", {}) or {}
        ts = parsed.get("timestamp", "N/A")

        fields = [
            ("Exception",    f"{ex.get('code', 'N/A')}"),
            ("Crash module", f"{verdict_info['crash_module']} +0x{verdict_info['crash_offset']:X}"),
            ("Crash address", verdict_info["crash_address"]),
            ("Thread ID",    str(ex.get("thread_id", "N/A"))),
            ("Dump size",    f"{parsed.get('size_mb', 'N/A')} MB"),
            ("Modules",      str(len(parsed.get("modules", [])))),
            ("Threads",      str(len(parsed.get("threads", [])))),
            ("Memory ranges",str(len(parsed.get("memory_map", [])))),
            ("Architecture", si.get("arch", "N/A")),
            ("CPU count",    str(si.get("cpu_count", "N/A"))),
            ("OS version",   si.get("os_version", "N/A")),
            ("Timestamp",    ts),
        ]

        for i, (label, value) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            tk.Label(self._grid, text=label, bg=BG2, fg=TEXT_DIM,
                     font=(UI_FONT, 8), anchor="w").grid(row=row, column=col, sticky="w", padx=(0, 8), pady=1)
            tk.Label(self._grid, text=value, bg=BG2, fg=TEXT,
                     font=(UI_MONO, 9), anchor="w").grid(row=row, column=col+1, sticky="w", padx=(0, 24), pady=1)


class EvidenceCard(tk.Frame):

    def __init__(self, parent, finding: dict, controller=None, **kwargs):
        super().__init__(parent, **kwargs)
        conf = finding.get("conf", "LOW")
        color = CONF_COLORS.get(conf, TEXT_DIM)

        self.configure(bg=BG2, highlightbackground=color, highlightthickness=0)
        self._finding = finding
        self._controller = controller
        self._expanded = False

        border = tk.Frame(self, bg=color, width=3)
        border.pack(side="left", fill="y")

        content = tk.Frame(self, bg=BG2, padx=12, pady=8)
        content.pack(side="left", fill="x", expand=True)

        title_row = tk.Frame(content, bg=BG2)
        title_row.pack(fill="x")

        tk.Label(title_row, text=f"[{conf}]", bg=BG2, fg=color,
                 font=(UI_FONT, 8, "bold")).pack(side="left")

        title_text = finding.get("title", "")
        link = finding.get("link")
        if link:
            title_label = tk.Label(title_row, text=title_text, bg=BG2, fg=BLUE,
                                   font=(UI_FONT, 9, "bold"), cursor="hand2",
                                   anchor="w")
            title_label.pack(side="left", padx=(8, 0))
            if controller:
                title_label.bind("<Button-1>", lambda e, l=link: controller.navigate_to(l))
        else:
            tk.Label(title_row, text=title_text, bg=BG2, fg=TEXT,
                     font=(UI_FONT, 9, "bold"), anchor="w").pack(side="left", padx=(8, 0))

        detail = finding.get("detail", "")
        if detail:
            self._detail_label = tk.Label(content, text=detail, bg=BG2, fg=TEXT_DIM,
                                          font=(UI_FONT, 8), wraplength=750,
                                          anchor="w", justify="left")
            self._detail_label.pack(fill="x", pady=(4, 0))


class EvidenceGroup(tk.Frame):

    def __init__(self, parent, title: str, color: str = ACCENT, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)
        self._title = title
        self._color = color
        self._expanded = True
        self._build()

    def _bind_click(self, widget):
        widget.bind("<Button-1>", lambda e: self.toggle())
        for child in widget.winfo_children():
            self._bind_click(child)

    def _build(self):
        self._header = tk.Frame(self, bg=BG, cursor="hand2", pady=6)
        self._header.pack(fill="x")

        self._arrow = tk.Label(self._header, text="▼", bg=BG, fg=self._color,
                               font=(UI_FONT, 10, "bold"))
        self._arrow.pack(side="left")

        tk.Label(self._header, text=self._title, bg=BG, fg=self._color,
                 font=(UI_FONT, 9, "bold")).pack(side="left", padx=(6, 0))

        self._count_label = tk.Label(self._header, text="", bg=BG, fg=TEXT_DIM,
                                     font=(UI_FONT, 9))
        self._count_label.pack(side="left", padx=(8, 0))

        self._bind_click(self._header)

        self._container = tk.Frame(self, bg=BG)
        self._container.pack(fill="x", padx=(16, 0), pady=(2, 0))

    def add_finding(self, finding: dict, controller=None):
        card = EvidenceCard(self._container, finding, controller, bg=BG2)
        card.pack(fill="x", pady=2)

    def set_count(self, count: int):
        self._count_label.configure(text=f"({count})")

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._arrow.configure(text="▼")
            self._container.pack(fill="x", padx=(16, 0), pady=(2, 0))
        else:
            self._arrow.configure(text="▶")
            self._container.pack_forget()


class CallChainWidget(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)
        self._build()

    def _build(self):
        tk.Label(self, text="CALL CHAIN (crash thread stack walk)", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", pady=(8, 4))

        self._frames_container = tk.Frame(self, bg=BG)
        self._frames_container.pack(fill="x", padx=16)

        self._quality_label = tk.Label(self, text="", bg=BG, fg=TEXT_DIM,
                                       font=(UI_FONT, 8))
        self._quality_label.pack(anchor="w", pady=(4, 0))

    def update_chain(self, chain: list, unwind_info: dict, extended: list = None):
        for w in self._frames_container.winfo_children():
            w.destroy()

        if not chain:
            tk.Label(self._frames_container, text="No call chain data available",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w")
            return

        for i, (addr, mod, off) in enumerate(chain):
            is_crash = (i == 0)
            verified = extended[i][3] if extended and i < len(extended) else None

            if is_crash:
                color = RED
                prefix = "CRASH →"
            elif mod.lower().endswith(".exe"):
                color = ORANGE
                prefix = f"  ← #{i:02d}"
            else:
                color = BLUE
                prefix = f"  ← #{i:02d}"

            frame_row = tk.Frame(self._frames_container, bg=BG)
            frame_row.pack(fill="x", pady=1)

            tk.Label(frame_row, text=prefix, bg=BG, fg=color,
                     font=(UI_MONO, 8, "bold")).pack(side="left")

            tk.Label(frame_row, text=f"0x{addr:016X}", bg=BG, fg=TEXT_DIM,
                     font=(UI_MONO, 8)).pack(side="left", padx=(8, 0))

            tk.Label(frame_row, text=f"{mod} +0x{off:X}", bg=BG, fg=color,
                     font=(UI_MONO, 8, "bold")).pack(side="left", padx=(8, 0))

            if verified is True:
                tk.Label(frame_row, text="[pdata✓]", bg=BG, fg=GREEN,
                         font=(UI_MONO, 7)).pack(side="left", padx=(8, 0))
            elif verified is False:
                tk.Label(frame_row, text="[heuristic]", bg=BG, fg=YELLOW,
                         font=(UI_MONO, 7)).pack(side="left", padx=(8, 0))

        pdata_c = unwind_info.get("pdata_confirmed", 0)
        heuristic = unwind_info.get("heuristic", 0)
        pdata_mods = unwind_info.get("pdata_modules", 0)
        total_mods = unwind_info.get("total_modules", 0)
        if pdata_mods > 0:
            quality = (f".pdata-verified: {pdata_c} frames confirmed, {heuristic} heuristic | "
                       f".pdata available for {pdata_mods}/{total_mods} modules")
        else:
            quality = f"Heuristic only ({heuristic} frames) - .pdata not available in this dump"
        self._quality_label.configure(text=quality)


class ThreadGroupWidget(tk.Frame):

    def __init__(self, parent, purpose: str, color: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)
        self._purpose = purpose
        self._color = color
        self._expanded = False
        self._build()

    def _bind_click(self, widget):
        widget.bind("<Button-1>", lambda e: self.toggle())
        for child in widget.winfo_children():
            self._bind_click(child)

    def _build(self):
        self._header = tk.Frame(self, bg=BG, cursor="hand2", pady=6)
        self._header.pack(fill="x")

        self._arrow = tk.Label(self._header, text="▶", bg=BG, fg=self._color,
                               font=(UI_FONT, 10, "bold"))
        self._arrow.pack(side="left")

        tk.Label(self._header, text="●", bg=BG, fg=self._color,
                 font=(UI_FONT, 11)).pack(side="left", padx=(4, 0))

        tk.Label(self._header, text=self._purpose, bg=BG, fg=TEXT,
                 font=(UI_FONT, 9, "bold")).pack(side="left", padx=(4, 0))

        self._count_label = tk.Label(self._header, text="", bg=BG, fg=TEXT_DIM,
                                     font=(UI_FONT, 9))
        self._count_label.pack(side="left", padx=(8, 0))

        self._bind_click(self._header)

        self._container = tk.Frame(self, bg=BG)

    def add_thread(self, thread_info: dict):
        row = tk.Frame(self._container, bg=BG2, padx=8, pady=4)
        row.pack(fill="x", pady=1)

        tid = thread_info.get("tid", "?")
        state = thread_info.get("state", "?")
        doing = thread_info.get("doing", "")
        module = thread_info.get("module", "")
        offset = thread_info.get("offset", "")

        is_crashed = thread_info.get("is_crashed", False)
        state_color = RED if is_crashed else TEXT_DIM

        tk.Label(row, text=f"TID {tid}", bg=BG2, fg=state_color,
                 font=(UI_MONO, 8, "bold")).pack(side="left")
        tk.Label(row, text=f"[{state}]", bg=BG2, fg=state_color,
                 font=(UI_MONO, 7)).pack(side="left", padx=(8, 0))
        tk.Label(row, text=f"{module} {offset}", bg=BG2, fg=TEXT,
                 font=(UI_MONO, 8)).pack(side="left", padx=(8, 0))
        tk.Label(row, text=doing, bg=BG2, fg=TEXT_DIM,
                 font=(UI_FONT, 8), wraplength=400).pack(side="left", padx=(8, 0))

    def set_count(self, count: int):
        self._count_label.configure(text=f"({count} threads)")

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._arrow.configure(text="▼")
            self._container.pack(fill="x", padx=(16, 0), pady=(2, 4))
        else:
            self._arrow.configure(text="▶")
            self._container.pack_forget()


class ModDetectionBanner(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG2)
        self._build()

    def _build(self):
        self._strip = tk.Frame(self, width=3, bg=GREEN)
        self._strip.pack(side="left", fill="y")

        content = tk.Frame(self, bg=BG2, padx=12, pady=8)
        content.pack(side="left", fill="x", expand=True)

        top_row = tk.Frame(content, bg=BG2)
        top_row.pack(fill="x")

        self._icon_label = tk.Label(top_row, text="[OK]", bg=BG2, fg=GREEN,
                                    font=(UI_FONT, 9, "bold"))
        self._icon_label.pack(side="left")

        self._text_label = tk.Label(top_row, text="No mods detected", bg=BG2, fg=TEXT,
                                    font=(UI_FONT, 9))
        self._text_label.pack(side="left", padx=(8, 0))

        self._detail_frame = tk.Frame(content, bg=BG2)

    def update_status(self, mods: dict):
        has_mods = mods.get("has_mods", False)
        confidence = mods.get("confidence", "LOW")
        indicators = mods.get("indicators", [])

        for w in self._detail_frame.winfo_children():
            w.destroy()
        self._detail_frame.pack_forget()

        if not has_mods:
            self._strip.configure(bg=GREEN)
            self._icon_label.configure(text="[OK]", fg=GREEN)
            self._text_label.configure(text="No mods or proxy DLLs detected")
        elif confidence == "HIGH":
            high_inds = [i for i in indicators if i.get("severity") == "HIGH"]
            self._strip.configure(bg=YELLOW)
            self._icon_label.configure(text="[!]", fg=YELLOW)
            count = len(indicators)
            self._text_label.configure(
                text=f"{count} mod/proxy DLL indicators found ({len(high_inds)} HIGH)")

            self._detail_frame.pack(fill="x", pady=(6, 0))
            for ind in indicators[:8]:
                sev = ind.get("severity", "?")
                ind_type = ind.get("type", "?")
                detail = ind.get("detail", "")
                path = ind.get("path", "")
                filename = path.split("\\")[-1] if path else ""

                sev_color = RED if sev == "HIGH" else (YELLOW if sev == "MED" else TEXT_DIM)

                row = tk.Frame(self._detail_frame, bg=BG2)
                row.pack(fill="x", pady=1)

                tk.Label(row, text=f"  [{sev}]", bg=BG2, fg=sev_color,
                         font=(UI_MONO, 8, "bold")).pack(side="left")
                tk.Label(row, text=f"  {ind_type}", bg=BG2, fg=sev_color,
                         font=(UI_FONT, 8, "bold")).pack(side="left", padx=(4, 0))
                if filename:
                    tk.Label(row, text=f"  {filename}", bg=BG2, fg=TEXT,
                             font=(UI_MONO, 8)).pack(side="left", padx=(4, 0))
                if detail and detail != path:
                    tk.Label(row, text=f"  - {detail[:80]}", bg=BG2, fg=TEXT_DIM,
                             font=(UI_FONT, 7)).pack(side="left", padx=(4, 0))

            if len(indicators) > 8:
                tk.Label(self._detail_frame, text=f"  ... and {len(indicators)-8} more",
                         bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 7)).pack(anchor="w", pady=1)
        else:
            self._strip.configure(bg=YELLOW)
            self._icon_label.configure(text="[?]", fg=YELLOW)
            self._text_label.configure(text=f"Possible mods detected ({len(indicators)} indicators)")

            if indicators:
                self._detail_frame.pack(fill="x", pady=(6, 0))
                for ind in indicators[:4]:
                    ind_type = ind.get("type", "?")
                    path = ind.get("path", "")
                    filename = path.split("\\")[-1] if path else ""
                    row = tk.Frame(self._detail_frame, bg=BG2)
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text=f"  {ind_type}: {filename}", bg=BG2, fg=TEXT_DIM,
                             font=(UI_MONO, 8)).pack(side="left")


class DropZone(tk.Frame):

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)
        self._controller = controller
        self._build()

    def _build(self):
        center = tk.Frame(self, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="Stingray", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 28, "bold")).pack()
        tk.Label(center, text="Crash Analyzer", bg=BG, fg=TEXT,
                 font=(UI_FONT, 28)).pack()

        tk.Label(center, text="Drop a .dmp file here, or browse", bg=BG, fg=TEXT_DIM,
                 font=(UI_FONT, 11)).pack(pady=(30, 0))

        tk.Button(center, text="  Browse .dmp", command=self._controller._open_file,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=24, pady=10,
                  font=(UI_FONT, 10, "bold"), cursor="hand2").pack(pady=(20, 0))

        tk.Button(center, text="  Open GPU Log (DRED)", command=self._controller._open_dred_file,
                  bg=PURPLE, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=20, pady=8,
                  font=(UI_FONT, 9), cursor="hand2").pack(pady=(8, 0))

        tk.Label(center, text="Also accepts .mdmp  |  Ctrl+F8 for internal debugger",
                 bg=BG, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(pady=(30, 0))


class ScrollableFrame(tk.Frame):

    _active_frame = None

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=BG)

        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview,
                                       bg=BG2, troughcolor=BG, relief="flat", width=10)
        self._inner = tk.Frame(self._canvas, bg=BG)

        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._canvas.bind("<Enter>", self._on_enter)
        self._inner.bind("<Enter>", self._on_enter)
        self._bind_enter_recursive(self._inner)

        if not hasattr(ScrollableFrame, '_global_bound'):
            self.bind_class("all", "<MouseWheel>", ScrollableFrame._global_mousewheel)
            self.bind_class("all", "<Button-4>", ScrollableFrame._global_button4)
            self.bind_class("all", "<Button-5>", ScrollableFrame._global_button5)
            ScrollableFrame._global_bound = True

    def _bind_enter_recursive(self, widget):
        widget.bind("<Enter>", self._on_enter)
        for child in widget.winfo_children():
            self._bind_enter_recursive(child)

    def rebind_enter(self):
        self._bind_enter_recursive(self._inner)

    def _on_enter(self, event):
        ScrollableFrame._active_frame = self

    @staticmethod
    def _global_mousewheel(event):
        frame = ScrollableFrame._active_frame
        if frame is None:
            return
        frame._do_scroll(int(-1 * (event.delta / 120)))

    @staticmethod
    def _global_button4(event):
        frame = ScrollableFrame._active_frame
        if frame is not None:
            frame._do_scroll(-1)

    @staticmethod
    def _global_button5(event):
        frame = ScrollableFrame._active_frame
        if frame is not None:
            frame._do_scroll(1)

    def _do_scroll(self, units):
        scrollregion = self._canvas.bbox("all")
        if not scrollregion:
            return
        canvas_h = self._canvas.winfo_height()
        content_h = scrollregion[3] - scrollregion[1]
        if content_h > canvas_h:
            self._canvas.yview_scroll(units, "units")

    def _on_inner_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._inner_id, width=event.width)

    @property
    def inner(self):
        return self._inner



class CrashAnalyzerUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Stingray Crash Analyzer")
        self.configure(bg=BG)
        self.geometry("1200x850")
        self.minsize(900, 650)

        try:
            _icon_path = resource_path("assets", "icon.ico")
            if _icon_path.exists():
                self.iconbitmap(default=str(_icon_path))
        except Exception:
            pass

        self.bind_all("<Control-F8>", self._open_debugger)
        self.bind_all("<Control-1>", lambda e: self._select_tab(0))
        self.bind_all("<Control-2>", lambda e: self._select_tab(1))
        self.bind_all("<Control-3>", lambda e: self._select_tab(2))
        self.bind_all("<Control-4>", lambda e: self._select_tab(3))
        self.bind_all("<Control-e>", lambda e: self.execute_action("export"))
        self.bind_all("<Control-l>", lambda e: self.execute_action("open_log"))
        self.bind_all("<Control-o>", lambda e: self._open_file())

        self._parsed = None
        self._verdict_info = None
        self._load_generation = 0

        self._build_ui()

        self._show_drop_zone()

    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, pady=0, padx=0)
        topbar.pack(fill="x", side="top")

        brand = tk.Frame(topbar, bg=BG2, padx=20, pady=10)
        brand.pack(side="left")
        tk.Label(brand, text="Stingray", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 12, "bold")).pack(side="left")
        tk.Label(brand, text=" Crash Analyzer", bg=BG2, fg=TEXT,
                 font=(UI_FONT, 12)).pack(side="left")

        btn_area = tk.Frame(topbar, bg=BG2, padx=16, pady=8)
        btn_area.pack(side="right")

        self._open_btn = tk.Button(btn_area, text="  Open .dmp",
                                   command=self._open_file,
                                   bg=ACCENT, fg="white",
                                   activebackground=ACCENT2,
                                   relief="flat", padx=14, pady=5,
                                   font=(UI_FONT, 9, "bold"),
                                   cursor="hand2")
        self._open_btn.pack(side="left", padx=(0, 8))

        self._open_dred_btn = tk.Button(btn_area, text="  Open GPU Log",
                                        command=self._open_dred_file,
                                        bg=PURPLE, fg="white",
                                        activebackground=ACCENT2,
                                        relief="flat", padx=12, pady=5,
                                        font=(UI_FONT, 9, "bold"),
                                        cursor="hand2")
        self._open_dred_btn.pack(side="left", padx=(0, 8))

        self._export_btn = tk.Button(btn_area, text="  Export",
                                     command=lambda: self.execute_action("export"),
                                     bg=BG3, fg=TEXT_DIM,
                                     activebackground=BORDER, activeforeground=TEXT,
                                     relief="flat", padx=12, pady=5,
                                     font=(UI_FONT, 9),
                                     cursor="hand2")
        self._export_btn.pack(side="left", padx=(0, 8))

        self._log_btn = tk.Button(btn_area, text="  Open .log",
                                  command=lambda: self.execute_action("open_log"),
                                  bg=BG3, fg=TEXT_DIM,
                                  activebackground=BORDER, activeforeground=TEXT,
                                  relief="flat", padx=12, pady=5,
                                  font=(UI_FONT, 9),
                                  cursor="hand2")
        self._log_btn.pack(side="left")

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        self._verdict_banner = VerdictBanner(self, bg=BG2)
        self._verdict_banner.pack(fill="x")
        self._verdict_banner.clear()

        self._action_panel = ActionPanel(self, self, bg=BG)
        self._action_panel.pack(fill="x", padx=20)
        self._action_panel.clear()

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_DIM,
                        padding=[20, 8], font=(UI_FONT, 9))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        self._tab_summary = tk.Frame(self._nb, bg=BG)
        self._tab_timeline = tk.Frame(self._nb, bg=BG)
        self._tab_evidence = tk.Frame(self._nb, bg=BG)
        self._tab_registers = tk.Frame(self._nb, bg=BG)
        self._tab_threads = tk.Frame(self._nb, bg=BG)
        self._tab_modules = tk.Frame(self._nb, bg=BG)
        self._tab_gpu = tk.Frame(self._nb, bg=BG)

        self._nb.add(self._tab_summary, text="  Summary  ")
        self._nb.add(self._tab_timeline, text="  Crash Timeline  ")
        self._nb.add(self._tab_evidence, text="  Evidence  ")
        self._nb.add(self._tab_registers, text="  Registers  ")
        self._nb.add(self._tab_threads, text="  Threads  ")
        self._nb.add(self._tab_modules, text="  Modules & DLLs  ")
        self._nb.add(self._tab_gpu, text="  GPU Hang  ")

        self._build_summary_tab()
        self._build_timeline_tab()
        self._build_evidence_tab()
        self._build_registers_tab()
        self._build_threads_tab()
        self._build_modules_tab()
        self._build_gpu_tab()

        for i in range(self._nb.index('end')):
            self._nb.select(i)
            self.update_idletasks()
        self._nb.select(0)

        self._drop_zone = DropZone(self, self, bg=BG)

        status = tk.Frame(self, bg=BG2, pady=0)
        status.pack(fill="x", side="bottom")
        tk.Frame(status, bg=BORDER, height=1).pack(fill="x")
        status_inner = tk.Frame(status, bg=BG2, padx=16, pady=5)
        status_inner.pack(fill="x")
        self._prog = ttk.Progressbar(status_inner, mode="indeterminate", length=100)
        self._prog.pack(side="right")
        self._status_var = tk.StringVar(value="Ready - drop a .dmp file to begin")
        tk.Label(status_inner, textvariable=self._status_var,
                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")

    def _build_summary_tab(self):
        scrollable = ScrollableFrame(self._tab_summary, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._summary_inner = scrollable.inner

        self._crash_summary = CrashSummaryCard(self._summary_inner, bg=BG2)
        self._crash_summary.pack(fill="x", padx=20, pady=(12, 8))

        instr_frame = tk.Frame(self._summary_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        instr_frame.pack(fill="x", padx=20, pady=4)

        tk.Label(instr_frame, text="CRASH INSTRUCTION", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        self._instr_text = tk.Label(instr_frame, text="N/A", bg=BG2, fg=TEXT,
                                    font=(UI_MONO, 11, "bold"), padx=14, anchor="w")
        self._instr_text.pack(anchor="w", fill="x")

        self._instr_explanation = tk.Label(instr_frame, text="", bg=BG2, fg=TEXT_DIM,
                                           font=(UI_FONT, 9), padx=14, pady=4,
                                           wraplength=800, anchor="w", justify="left")
        self._instr_explanation.pack(anchor="w", fill="x")

        self._mod_banner = ModDetectionBanner(self._summary_inner, bg=BG2)
        self._mod_banner.pack(fill="x", padx=20, pady=4)

        dll_frame = tk.Frame(self._summary_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        dll_frame.pack(fill="x", padx=20, pady=4)

        tk.Label(dll_frame, text="DLL AUTHENTICITY", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        self._dll_status_frame = tk.Frame(dll_frame, bg=BG2, padx=14, pady=0)
        self._dll_status_frame.pack(fill="x")

        doing_frame = tk.Frame(self._summary_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        doing_frame.pack(fill="x", padx=20, pady=4)

        tk.Label(doing_frame, text="WHAT THE ENGINE WAS DOING", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        self._engine_doing = tk.Label(doing_frame, text="", bg=BG2, fg=TEXT,
                                      font=(UI_FONT, 10), wraplength=800,
                                      padx=14, pady=0, anchor="w", justify="left")
        self._engine_doing.pack(anchor="w", fill="x")

        self._active_thread_frame = tk.Frame(self._summary_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)

        tk.Label(self._active_thread_frame, text="ACTIVE GAME THREAD (likely trigger)", bg=BG2, fg=ORANGE,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        self._active_thread_text = tk.Label(self._active_thread_frame, text="", bg=BG2, fg=TEXT,
                                            font=(UI_MONO, 9), padx=14, pady=0,
                                            wraplength=800, anchor="w", justify="left")
        self._active_thread_text.pack(anchor="w", fill="x")

        chain_frame = tk.Frame(self._summary_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        chain_frame.pack(fill="x", padx=20, pady=4)

        tk.Label(chain_frame, text="CALL CHAIN (top 5 frames)", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        self._chain_summary_frame = tk.Frame(chain_frame, bg=BG2, padx=14, pady=0)
        self._chain_summary_frame.pack(fill="x")

        self._chain_quality_label = tk.Label(chain_frame, text="", bg=BG2, fg=TEXT_DIM,
                                              font=(UI_FONT, 8), padx=14, pady=0)
        self._chain_quality_label.pack(anchor="w")

        tk.Label(self._summary_inner, text="OTHER POSSIBILITIES & SUBSYSTEM MATCHES", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        self._possibilities_frame = tk.Frame(self._summary_inner, bg=BG)
        self._possibilities_frame.pack(fill="x", padx=20)

        tk.Label(self._summary_inner, text="WHAT WAS THE PLAYER DOING? (optional - included in exported report)", bg=BG, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(20, 4))

        self._player_notes = tk.Text(self._summary_inner, height=3, bg=BG2, fg=TEXT,
                                     font=(UI_FONT, 9), relief="flat",
                                     insertbackground=TEXT, wrap="word",
                                     highlightbackground=BORDER, highlightthickness=1)
        self._player_notes.pack(fill="x", padx=20, pady=(0, 20))

    def _build_timeline_tab(self):
        scrollable = ScrollableFrame(self._tab_timeline, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._timeline_inner = scrollable.inner

        tk.Label(self._timeline_inner, text="CRASH TIMELINE", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 12, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        tk.Label(self._timeline_inner,
                 text="Reconstructed chain of events leading to the crash, from initial cause to final fault.",
                 bg=BG, fg=TEXT_DIM, font=(UI_FONT, 9),
                 wraplength=800).pack(anchor="w", padx=20, fill="x")

        self._timeline_container = tk.Frame(self._timeline_inner, bg=BG)
        self._timeline_container.pack(fill="x", padx=20, pady=(12, 20))

        self._timeline_placeholder = tk.Label(self._timeline_container,
            text="No dump loaded. Open a .dmp file to see the crash timeline.",
            bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10))
        self._timeline_placeholder.pack(pady=40)

    def _display_timeline(self, parsed: dict, rootcause: list, mods: dict,
                          pattern, all_patterns: list, verdict_info: dict,
                          decoded_instr: dict = None):
        for w in self._timeline_container.winfo_children():
            w.destroy()

        ex = parsed.get("exception") or {}
        is_suicide = verdict_info["verdict"] == "SUICIDE"
        chain = parsed.get("_stack_chain_extended", [])

        self._timeline_add_event(
            self._timeline_container,
            step=1,
            title=verdict_info["title"],
            color=verdict_info["color"],
            icon=self._timeline_verdict_icon(verdict_info["verdict"]),
            details=[
                f"Verdict: {verdict_info['verdict']} (confidence: {verdict_info['confidence']})",
                verdict_info["explanation"],
                f"Crash signature: {verdict_info['signature']}",
            ],
            tags=[verdict_info["verdict"], verdict_info["confidence"]],
        )

        all_mod_names = " ".join(PureWindowsPath(m["name"]).name.lower()
                                 for m in parsed.get("modules", []))
        SUBSYSTEM_LABELS = {
            "dstorage":     "DirectStorage streaming",
            "dstoragecore": "DirectStorage core",
            "d3d12":        "DirectX 12 rendering",
            "d3d11":        "DirectX 11 rendering",
            "dxgi":         "Display / swap chain",
            "lua":          "Lua scripting",
            "wwise":        "Wwise audio",
            "fmod":         "FMOD audio",
            "physx":        "PhysX physics",
            "steam_api":    "Steam API",
            "gameoverlayrenderer": "Steam overlay",
            "npggnt":       "GameGuard anti-cheat",
            "easyanticheat":"EasyAntiCheat",
            "amdxc":        "AMD GPU driver",
            "amdxx":        "AMD GPU driver",
            "nvwgf":        "NVIDIA GPU driver",
            "nvd3d":        "NVIDIA GPU driver",
            "network":      "Game networking",
            "game.dll":     "Game logic",
            "playfab":      "PlayFab online services",
            "partywin":     "Xbox Party SDK",
            "level_generation": "Level generation",
            "crs-client":   "Arrowhead crash reporter",
            "reshade":      "ReShade post-processing",
            "amd_fidelityfx": "AMD FidelityFX / FSR",
            "libxess":      "Intel XeSS upscaler",
        }
        active_subsystems = []
        for kw, label in SUBSYSTEM_LABELS.items():
            if kw in all_mod_names:
                active_subsystems.append(label)

        if active_subsystems:
            self._timeline_add_event(
                self._timeline_container,
                step=2,
                title="Active subsystems at crash time",
                color=BLUE,
                icon="[SUB]",
                details=[f"{len(active_subsystems)} subsystems loaded:"] +
                        [f"  - {s}" for s in active_subsystems[:12]] +
                        ([f"  ... and {len(active_subsystems)-12} more"]
                         if len(active_subsystems) > 12 else []),
                tags=[f"{len(active_subsystems)} subsystems"],
            )

        if is_suicide:
            active_threads = _active_game_threads_at_crash(parsed)
            if active_threads:
                t = active_threads[0]
                doing_title = f"Engine suicide triggered by TID {t['tid']}"
                doing_details = [
                    f"The active game thread was executing in {t['module']} +0x{t['offset']:X}",
                    f"RCX (likely 'this' pointer) = 0x{t.get('rcx', 0):016X}" +
                    ("  <- NULL (destroyed object)" if t.get("rcx", 0) < 0x1000 else ""),
                    "",
                    "The engine detected an internal error while this thread was running",
                    "and called its suicide routine. To get engine logs: right-click the game in Steam > Properties > Launch Options, add --log-to-file, then launch and play until it crashes. The log will be in %APPDATA%\\Arrowhead\\Helldivers 2\\logs",
                ]
                doing_color = ORANGE
            else:
                doing_title = "Engine suicide (no active game thread found)"
                doing_details = ["No active game threads were found at crash time."]
                doing_color = ORANGE
        else:
            if chain:
                addr, mod, off, _ = chain[0] if len(chain[0]) == 4 else (chain[0][0], chain[0][1], chain[0][2], False)
                doing_title = f"Executing code in {mod} +0x{off:X}"
                doing_details = [f"Crash address: 0x{addr:016X}", f"Module: {mod}", f"Offset: +0x{off:X}"]
                doing_color = RED
            else:
                doing_title = "Could not determine what the engine was doing"
                doing_details = ["No call chain data available in this dump."]
                doing_color = TEXT_DIM

        self._timeline_add_event(
            self._timeline_container,
            step=3,
            title=doing_title,
            color=doing_color,
            icon="[RUN]",
            details=doing_details,
            tags=[],
        )

        if decoded_instr:
            instr_title = f"FAULT: {decoded_instr.get('instruction', 'N/A')}"
            instr_details = [decoded_instr.get("explanation", "")]
            if decoded_instr.get("is_suicide"):
                instr_details.append("")
                instr_details.append("This is an ENGINE SUICIDE instruction - the null pointer")
                instr_details.append("access is intentional, not a real bug.")
            instr_color = RED if decoded_instr.get("is_suicide") else YELLOW
            if is_suicide and not decoded_instr.get("is_suicide"):
                instr_color = ORANGE
                instr_details.append("")
                instr_details.append("This instruction is the engine's suicide MECHANISM.")
                instr_details.append("The null deref is intentional - do NOT treat as a bug.")
        else:
            instr_title = "FAULT: Instruction bytes not available"
            instr_details = ["The crash address memory was not captured in this minidump."]
            instr_color = TEXT_DIM

        params = ex.get("params", [])
        if ex.get("code") == "0xC0000005" and len(params) >= 2:
            op = "WRITE" if params[0] == "0x1" else "READ"
            fault_addr = int(params[1], 16) if len(params) >= 2 else 0
            instr_details.append("")
            instr_details.append(f"Exception: {ex.get('code')} (Access Violation)")
            instr_details.append(f"Operation: {op}")
            instr_details.append(f"Fault address: 0x{fault_addr:016X}" +
                                 ("  <- NULL" if fault_addr == 0 else
                                  f"  <- near-null offset +{fault_addr}" if fault_addr < 0x1000 else ""))
        else:
            instr_details.append("")
            instr_details.append(f"Exception: {ex.get('code', 'N/A')}")

        self._timeline_add_event(
            self._timeline_container,
            step=4,
            title=instr_title,
            color=instr_color,
            icon="[!]",
            details=instr_details,
            tags=[ex.get("code", "")],
        )

        if chain:
            chain_details = []
            for i, entry in enumerate(chain[:8]):
                if len(entry) == 4:
                    addr, mod, off, verified = entry
                else:
                    addr, mod, off = entry[0], entry[1], entry[2]
                    verified = None
                badge = " [pdata ok]" if verified is True else (" [heuristic]" if verified is False else "")
                prefix = "CRASH ->" if i == 0 else f"  #{i:02d}"
                chain_details.append(f"{prefix}  0x{addr:016X}  {mod} +0x{off:X}{badge}")
            if len(chain) > 8:
                chain_details.append(f"  ... +{len(chain)-8} more frames")

            unwind = parsed.get("_stack_unwind", {})
            pdata_mods = unwind.get("pdata_modules", 0)
            total_mods = unwind.get("total_modules", 0)
            pdata_c = unwind.get("pdata_confirmed", 0)
            heuristic = unwind.get("heuristic", 0)
            if pdata_mods > 0:
                chain_details.append("")
                chain_details.append(f"Quality: {pdata_c} pdata-confirmed, {heuristic} heuristic, "
                                     f".pdata for {pdata_mods}/{total_mods} modules")
            else:
                chain_details.append("")
                chain_details.append(f"Quality: heuristic only ({heuristic} frames), .pdata not available")

            self._timeline_add_event(
                self._timeline_container,
                step=5,
                title=f"Call chain ({len(chain)} frames)",
                color=BLUE,
                icon="[STK]",
                details=chain_details,
                tags=[f"{len(chain)} frames"],
            )

        regs = ex.get("regs", {})
        if regs:
            null_regs = {k.upper(): v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and v == 0}
            near_nulls = {k.upper(): v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and 0 < v < 0x1000}

            reg_details = []
            if null_regs:
                reg_details.append(f"Null registers ({len(null_regs)}): {', '.join(sorted(null_regs.keys()))}")
            if near_nulls:
                reg_details.append(f"Near-null registers ({len(near_nulls)}): " +
                                   ", ".join(f"{k}=0x{v:X}" for k, v in sorted(near_nulls.items())))

            key_regs = ["rip", "rax", "rcx", "rdx", "rsp"]
            reg_details.append("")
            for name in key_regs:
                val = regs.get(name)
                if val is not None:
                    null_note = "  <- NULL" if val == 0 else ""
                    reg_details.append(f"  {name.upper():4s} = 0x{val:016X}{null_note}")

            reg_color = RED if null_regs else TEXT_DIM
            self._timeline_add_event(
                self._timeline_container,
                step=6,
                title=f"Register state ({len(null_regs)} null, {len(near_nulls)} near-null)",
                color=reg_color,
                icon="[REG]",
                details=reg_details,
                tags=[f"{len(null_regs)} null"],
            )

        env_details = []
        if mods.get("has_mods"):
            env_details.append(f"Mods detected: {len(mods.get('indicators', []))} indicators "
                               f"(confidence: {mods.get('confidence', 'LOW')})")
            for ind in mods.get("indicators", [])[:5]:
                env_details.append(f"  [{ind.get('severity', '?')}] {ind.get('type', '?')}: {ind.get('detail', '')[:60]}")
        else:
            env_details.append("No mods detected - crash is not mod-related.")

        try:
            dv = verify_critical_dlls(parsed)
            m140 = dv.get("msvcp140") or {}
            if m140.get("verdict") != "OK":
                env_details.append(f"MSVCP140: {m140.get('verdict', '?')} (issues: {len(m140.get('issues', []))})")
            for dll_key in ["vcruntime140.dll", "ucrtbase.dll"]:
                r = dv.get("runtime", {}).get(dll_key)
                if r and r.get("verdict") != "OK":
                    env_details.append(f"{dll_key}: {r.get('verdict', '?')}")
            all_ok = all(
                (dv.get("msvcp140") or {}).get("verdict") == "OK"
                and all(
                    (dv.get("runtime", {}).get(k) or {}).get("verdict") == "OK"
                    for k in ["vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "ucrtbase.dll"]
                )
            )
            if all_ok:
                env_details.append("DLL authenticity: all OK")
        except Exception:
            pass

        env_color = YELLOW if mods.get("has_mods") else GREEN
        self._timeline_add_event(
            self._timeline_container,
            step=7,
            title="Environment & mod status",
            color=env_color,
            icon="[ENV]",
            details=env_details,
            tags=[],
        )

        if pattern:
            self._timeline_add_event(
                self._timeline_container,
                step=8,
                title=f"Pattern matched: {pattern.get('name', '?')}",
                color=GREEN,
                icon="[PAT]",
                details=[
                    pattern.get("player_message", ""),
                    "",
                    f"Pattern ID: {pattern.get('id', '?')}",
                    f"Confidence: {pattern.get('confidence', '?')}",
                ],
                tags=[pattern.get("id", ""), pattern.get("confidence", "")],
            )

    def _timeline_verdict_icon(self, verdict: str) -> str:
        icons = {"SUICIDE": "[SUI]", "GPU": "[GPU]", "MOD": "[MOD]",
                 "GAME_BUG": "[BUG]", "INCONCLUSIVE": "[?]"}
        return icons.get(verdict, "[?]")

    def _timeline_add_event(self, parent, step: int, title: str, color: str,
                            icon: str, details: list, tags: list):
        if step > 1:
            arrow_frame = tk.Frame(parent, bg=BG)
            arrow_frame.pack(fill="x", padx=40)
            tk.Label(arrow_frame, text="  |", bg=BG, fg=BORDER,
                     font=(UI_MONO, 12)).pack(anchor="center")
            tk.Label(arrow_frame, text="  v", bg=BG, fg=BORDER,
                     font=(UI_MONO, 10)).pack(anchor="center")

        card = tk.Frame(parent, bg=BG2, highlightbackground=color, highlightthickness=1)
        card.pack(fill="x", pady=2)

        strip = tk.Frame(card, bg=color, width=4)
        strip.pack(side="left", fill="y")

        content = tk.Frame(card, bg=BG2, padx=14, pady=10)
        content.pack(side="left", fill="x", expand=True)

        header = tk.Frame(content, bg=BG2)
        header.pack(fill="x")

        tk.Label(header, text=f"STEP {step}", bg=color, fg="white",
                 font=(UI_FONT, 7, "bold"), padx=6, pady=2).pack(side="left")

        tk.Label(header, text=f" {icon} ", bg=BG3, fg=color,
                 font=(UI_MONO, 8, "bold"), padx=4).pack(side="left", padx=(4, 0))

        tk.Label(header, text=title, bg=BG2, fg=TEXT,
                 font=(UI_FONT, 10, "bold"), anchor="w").pack(side="left", padx=(8, 0))

        for tag in tags:
            if tag:
                tk.Label(header, text=f" {tag} ", bg=BG3, fg=TEXT_DIM,
                         font=(UI_FONT, 7, "bold")).pack(side="right", padx=(2, 0))

        for line in details:
            if not line:
                tk.Label(content, text="", bg=BG2).pack(anchor="w")
            else:
                fg = TEXT
                if line.startswith("  <-") or line.startswith("CRASH"):
                    fg = RED
                elif line.startswith("  #"):
                    fg = BLUE
                elif "NULL" in line or "null" in line:
                    fg = RED
                elif "suicide" in line.lower() or "intentional" in line.lower():
                    fg = ORANGE
                elif line.startswith("Quality:") or line.startswith("Pattern"):
                    fg = TEXT_DIM

                tk.Label(content, text=line, bg=BG2, fg=fg,
                         font=(UI_MONO, 8), anchor="w", wraplength=800,
                         justify="left").pack(anchor="w", fill="x")

    def _build_registers_tab(self):
        scrollable = ScrollableFrame(self._tab_registers, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._registers_inner = scrollable.inner

        tk.Label(self._registers_inner, text="REGISTER ANALYSIS", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 12, "bold")).pack(anchor="w", padx=20, pady=16)

        self._registers_container = tk.Frame(self._registers_inner, bg=BG)
        self._registers_container.pack(fill="x", padx=20, pady=12)

        tk.Label(self._registers_container,
                 text="No dump loaded. Open a .dmp file to see register analysis.",
                 bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10)).pack(pady=40)

    def _display_registers(self, parsed: dict):
        for w in self._registers_container.winfo_children():
            w.destroy()

        ex = parsed.get("exception") or {}
        regs = ex.get("regs", {})
        modules = parsed.get("modules", [])
        params = ex.get("params", [])
        ex_code_str = ex.get("code", "")
        fault_addr = 0
        if ex_code_str == "0xC0000005" and len(params) >= 2:
            try:
                fault_addr = int(params[1], 16)
            except Exception:
                fault_addr = 0

        if not regs:
            tk.Label(self._registers_container, text="No register data available in this dump.",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10)).pack(pady=40)
            return

        null_regs = {k: v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and v == 0}
        near_nulls = {k: v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and 0 < v < 0x1000}
        valid_regs = {k: v for k, v in regs.items() if k != "_xmm" and isinstance(v, int) and v >= 0x1000}

        summary_frame = tk.Frame(self._registers_container, bg=BG2,
                                 highlightbackground=BORDER, highlightthickness=1)
        summary_frame.pack(fill="x", pady=4)

        tk.Label(summary_frame, text="REGISTER SUMMARY", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        summary_row = tk.Frame(summary_frame, bg=BG2, padx=14, pady=8)
        summary_row.pack(fill="x")

        tk.Label(summary_row, text="NULL", bg=RED, fg="white",
                 font=(UI_FONT, 8, "bold"), padx=8, pady=2).pack(side="left")
        tk.Label(summary_row, text=f" {len(null_regs)} registers ", bg=BG2, fg=RED,
                 font=(UI_MONO, 9, "bold")).pack(side="left", padx=(4, 16))

        tk.Label(summary_row, text="NEAR-NULL", bg=YELLOW, fg="#111111",
                 font=(UI_FONT, 8, "bold"), padx=8, pady=2).pack(side="left")
        tk.Label(summary_row, text=f" {len(near_nulls)} registers ", bg=BG2, fg=YELLOW,
                 font=(UI_MONO, 9, "bold")).pack(side="left", padx=(4, 16))

        tk.Label(summary_row, text="VALID", bg=GREEN, fg="#111111",
                 font=(UI_FONT, 8, "bold"), padx=8, pady=2).pack(side="left")
        tk.Label(summary_row, text=f" {len(valid_regs)} registers ", bg=BG2, fg=GREEN,
                 font=(UI_MONO, 9, "bold")).pack(side="left", padx=(4, 16))

        if null_regs:
            tk.Label(summary_row, text=f"  Null: {', '.join(k.upper() for k in sorted(null_regs.keys()))}",
                     bg=BG2, fg=RED, font=(UI_MONO, 8)).pack(side="left", padx=(8, 0))

        conv_frame = tk.Frame(self._registers_container, bg=BG2,
                              highlightbackground=BORDER, highlightthickness=1)
        conv_frame.pack(fill="x", pady=4)

        tk.Label(conv_frame, text="x64 CALLING CONVENTION CONTEXT", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

        conv_info = [
            ("RCX", "1st argument / 'this' pointer (C++ member functions)"),
            ("RDX", "2nd argument / return buffer in some ABIs"),
            ("R8",  "3rd argument"),
            ("R9",  "4th argument"),
            ("RAX", "Return value / volatile scratch"),
            ("R10", "Volatile / used for indirect calls in some codegen"),
            ("R11", "Volatile / used for indirect calls in some codegen"),
            ("RBX", "Callee-saved (preserved across calls)"),
            ("RBP", "Frame pointer (callee-saved)"),
            ("RSI", "Callee-saved (string source in some ABIs)"),
            ("RDI", "Callee-saved (string dest in some ABIs)"),
            ("R12-R15", "Callee-saved (preserved across calls)"),
            ("RSP", "Stack pointer (points to return address + locals)"),
            ("RIP", "Instruction pointer (the faulting instruction)"),
        ]

        for name, desc in conv_info:
            row = tk.Frame(conv_frame, bg=BG2, padx=14)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"  {name:10s}", bg=BG2, fg=BLUE,
                     font=(UI_MONO, 8, "bold")).pack(side="left")
            tk.Label(row, text=desc, bg=BG2, fg=TEXT_DIM,
                     font=(UI_FONT, 8)).pack(side="left", padx=(8, 0))

        tk.Label(self._registers_container, text="REGISTER DETAIL", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=0, pady=(16, 4))

        reg_order = ["rip", "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
                     "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]

        for reg_name in reg_order:
            val = regs.get(reg_name)
            if val is None:
                continue

            if val == 0:
                status = "NULL"
                color = RED
                status_bg = RED
            elif val < 0x1000:
                status = f"NEAR-NULL (+0x{val:X})"
                color = YELLOW
                status_bg = YELLOW
            elif val > 0x00007F0000000000:
                status = "KERNEL/INVALID"
                color = RED
                status_bg = RED
            else:
                status = "VALID"
                color = GREEN
                status_bg = GREEN

            mod_name = None
            mod_offset = 0
            mod_full_path = ""
            for m in modules:
                try:
                    base = int(m["base"], 16)
                    if base <= val < base + m["size"]:
                        mod_name = PureWindowsPath(m["name"]).name
                        mod_offset = val - base
                        mod_full_path = m["name"]
                        break
                except Exception:
                    pass

            interpretation = self._interpret_register(reg_name, val, mod_name,
                                                       mod_offset, fault_addr,
                                                       regs, params, ex_code_str)

            card = tk.Frame(self._registers_container, bg=BG2,
                            highlightbackground=color, highlightthickness=1)
            card.pack(fill="x", pady=2)

            strip = tk.Frame(card, bg=color, width=4)
            strip.pack(side="left", fill="y")

            content = tk.Frame(card, bg=BG2, padx=14, pady=8)
            content.pack(side="left", fill="x", expand=True)

            header = tk.Frame(content, bg=BG2)
            header.pack(fill="x")

            tk.Label(header, text=reg_name.upper(), bg=BG2, fg=TEXT,
                     font=(UI_MONO, 12, "bold")).pack(side="left")

            tk.Label(header, text=f"  0x{val:016X}", bg=BG2, fg=color,
                     font=(UI_MONO, 11, "bold")).pack(side="left", padx=(8, 0))

            tk.Label(header, text=f" {status} ", bg=status_bg,
                     fg="#111111" if status_bg in (GREEN, YELLOW) else "white",
                     font=(UI_FONT, 7, "bold")).pack(side="left", padx=(8, 0))

            if mod_name:
                tk.Label(header, text=f"  -> {mod_name} +0x{mod_offset:X}", bg=BG2, fg=BLUE,
                         font=(UI_MONO, 8, "bold")).pack(side="left", padx=(8, 0))
                tk.Label(content, text=f"  Path: {mod_full_path}", bg=BG2, fg=TEXT_DIM,
                         font=(UI_FONT, 7)).pack(anchor="w", pady=(2, 0))

            if interpretation:
                tk.Label(content, text=interpretation, bg=BG2, fg=TEXT,
                         font=(UI_FONT, 9), wraplength=800, anchor="w", justify="left").pack(anchor="w", pady=(4, 0))

            if val == fault_addr and fault_addr != 0:
                tk.Label(content, text=">>> This register holds the FAULT ADDRESS from the exception parameters <<<",
                         bg=BG2, fg=RED, font=(UI_FONT, 8, "bold")).pack(anchor="w", pady=(4, 0))

            if val == 0 and fault_addr < 0x1000 and reg_name in ("rcx", "rax", "rdx", "rbx"):
                tk.Label(content, text=">>> This null register is likely the base pointer that caused the fault <<<",
                         bg=BG2, fg=RED, font=(UI_FONT, 8, "bold")).pack(anchor="w", pady=(4, 0))

        xmm_regs = regs.get("_xmm", {})
        if xmm_regs:
            tk.Label(self._registers_container, text="SIMD REGISTERS (XMM0-XMM15)", bg=BG, fg=ACCENT,
                     font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=0, pady=(16, 4))

            for i in range(16):
                name = f"xmm{i}"
                vals = xmm_regs.get(name)
                if vals is None:
                    continue
                lo, hi = vals

                hex_str = f"{lo:016X} {hi:016X}"

                import struct as _struct
                try:
                    f0, f1, f2, f3 = _struct.unpack_from("<ffff", _struct.pack("<QQ", lo, hi))
                    float_str = f"  floats: {f0:.4g}, {f1:.4g}, {f2:.4g}, {f3:.4g}"
                except Exception:
                    float_str = ""

                try:
                    d0, d1 = _struct.unpack_from("<dd", _struct.pack("<QQ", lo, hi))
                    double_str = f"  doubles: {d0:.6g}, {d1:.6g}"
                except Exception:
                    double_str = ""

                is_zero = (lo == 0 and hi == 0)
                color = TEXT_DIM if is_zero else PURPLE

                card = tk.Frame(self._registers_container, bg=BG2,
                                highlightbackground=color, highlightthickness=1)
                card.pack(fill="x", pady=1)

                strip = tk.Frame(card, bg=color, width=3)
                strip.pack(side="left", fill="y")

                content = tk.Frame(card, bg=BG2, padx=12, pady=4)
                content.pack(side="left", fill="x", expand=True)

                header = tk.Frame(content, bg=BG2)
                header.pack(fill="x")

                tk.Label(header, text=f"XMM{i:2d}", bg=BG2, fg=PURPLE,
                         font=(UI_MONO, 9, "bold")).pack(side="left")
                tk.Label(header, text=f"  {hex_str}", bg=BG2, fg=color,
                         font=(UI_MONO, 8)).pack(side="left", padx=(4, 0))
                if is_zero:
                    tk.Label(header, text=" (zero)", bg=BG2, fg=TEXT_DIM,
                             font=(UI_FONT, 7)).pack(side="left", padx=(4, 0))

                if not is_zero and (float_str or double_str):
                    detail = tk.Frame(content, bg=BG2)
                    detail.pack(fill="x", pady=(2, 0))
                    if float_str:
                        tk.Label(detail, text=float_str, bg=BG2, fg=TEXT_DIM,
                                 font=(UI_MONO, 7)).pack(anchor="w")
                    if double_str:
                        tk.Label(detail, text=double_str, bg=BG2, fg=TEXT_DIM,
                                 font=(UI_MONO, 7)).pack(anchor="w")

        if params:
            param_frame = tk.Frame(self._registers_container, bg=BG2,
                                   highlightbackground=BORDER, highlightthickness=1)
            param_frame.pack(fill="x", pady=4)

            tk.Label(param_frame, text="EXCEPTION PARAMETERS", bg=BG2, fg=ACCENT,
                     font=(UI_FONT, 8, "bold"), padx=14, pady=10).pack(anchor="w")

            if ex_code_str == "0xC0000005" and len(params) >= 2:
                op = "WRITE" if params[0] == "0x1" else "READ"
                fa = int(params[1], 16)
                tk.Label(param_frame, text=f"  Operation:  {op}", bg=BG2, fg=TEXT,
                         font=(UI_MONO, 9)).pack(anchor="w", padx=14)
                tk.Label(param_frame, text=f"  Fault addr: 0x{fa:016X}", bg=BG2, fg=RED,
                         font=(UI_MONO, 9, "bold")).pack(anchor="w", padx=14)

                if fa == 0:
                    tk.Label(param_frame, text="  Interpretation: NULL pointer dereference (base pointer was 0)",
                             bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w", padx=14, pady=(4, 0))
                elif fa < 0x1000:
                    tk.Label(param_frame, text=f"  Interpretation: Near-null access (struct member at offset +0x{fa:X} via null base pointer)",
                             bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w", padx=14, pady=(4, 0))
                elif fa > 0x00007F0000000000:
                    tk.Label(param_frame, text="  Interpretation: Kernel/guard address (stack overflow or corrupted pointer)",
                             bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w", padx=14, pady=(4, 0))
                else:
                    fa_mod = None
                    for m in modules:
                        try:
                            base = int(m["base"], 16)
                            if base <= fa < base + m["size"]:
                                fa_mod = PureWindowsPath(m["name"]).name
                                fa_off = fa - base
                                break
                        except Exception:
                            pass
                    if fa_mod:
                        tk.Label(param_frame, text=f"  Interpretation: Access into {fa_mod} +0x{fa_off:X} (possibly use-after-free or stale pointer)",
                                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w", padx=14, pady=(4, 0))
                    else:
                        tk.Label(param_frame, text="  Interpretation: Invalid heap address (possibly freed memory or corrupted pointer)",
                                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(anchor="w", padx=14, pady=(4, 0))
            else:
                for i, p in enumerate(params[:4]):
                    tk.Label(param_frame, text=f"  Param[{i}]: {p}", bg=BG2, fg=TEXT_DIM,
                             font=(UI_MONO, 9)).pack(anchor="w", padx=14)

    def _interpret_register(self, name: str, val: int, mod_name: str, mod_offset: int,
                            fault_addr: int, regs: dict, params: list, ex_code: str) -> str:
        name_l = name.lower()

        RESOLUTIONS = {
            1920: "1920 (1080p width)",
            1080: "1080 (1080p height)",
            2560: "2560 (1440p width)",
            1440: "1440 (1440p height / UW width)",
            3840: "3840 (4K width)",
            2160: "2160 (4K height)",
            1280: "1280 (720p width)",
            720:  "720 (720p height)",
            1366: "1366 (laptop width)",
            768:  "768 (laptop height)",
            1600: "1600 (900p width)",
            900:  "900 (900p height)",
            3440: "3440 (ultrawide width)",
            1680: "1680 (1050p width)",
            1050: "1050 (1050p height)",
            5120: "5120 (5K width)",
            2880: "2880 (5K height)",
        }
        lo32 = val & 0xFFFFFFFF
        lo16 = val & 0xFFFF
        hi16 = (val >> 16) & 0xFFFF
        res_note = ""
        if lo32 in RESOLUTIONS and val < 0x10000:
            res_note = f"  [Screen resolution: {RESOLUTIONS[lo32]}]"
        elif lo16 in RESOLUTIONS and hi16 in RESOLUTIONS:
            res_note = f"  [Packed resolution: {lo16}x{hi16}]"
        elif lo16 in RESOLUTIONS and val < 0x100000000:
            res_note = f"  [Low 16 bits = {RESOLUTIONS[lo16]}]"

        def note(s):
            return s + res_note if res_note else s

        if name_l == "rip":
            if mod_name:
                return note(f"Instruction pointer - executing code at {mod_name} +0x{mod_offset:X}. This is the instruction that caused the fault.")
            return note("Instruction pointer - the faulting instruction address.")

        if name_l == "rsp":
            return note("Stack pointer - points to the current stack frame. The return address is at [RSP].")

        if name_l == "rbp":
            if val == 0:
                return note("Frame pointer is NULL - function may have no frame pointer (optimized build) or stack corruption.")
            return note("Frame pointer - base of the current stack frame. Local variables are at negative offsets from RBP.")

        if name_l == "rcx":
            if val == 0:
                return note("'this' pointer is NULL - a virtual method was called on a null or destroyed C++ object. This is the most common cause of null-deref crashes in game engines.")
            elif val < 0x1000:
                return note(f"'this' pointer is near-null (0x{val:X}) - possibly a corrupted or partially-initialized object pointer.")
            if mod_name:
                return note(f"1st argument / 'this' pointer - points into {mod_name} +0x{mod_offset:X}. This is the object the current function is operating on.")
            return note("1st argument / 'this' pointer - points to valid heap memory (likely a game object).")

        if name_l == "rdx":
            if val == 0:
                return note("2nd argument is NULL - may be an optional parameter that wasn't checked, or a missing output buffer.")
            if mod_name:
                return note(f"2nd argument - points into {mod_name} +0x{mod_offset:X}.")
            return note("2nd argument - holds a valid pointer or integer value.")

        if name_l in ("r8", "r9"):
            idx = 3 if name_l == "r8" else 4
            if val == 0:
                return note(f"{idx}th argument is NULL - possibly an optional parameter or uninitialized argument.")
            if val < 0x1000:
                return note(f"{idx}th argument is small value 0x{val:X} - likely a count, size, flag, or enum.")
            if mod_name:
                return note(f"{idx}th argument - points into {mod_name} +0x{mod_offset:X}.")
            return note(f"{idx}th argument - holds a valid value (pointer or integer).")

        if name_l == "rax":
            if val == 0:
                return note("Return value / volatile - NULL. Possibly a function that just returned null/failure, or this register is simply scratch.")
            if val == fault_addr and fault_addr != 0:
                return note("Return value / volatile - holds the FAULT ADDRESS. A function likely returned a bad pointer and it was immediately dereferenced.")
            if mod_name:
                return note(f"Return value / volatile - points into {mod_name} +0x{mod_offset:X}.")
            return note("Return value / volatile scratch register.")

        if name_l == "rbx":
            if val == 0:
                return note("Callee-saved register is NULL - was zeroed by a function that previously used it. Check the call chain for who set it.")
            if mod_name:
                return note(f"Callee-saved - points into {mod_name} +0x{mod_offset:X}. Often holds a 'this' pointer or context that persists across calls.")
            return note("Callee-saved register - holds a value from a calling function.")

        if name_l == "rsi":
            if val == 0:
                return note("Callee-saved (source index) is NULL - was cleared by a calling function.")
            if mod_name:
                return note(f"Callee-saved - points into {mod_name} +0x{mod_offset:X}.")
            return note("Callee-saved register - string source or general-purpose preserved value.")

        if name_l == "rdi":
            if val == 0:
                return note("Callee-saved (destination index) is NULL - was cleared by a calling function.")
            if mod_name:
                return note(f"Callee-saved - points into {mod_name} +0x{mod_offset:X}.")
            return note("Callee-saved register - string destination or general-purpose preserved value.")

        if name_l in ("r10", "r11"):
            if val == 0:
                return note(f"Volatile register {name.upper()} is NULL - scratch register, not significant unless used as an argument.")
            if mod_name:
                return note(f"Volatile - points into {mod_name} +0x{mod_offset:X}. Used for indirect calls or scratch.")
            return note(f"Volatile scratch register - holds value 0x{val:X}.")

        if name_l in ("r12", "r13", "r14", "r15"):
            if val == 0:
                return note(f"Callee-saved {name.upper()} is NULL - was zeroed by a calling function. These are often used for 'this' pointers or loop variables that persist across calls.")
            if mod_name:
                return note(f"Callee-saved {name.upper()} - points into {mod_name} +0x{mod_offset:X}.")
            return note(f"Callee-saved {name.upper()} - preserved value from calling function.")

        return ""

    def _build_evidence_tab(self):
        scrollable = ScrollableFrame(self._tab_evidence, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._evidence_inner = scrollable.inner

        self._evidence_groups = {}

        self._call_chain = CallChainWidget(self._evidence_inner, bg=BG)
        self._call_chain.pack(fill="x", padx=20, pady=(8, 12))

    def _build_threads_tab(self):
        scrollable = ScrollableFrame(self._tab_threads, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._threads_inner = scrollable.inner
        self._thread_groups = {}

    def _build_modules_tab(self):
        scrollable = ScrollableFrame(self._tab_modules, bg=BG)
        scrollable.pack(fill="both", expand=True)
        self._modules_inner = scrollable.inner

    def _build_gpu_tab(self):
        self._gpu_placeholder = tk.Label(self._tab_gpu,
            text="No GPU log loaded. Use 'Open GPU Log' to load a DRED .txt file.",
            bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10))
        self._gpu_placeholder.pack(expand=True)


    def _show_drop_zone(self):
        self._drop_zone.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _hide_drop_zone(self):
        self._drop_zone.place_forget()

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Select minidump file",
            filetypes=[("Minidump files", "*.dmp *.mdmp"), ("All files", "*.*")]
        )
        if not path:
            return
        self._load_path(path)

    def _open_dred_file(self):
        path = filedialog.askopenfilename(
            title="Select DRED GPU log file",
            filetypes=[("DRED log files", "*_dred.txt *.dred.txt"), ("All files", "*.txt")]
        )
        if not path:
            return
        self._load_dred(path)

    def _load_path(self, path: str):
        self._load_generation += 1
        my_generation = self._load_generation

        self._hide_drop_zone()
        self._open_btn.config(state="disabled")
        self._status(f"Parsing {Path(path).name} …", busy=True)

        def _work():
            try:
                parsed = parse_minidump(path)
                rootcause = assess_root_cause(parsed)

                decoded_instr = None
                try:
                    ex = parsed.get("exception", {})
                    if ex:
                        ca = int(ex.get("address", "0"), 16)
                        imem = read_virtual_memory(parsed, ca, 16)
                        if imem:
                            decoded_instr = decode_crash_instruction(imem, ca)
                except Exception:
                    pass

                mods = detect_mods(parsed)
                pattern = _match_patterns(parsed, decoded_instr, mods, rootcause)
                all_patterns = _match_all_patterns(parsed, decoded_instr, mods, rootcause)

                verdict_info = compute_verdict(parsed, rootcause, mods, pattern,
                                               all_patterns, decoded_instr)

                def _maybe_display():
                    if self._load_generation == my_generation:
                        self._display_results(parsed, rootcause, mods, pattern,
                                              all_patterns, verdict_info, decoded_instr)

                self.after(0, _maybe_display)
            except Exception as e:
                def _maybe_show_error():
                    if self._load_generation == my_generation:
                        self._status(f"Parse error: {e}", busy=False)
                        self._open_btn.config(state="normal")
                self.after(0, _maybe_show_error)

        threading.Thread(target=_work, daemon=True).start()

    def _load_dred(self, path: str):
        self._status(f"Parsing DRED log {Path(path).name} …", busy=True)
        try:
            parsed_dred = parse_dred_log(path)
            verdict = assess_dred(parsed_dred)
            self._display_dred(parsed_dred, verdict)
            self._status(f"DRED parsed - {verdict.get('reason_name', 'unknown')}", busy=False)
            self._nb.select(4)
        except Exception as e:
            self._status(f"DRED parse error: {e}", busy=False)


    def _display_results(self, parsed, rootcause, mods, pattern, all_patterns,
                         verdict_info, decoded_instr):
        self._parsed = parsed
        self._verdict_info = verdict_info

        self._verdict_banner.update_verdict(verdict_info)

        self._action_panel.update_actions(verdict_info["actions"])

        ex = parsed.get("exception") or {}
        is_suicide = verdict_info["verdict"] == "SUICIDE"

        self._crash_summary.update_summary(parsed, verdict_info)

        if decoded_instr:
            self._instr_text.configure(text=decoded_instr.get("instruction", "N/A"),
                                       fg=RED if decoded_instr.get("is_suicide") else TEXT)
            self._instr_explanation.configure(text=decoded_instr.get("explanation", ""))
        else:
            self._instr_text.configure(text="Instruction bytes not available in this dump", fg=TEXT_DIM)
            self._instr_explanation.configure(text="The crash address memory was not captured in the minidump.")

        self._mod_banner.update_status(mods)

        self._display_dll_status_row(parsed)

        if is_suicide:
            active_threads = _active_game_threads_at_crash(parsed)
            if active_threads:
                t = active_threads[0]
                engine_text = (f"The engine committed suicide while TID {t['tid']} was executing "
                               f"in {t['module']} +0x{t['offset']:X}. "
                               f"This thread is the likely trigger - check the .log file for the "
                               f"engine's actual error message.")
            else:
                engine_text = ("The engine committed suicide. No active game threads were found at "
                               "crash time. Check the .log file for the engine's error message.")
        else:
            chain = parsed.get("_stack_chain_extended", [])
            if chain:
                addr, mod, off, _ = chain[0] if len(chain[0]) == 4 else (chain[0][0], chain[0][1], chain[0][2], False)
                engine_text = f"Executing code in {mod} +0x{off:X} when the crash occurred."
            else:
                engine_text = "Could not determine what the engine was doing at crash time."
        self._engine_doing.configure(text=engine_text)

        if is_suicide and active_threads:
            self._active_thread_frame.pack(fill="x", padx=20, pady=4, after=self._engine_doing.master)
            lines = []
            for t in active_threads[:3]:
                rcx_note = "  <- RCX null (null object)" if t.get("rcx", 0) < 0x1000 else ""
                lines.append(f"TID {t['tid']:6d}  {t['module']} +0x{t['offset']:X}{rcx_note}")
            self._active_thread_text.configure(text="\n".join(lines))
        else:
            self._active_thread_frame.pack_forget()

        self._display_chain_summary(parsed)

        self._display_possibilities(parsed)

        self._display_timeline(parsed, rootcause, mods, pattern, all_patterns,
                               verdict_info, decoded_instr)
        self._display_evidence(rootcause, parsed, mods, pattern, all_patterns)
        self._display_registers(parsed)
        self._display_threads(parsed)
        self._display_modules(parsed, mods, verdict_info)

        ex_code = ex.get("code", "none")
        nmod = len(parsed.get("modules", []))
        self._open_btn.config(state="normal")
        self._status(f"Parsed - {nmod} modules, exception {ex_code} - verdict: {verdict_info['verdict']}", busy=False)

        self._rebind_all_scrollable()

        self._nb.select(0)

    def _display_dll_status_row(self, parsed: dict):
        for w in self._dll_status_frame.winfo_children():
            w.destroy()
        try:
            dv = verify_critical_dlls(parsed)
        except Exception:
            dv = {}

        row = tk.Frame(self._dll_status_frame, bg=BG2)
        row.pack(fill="x")

        m140 = dv.get("msvcp140") or {}
        vc_verdict = m140.get("verdict", "N/A")
        vc_color = {"OK": GREEN, "SUSPICIOUS": YELLOW, "LIKELY_TAMPERED": RED,
                     "NOT_FOUND": TEXT_DIM}.get(vc_verdict, TEXT_DIM)
        tk.Label(row, text="MSVCP140", bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")
        tk.Label(row, text=f" {vc_verdict} ", bg=vc_color, fg="#111111" if vc_color == GREEN else "white",
                 font=(UI_FONT, 8, "bold")).pack(side="left", padx=(4, 16))

        for dll_key in ["vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "ucrtbase.dll"]:
            r = dv.get("runtime", {}).get(dll_key)
            if r:
                v = r.get("verdict", "N/A")
                c = {"OK": GREEN, "SUSPICIOUS": YELLOW, "LIKELY_TAMPERED": RED,
                     "NOT_FOUND": TEXT_DIM}.get(v, TEXT_DIM)
                short = dll_key.replace(".dll", "").replace("vcruntime", "vcrun")
                tk.Label(row, text=short, bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")
                tk.Label(row, text=f" {v} ", bg=c, fg="#111111" if c == GREEN else "white",
                         font=(UI_FONT, 8, "bold")).pack(side="left", padx=(4, 16))
            else:
                short = dll_key.replace(".dll", "").replace("vcruntime", "vcrun")
                tk.Label(row, text=short, bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")
                tk.Label(row, text=" N/A ", bg=TEXT_DIM, fg="white",
                         font=(UI_FONT, 8, "bold")).pack(side="left", padx=(4, 16))

    def _display_chain_summary(self, parsed: dict):
        for w in self._chain_summary_frame.winfo_children():
            w.destroy()

        chain = parsed.get("_stack_chain_extended", [])
        unwind = parsed.get("_stack_unwind", {})

        if not chain:
            tk.Label(self._chain_summary_frame, text="No call chain data available",
                     bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 9)).pack(anchor="w")
            self._chain_quality_label.configure(text="")
            return

        for i, entry in enumerate(chain[:5]):
            if len(entry) == 4:
                addr, mod, off, verified = entry
            else:
                addr, mod, off = entry[0], entry[1], entry[2]
                verified = None

            is_crash = (i == 0)
            if is_crash:
                color = RED
                prefix = "CRASH ->"
            elif mod.lower().endswith(".exe"):
                color = ORANGE
                prefix = f"  <- #{i:02d}"
            else:
                color = BLUE
                prefix = f"  <- #{i:02d}"

            badge = ""
            if verified is True:
                badge = " [pdata ok]"
            elif verified is False:
                badge = " [heuristic]"

            row = tk.Frame(self._chain_summary_frame, bg=BG2)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=prefix, bg=BG2, fg=color,
                     font=(UI_MONO, 8, "bold")).pack(side="left")
            tk.Label(row, text=f"0x{addr:016X}", bg=BG2, fg=TEXT_DIM,
                     font=(UI_MONO, 8)).pack(side="left", padx=(6, 0))
            tk.Label(row, text=f"{mod} +0x{off:X}{badge}", bg=BG2, fg=color,
                     font=(UI_MONO, 8, "bold")).pack(side="left", padx=(6, 0))

        pdata_c = unwind.get("pdata_confirmed", 0)
        heuristic = unwind.get("heuristic", 0)
        pdata_mods = unwind.get("pdata_modules", 0)
        total_mods = unwind.get("total_modules", 0)
        if len(chain) > 5:
            extra = f"  (+{len(chain)-5} more frames - see Evidence tab)"
        else:
            extra = ""
        if pdata_mods > 0:
            quality = f".pdata verified: {pdata_c} confirmed, {heuristic} heuristic | .pdata for {pdata_mods}/{total_mods} modules{extra}"
        else:
            quality = f"Heuristic only ({heuristic} frames) - .pdata not available{extra}"
        self._chain_quality_label.configure(text=quality)

    def _display_possibilities(self, parsed: dict):
        for w in self._possibilities_frame.winfo_children():
            w.destroy()

        hints = quick_patterns(parsed)

        if not hints:
            tk.Label(self._possibilities_frame,
                     text="No additional patterns detected.",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 9),
                     anchor="w").pack(anchor="w")
            return

        for label, detail, colour, could_be in hints:
            card = tk.Frame(self._possibilities_frame, bg=BG2,
                            highlightbackground=colour, highlightthickness=0)
            card.pack(fill="x", pady=3)

            strip = tk.Frame(card, bg=colour, width=3)
            strip.pack(side="left", fill="y")

            content = tk.Frame(card, bg=BG2, padx=10, pady=8)
            content.pack(side="left", fill="x", expand=True)

            tk.Label(content, text=label, bg=BG2, fg=colour,
                     font=(UI_FONT, 9, "bold"), anchor="w",
                     wraplength=750).pack(anchor="w")

            tk.Label(content, text=detail, bg=BG2, fg=TEXT_DIM,
                     font=(UI_MONO, 8), anchor="w",
                     wraplength=750).pack(anchor="w", pady=(2, 0))

            tk.Label(content, text=could_be, bg=BG2, fg=TEXT,
                     font=(UI_FONT, 9), anchor="w", wraplength=750,
                     justify="left").pack(anchor="w", pady=(4, 0))

    def _rebind_all_scrollable(self):
        def find_and_rebind(parent):
            for child in parent.winfo_children():
                if isinstance(child, ScrollableFrame):
                    child.rebind_enter()
                find_and_rebind(child)
        find_and_rebind(self)

    def _display_evidence(self, rootcause, parsed, mods, pattern, all_patterns):
        for w in self._evidence_inner.winfo_children():
            if w is not self._call_chain:
                w.destroy()
        self._evidence_groups.clear()

        chain = [(a, m, o) for a, m, o, _ in parsed.get("_stack_chain_extended", [])]
        unwind_info = parsed.get("_stack_unwind", {})
        extended = parsed.get("_stack_chain_extended", [])
        self._call_chain.update_chain(chain, unwind_info, extended)

        groups = {
            "crash_instruction": ("CRASH INSTRUCTION", ACCENT, []),
            "call_chain":        ("CALL CHAIN & STACK", ACCENT, []),
            "active_threads":    ("ACTIVE GAME THREADS (likely trigger for suicides)", ORANGE, []),
            "registers":         ("REGISTER STATE", BLUE, []),
            "suicide":           ("ENGINE SUICIDE ANALYSIS", ORANGE, []),
            "mod_indicators":    ("MOD DETECTION", YELLOW, []),
            "dll_verify":        ("DLL AUTHENTICITY", PURPLE, []),
            "other":             ("OTHER FINDINGS", TEXT_DIM, []),
        }

        for finding in rootcause:
            title = finding.get("title", "").lower()
            detail = finding.get("detail", "").lower()
            if "suicide" in title or "suicide" in detail:
                cat = "suicide"
            elif "faulting instruction" in title or "crash instruction" in title:
                cat = "crash_instruction"
            elif "call chain" in title or "stack" in title:
                cat = "call_chain"
            elif "active game thread" in title or "active" in title:
                cat = "active_threads"
            elif "register" in title or "null" in title:
                cat = "registers"
            elif "mod" in title:
                cat = "mod_indicators"
            elif "dll" in title or "tampered" in title:
                cat = "dll_verify"
            else:
                cat = "other"
            groups[cat][2].append(finding)

        for ind in mods.get("indicators", []):
            finding = {
                "conf": ind.get("severity", "LOW"),
                "title": f"{ind.get('type', 'unknown')}: {ind.get('path', '')}",
                "detail": ind.get("detail", ""),
                "link": None,
            }
            groups["mod_indicators"][2].append(finding)

        for key, (label, color, findings) in groups.items():
            if not findings:
                continue
            group = EvidenceGroup(self._evidence_inner, label, color, bg=BG)
            group.pack(fill="x", padx=20, pady=4)
            for f in findings:
                group.add_finding(f, self)
            group.set_count(len(findings))

        verdict = self._verdict_info["verdict"] if self._verdict_info else "INCONCLUSIVE"
        if verdict == "SUICIDE":
            expand_key = "suicide"
        elif verdict == "GPU":
            expand_key = "crash_instruction"
        elif verdict == "MOD":
            expand_key = "mod_indicators"
        else:
            expand_key = "crash_instruction"

        for key, (label, color, findings) in groups.items():
            if not findings:
                continue
            if key != expand_key:
                for w in self._evidence_inner.winfo_children():
                    if isinstance(w, EvidenceGroup) and w._title == label:
                        w.toggle()
                        break

    def _display_threads(self, parsed):
        for w in self._threads_inner.winfo_children():
            w.destroy()
        self._thread_groups.clear()

        threads = analyse_threads(parsed)

        if not threads:
            tk.Label(self._threads_inner, text="No thread data available",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10)).pack(pady=40)
            return

        purpose_groups = {}
        crash_threads = []

        for t in threads:
            if t.get("is_crashed"):
                crash_threads.append(t)
                continue
            purpose = t.get("purpose") or "Other"
            purpose_color = t.get("purpose_colour_key") or "system"
            if purpose not in purpose_groups:
                color_map = {
                    "audio": GREEN, "gpu": PURPLE, "network": BLUE,
                    "game": YELLOW, "system": TEXT_DIM, "storage": ORANGE,
                }
                purpose_groups[purpose] = {"color": color_map.get(purpose_color, TEXT_DIM),
                                           "threads": []}
            purpose_groups[purpose]["threads"].append(t)

        if crash_threads:
            tk.Label(self._threads_inner, text="CRASH THREAD", bg=BG, fg=RED,
                     font=(UI_FONT, 9, "bold")).pack(anchor="w", padx=20, pady=(12, 4))
            for t in crash_threads:
                card = EvidenceCard(self._threads_inner, {
                    "conf": "HIGH",
                    "title": f"TID {t['tid']} - {t.get('doing', 'crashed')}",
                    "detail": (f"Module: {t.get('module', '?')} {t.get('offset', '')}\n"
                               f"RIP: {t.get('rip', '?')}\n"
                               f"State: {t.get('state', '?')}"),
                    "link": None,
                }, self, bg=BG2)
                card.pack(fill="x", padx=20, pady=2)

        tk.Label(self._threads_inner, text="ALL THREADS (grouped by purpose)", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        for purpose, info in sorted(purpose_groups.items(), key=lambda x: -len(x[1]["threads"])):
            group = ThreadGroupWidget(self._threads_inner, purpose, info["color"], bg=BG)
            group.pack(fill="x", padx=20, pady=2)
            for t in info["threads"]:
                group.add_thread(t)
            group.set_count(len(info["threads"]))

    def _display_modules(self, parsed, mods, verdict_info):
        for w in self._modules_inner.winfo_children():
            w.destroy()

        mod_banner = ModDetectionBanner(self._modules_inner, bg=BG2)
        mod_banner.update_status(mods)
        mod_banner.pack(fill="x", padx=20, pady=12)

        tk.Label(self._modules_inner, text="LOADED MODULES", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(12, 4))

        modules = parsed.get("modules", [])
        crash_mod = verdict_info.get("crash_module", "").lower()

        header = tk.Frame(self._modules_inner, bg=BG2, padx=8, pady=4)
        header.pack(fill="x", padx=20)
        tk.Label(header, text="Module", bg=BG2, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold"), width=40, anchor="w").pack(side="left")
        tk.Label(header, text="Base", bg=BG2, fg=TEXT_DIM,
                 font=(UI_MONO, 8, "bold"), width=20, anchor="w").pack(side="left")
        tk.Label(header, text="Size", bg=BG2, fg=TEXT_DIM,
                 font=(UI_MONO, 8, "bold"), width=12, anchor="w").pack(side="left")
        tk.Label(header, text="Path", bg=BG2, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold"), anchor="w").pack(side="left")

        sorted_mods = sorted(modules, key=lambda m: (
            0 if PureWindowsPath(m["name"]).name.lower() == crash_mod else 1,
            PureWindowsPath(m["name"]).name.lower()
        ))

        for m in sorted_mods[:100]:
            name = PureWindowsPath(m["name"]).name
            is_crash = name.lower() == crash_mod
            bg_color = BG3 if is_crash else BG2
            border_color = RED if is_crash else BORDER

            row = tk.Frame(self._modules_inner, bg=bg_color, padx=8, pady=3,
                           highlightbackground=border_color,
                           highlightthickness=1 if is_crash else 0)
            row.pack(fill="x", padx=20, pady=1)

            tk.Label(row, text=name, bg=bg_color,
                     fg=RED if is_crash else TEXT,
                     font=(UI_MONO, 8, "bold" if is_crash else "normal"),
                     width=40, anchor="w").pack(side="left")
            tk.Label(row, text=m["base"], bg=bg_color, fg=TEXT_DIM,
                     font=(UI_MONO, 8), width=20, anchor="w").pack(side="left")
            tk.Label(row, text=f"{m['size']:,}", bg=bg_color, fg=TEXT_DIM,
                     font=(UI_MONO, 8), width=12, anchor="w").pack(side="left")
            tk.Label(row, text=m["name"], bg=bg_color, fg=TEXT_DIM,
                     font=(UI_FONT, 7), anchor="w").pack(side="left")

        if len(modules) > 100:
            tk.Label(self._modules_inner, text=f"... and {len(modules)-100} more modules",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(pady=8)

        tk.Label(self._modules_inner, text="DLL AUTHENTICITY VERIFICATION", bg=BG, fg=ACCENT,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(20, 4))

        try:
            dv = verify_critical_dlls(parsed)
        except Exception:
            dv = {}

        summary_row = tk.Frame(self._modules_inner, bg=BG2, padx=12, pady=8)
        summary_row.pack(fill="x", padx=20, pady=2)

        m140 = dv.get("msvcp140") or {}
        vc_color = {"OK": GREEN, "SUSPICIOUS": YELLOW, "LIKELY_TAMPERED": RED,
                     "NOT_FOUND": TEXT_DIM}.get(m140.get("verdict", "NOT_FOUND"), TEXT_DIM)
        tk.Label(summary_row, text=f"MSVCP140: {m140.get('verdict', 'N/A')}",
                 bg=BG2, fg=vc_color, font=(UI_MONO, 8, "bold")).pack(side="left", padx=(0, 16))

        for dll_key in ["vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "ucrtbase.dll"]:
            r = dv.get("runtime", {}).get(dll_key)
            if r:
                v = r.get("verdict", "N/A")
                c = {"OK": GREEN, "SUSPICIOUS": YELLOW, "LIKELY_TAMPERED": RED,
                     "NOT_FOUND": TEXT_DIM}.get(v, TEXT_DIM)
                short = dll_key.replace(".dll", "").replace("vcruntime", "vcrun")
                tk.Label(summary_row, text=f"{short}: {v}",
                         bg=BG2, fg=c, font=(UI_MONO, 8)).pack(side="left", padx=(0, 16))

    def _display_dred(self, parsed_dred, verdict):
        for w in self._tab_gpu.winfo_children():
            w.destroy()

        scrollable = ScrollableFrame(self._tab_gpu, bg=BG)
        scrollable.pack(fill="both", expand=True)
        inner = scrollable.inner

        tk.Label(inner, text="GPU DEVICE REMOVAL", bg=BG, fg=PURPLE,
                 font=(UI_FONT, 10, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        tk.Label(inner, text=f"{verdict.get('reason_name', 'Unknown')} ({verdict.get('reason_code', '?')})",
                 bg=BG, fg=TEXT, font=(UI_FONT, 12, "bold")).pack(anchor="w", padx=20)

        desc = verdict.get("reason_desc", "")
        if desc:
            tk.Label(inner, text=desc, bg=BG, fg=TEXT_DIM, font=(UI_FONT, 9),
                     wraplength=800, anchor="w", justify="left").pack(anchor="w", padx=20, pady=(8, 0))

        cs = verdict.get("culprit_summary", "")
        if cs:
            tk.Label(inner, text="ANALYSIS", bg=BG, fg=ACCENT,
                     font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
            tk.Label(inner, text=cs, bg=BG, fg=TEXT, font=(UI_FONT, 9),
                     wraplength=800, anchor="w", justify="left").pack(anchor="w", padx=20)

        dred_errors = parsed_dred.get("dred_api_errors", [])
        if dred_errors:
            tk.Label(inner, text="DRED API STATUS", bg=BG, fg=YELLOW,
                     font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
            for e in dred_errors:
                tk.Label(inner, text=f"  Failed to get {e['what']}: {e['code']}",
                         bg=BG, fg=TEXT_DIM, font=(UI_MONO, 8)).pack(anchor="w", padx=20)

        fix = verdict.get("reason_fix", "")
        if fix:
            tk.Label(inner, text="HOW TO FIX", bg=BG, fg=GREEN,
                     font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
            tk.Label(inner, text=fix, bg=BG, fg=TEXT, font=(UI_FONT, 9),
                     wraplength=800, anchor="w", justify="left").pack(anchor="w", padx=20)


    def execute_action(self, command: str):
        if command == "open_log":
            self._open_log_file()
        elif command == "export":
            self._export_report()
        elif command == "goto_threads":
            self._nb.select(2)
        elif command == "goto_rootcause":
            self._nb.select(1)
        elif command == "goto_mods":
            self._nb.select(3)
        elif command == "open_dred":
            self._open_dred_file()
        elif command == "gpu_guide":
            messagebox.showinfo("GPU Troubleshooting",
                "1. Update GPU drivers (use DDU for clean install)\n"
                "2. Check GPU temperatures (HWiNFO64, GPU-Z)\n"
                "3. Revert any GPU overclock\n"
                "4. Reseat GPU and check power connectors\n"
                "5. Run FurMark stress test to check hardware stability")
        elif command == "mod_guide":
            messagebox.showinfo("Mod Troubleshooting",
                "1. Remove proxy DLLs from the game folder\n"
                "2. Remove mod manager hooks\n"
                "3. Verify game files through Steam\n"
                "4. Retest without any mods installed")

    def _open_log_file(self):
        initial_dir = None
        initial_file = None
        if self._parsed and self._parsed.get("_raw_path"):
            dmp_path = Path(self._parsed["_raw_path"])
            initial_dir = str(dmp_path.parent)
            for candidate in dmp_path.parent.glob("*.log"):
                initial_file = str(candidate)
                break

        path = filedialog.askopenfilename(
            title="Select engine log file",
            initialdir=initial_dir,
            initialfile=Path(initial_file).name if initial_file else None,
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            win = tk.Toplevel(self)
            win.title(f"Engine Log - {Path(path).name}")
            win.geometry("900x600")
            win.configure(bg=BG)

            text = scrolledtext.ScrolledText(win, bg=BG2, fg=TEXT, font=(UI_MONO, 9),
                                             insertbackground=TEXT, wrap="word", relief="flat")
            text.pack(fill="both", expand=True)
            text.insert("1.0", content)
            text.configure(state="disabled")

            text.see("end")

        except Exception as e:
            messagebox.showerror("Error", f"Could not read log file: {e}")

    def _export_report(self):
        if not self._parsed or not self._verdict_info:
            messagebox.showwarning("No Data", "No analysis to export. Load a dump file first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export report",
            defaultextension=".txt",
            filetypes=[("Text report", "*.txt"), ("HTML", "*.html"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            report = self._generate_report_text()
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            messagebox.showinfo("Exported", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export: {e}")

    def _generate_report_text(self) -> str:
        v = self._verdict_info
        p = self._parsed
        ex = p.get("exception", {}) or {}

        lines = []
        lines.append("=" * 70)
        lines.append("STINGRAY CRASH ANALYZER - CRASH REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"VERDICT: {v['verdict']} (confidence: {v['confidence']})")
        lines.append(f"  {v['title']}")
        lines.append(f"  {v['explanation']}")
        lines.append(f"  Crash signature: {v['signature']}")
        lines.append("")
        lines.append("CRASH SUMMARY")
        lines.append(f"  Exception code:   {ex.get('code', 'N/A')}")
        lines.append(f"  Crash address:    {v['crash_address']}")
        lines.append(f"  Crash module:     {v['crash_module']} +0x{v['crash_offset']:X}")
        lines.append(f"  Thread ID:        {ex.get('thread_id', 'N/A')}")
        lines.append(f"  Dump size:        {p.get('size_mb', 'N/A')} MB")
        lines.append(f"  Modules:          {len(p.get('modules', []))}")
        lines.append(f"  Threads:          {len(p.get('threads', []))}")
        lines.append(f"  Timestamp:        {p.get('timestamp', 'N/A')}")
        lines.append("")

        chain = p.get("_stack_chain_extended", [])
        if chain:
            lines.append("CALL CHAIN")
            for i, entry in enumerate(chain):
                if len(entry) == 4:
                    addr, mod, off, verified = entry
                else:
                    addr, mod, off = entry[0], entry[1], entry[2]
                    verified = None
                prefix = "CRASH →" if i == 0 else f"  ← #{i:02d}"
                badge = ""
                if verified is True:
                    badge = " [pdata✓]"
                elif verified is False:
                    badge = " [heuristic]"
                lines.append(f"  {prefix} 0x{addr:016X}  {mod} +0x{off:X}{badge}")
            lines.append("")

        if True:
            active = _active_game_threads_at_crash(p)
            if active:
                lines.append("ACTIVE GAME THREADS (likely trigger for suicides)")
                for t in active[:8]:
                    rcx_note = "  <- RCX null" if t.get("rcx", 0) < 0x1000 else ""
                    lines.append(f"  TID {t['tid']:6d}  {t['module']}+0x{t['offset']:X}{rcx_note}")
                lines.append("")

        notes = self._player_notes.get("1.0", "end-1c").strip()
        if notes:
            lines.append("PLAYER NOTES")
            lines.append(f"  {notes}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)


    def navigate_to(self, link: dict):
        if not link:
            return
        tab = link.get("tab")
        if tab == "modules":
            self._nb.select(3)
        elif tab == "threads":
            self._nb.select(2)
        elif tab == "rootcause":
            self._nb.select(1)

    def _select_tab(self, index: int):
        if index < 5:
            self._nb.select(index)


    DEBUGGER_SCENARIOS = [
        ("Access Violation (NULL deref)",       "access_violation",   "Exceptions"),
        ("Access Violation (near-null offset)", "near_null_offset",   "Exceptions"),
        ("Access Violation (write to null)",    "null_write",         "Exceptions"),
        ("Access Violation (vtable dispatch)",  "vtable_dispatch",    "Exceptions"),
        ("Access Violation (use-after-free)",   "use_after_free",     "Exceptions"),
        ("Access Violation (high addr/kernel)", "high_address",       "Exceptions"),
        ("Single-Step Trap (debugger/AC)",      "single_step_trap",   "Exceptions"),
        ("Breakpoint (0x80000003)",             "breakpoint",         "Exceptions"),
        ("Stack Overflow (recursion)",          "stack_overflow",     "Exceptions"),
        ("Guard Page (near overflow)",          "guard_page",         "Exceptions"),
        ("Heap Overflow (write past bounds)",   "heap_overflow",      "Exceptions"),
        ("Heap Corruption (0xC0000374)",        "heap_corruption",    "Exceptions"),
        ("Stack Buffer Overrun (/GS)",          "stack_buffer_overrun","Exceptions"),
        ("DLL Init Failure (0xC0000142)",       "dll_init_fail",      "Exceptions"),
        ("DLL Not Found (0xC0000135)",          "dll_not_found",      "Exceptions"),
        ("Entry Point Not Found (0xC0000139)",  "entry_point",        "Exceptions"),
        ("In-Page Error (0xC0000006)",          "in_page_error",      "Exceptions"),
        ("Unhandled C++ Exception",             "cpp_exception",      "Exceptions"),
        ("Integer Divide by Zero",              "int_div_zero",       "Exceptions"),
        ("Float Divide by Zero",                "float_div_zero",     "Exceptions"),
        ("Float Invalid (NaN)",                 "float_invalid",      "Exceptions"),
        ("Integer Overflow",                    "int_overflow",       "Exceptions"),
        ("Privileged Instruction",              "privileged_instr",   "Exceptions"),
        ("Array Bounds Exceeded",               "array_bounds",       "Exceptions"),
        ("Invalid Handle (use-after-close)",    "invalid_handle",     "Exceptions"),
        ("Invalid CRT Parameter",               "invalid_crt_param",  "Exceptions"),
        ("Access Denied (permissions)",         "access_denied",      "Exceptions"),
        ("Out of Memory",                       "out_of_memory",      "Exceptions"),
        ("Not Mapped View",                     "not_mapped",         "Exceptions"),
        ("Assertion Failure (release)",         "assertion_failure",  "Exceptions"),
        ("Datatype Misalignment",               "misalignment",       "Exceptions"),
        ("Illegal Instruction (0xC000001D)",    "illegal_instr",      "Exceptions"),
        ("Suicide: Generic (engine self-kill)", "suicide_generic",    "Suicides"),
        ("Suicide: DirectStorage",              "suicide_dstorage",   "Suicides"),
        ("Suicide: Lua scripting",              "suicide_lua",        "Suicides"),
        ("Suicide: Audio (Wwise)",              "suicide_audio",      "Suicides"),
        ("Suicide: GPU driver",                 "suicide_gpu",        "Suicides"),
        ("Suicide: Network",                    "suicide_network",    "Suicides"),
        ("Suicide: Physics (PhysX)",            "suicide_physics",    "Suicides"),
        ("Suicide: Save/Load",                  "suicide_savegame",   "Suicides"),
        ("Suicide: Level streaming",            "suicide_level",      "Suicides"),
        ("Suicide: Animation",                  "suicide_anim",       "Suicides"),
        ("Suicide: UI/HUD",                     "suicide_ui",         "Suicides"),
        ("Suicide: Entity system",              "suicide_entity",     "Suicides"),
        ("Suicide: Resource loading",           "suicide_resource",   "Suicides"),
        ("Suicide: Shader compilation",         "suicide_shader",     "Suicides"),
        ("GPU Driver Crash (in nvwgf2umx)",     "gpu_driver_crash",   "GPU / D3D"),
        ("DXGI Device Hung (0x887A0006)",       "dxgi_device_hung",   "GPU / D3D"),
        ("DXGI Device Removed (0x887A0005)",    "dxgi_device_removed","GPU / D3D"),
        ("DXGI Driver Internal Error",          "dxgi_driver_error",  "GPU / D3D"),
        ("Dual-GPU Crash (NVIDIA+Intel)",       "dual_gpu_crash",     "GPU / D3D"),
        ("Crash in DirectStorage",              "dstorage_crash",     "GPU / D3D"),
        ("Mod detected (proxy DLL)",            "mod_detected",       "Mods & DLLs"),
        ("Mod in AppData (suspicious path)",    "appdata_mod",        "Mods & DLLs"),
        ("DLL Tamper (zeroed checksum)",        "dll_tamper",         "Mods & DLLs"),
        ("DLL Version Mismatch",                "dll_mismatch",       "Mods & DLLs"),
        ("Discord DLL in System32",             "discord_hijack",     "Mods & DLLs"),
        ("Missing VC++ Runtime entirely",       "missing_runtime",    "Mods & DLLs"),
        ("ReShade direct crash",                "reshade_crash",      "Mods & DLLs"),
        ("ReShade D3D corruption",              "reshade_d3d_corrupt","Mods & DLLs"),
        ("Crash in ntdll.dll (heap prop)",      "ntdll_crash",        "Crash Modules"),
        ("Crash in kernel32.dll",               "kernel32_crash",     "Crash Modules"),
        ("Crash in anti-cheat (EAC)",           "anticheat_crash",    "Crash Modules"),
        ("Crash in GameGuard",                  "gameguard_crash",    "Crash Modules"),
        ("Crash in Bink Video",                 "bink_crash",         "Crash Modules"),
        ("Crash in Steam API",                  "steam_api_crash",    "Crash Modules"),
        ("Crash in Wwise audio",                "wwise_crash",        "Crash Modules"),
        ("Crash in FMOD audio",                 "fmod_crash",         "Crash Modules"),
        ("Crash in PhysX",                      "physx_crash",        "Crash Modules"),
        ("Crash in Lua runtime",                "lua_crash",          "Crash Modules"),
        ("Crash in crash reporter",             "crash_handler_crash","Crash Modules"),
        ("Pure virtual call (vcruntime)",       "pure_virtual",       "Crash Modules"),
        ("Everything Clean (baseline-good)",    "clean_baseline",     "Baselines"),
        ("Kitchen Sink (multiple issues)",      "kitchen_sink",       "Baselines"),
        ("Multi-Signature Match (2+ patterns)",  "multi_signature",    "Baselines"),
        ("Empty module list",                   "empty_modules",      "Edge Cases"),
        ("No exception data",                   "no_exception",       "Edge Cases"),
        ("Corrupt module names",                "corrupt_names",      "Edge Cases"),
        ("Very large dump (simulated)",         "large_dump",         "Edge Cases"),
        ("Non-Stingray game (generic exe)",     "non_stingray",       "Edge Cases"),
        ("Multi-drive install (G:\\)",          "multi_drive",        "Edge Cases"),
        ("Helldivers 2 (real-style)",           "hd2_real_style",     "Edge Cases"),
    ]

    DEBUGGER_SECTIONS = [
        ("synthetic",  "1. Synthetic Data"),
        ("pipeline",   "2. Core Analysis Pipeline"),
        ("stack",      "3. Stack Analysis"),
        ("suicide",    "4. Stingray Suicide Detection"),
        ("dllinit",    "5. DLL Init Failure Handler"),
        ("dllverify",  "6. DLL Authenticity Verification"),
        ("patterns",   "7. Pattern Matching (all 61 patterns)"),
        ("mods",       "8. Mod Detection & Severity Ranking"),
        ("verdict",    "9. Verdict Engine & Signature"),
        ("sentinel",   "10. Sentinel Timestamp Whitelist"),
        ("threads",    "11. Thread Analysis"),
        ("callchain",  "12. Call Chain Reconstruction"),
        ("nullregs",   "13. Null Register Analysis"),
        ("instruction","14. Instruction Decoder"),
        ("dred",       "15. DRED GPU Log Parser"),
        ("env",        "16. Environment & Dependencies"),
    ]

    def _open_debugger(self, event=None):
        win = tk.Toplevel(self)
        win.title("Internal Debugger")
        win.geometry("1200x800")
        win.minsize(900, 600)
        win.configure(bg=BG)

        try:
            _icon_path = resource_path("assets", "icon.ico")
            if _icon_path.exists():
                win.iconbitmap(default=str(_icon_path))
        except Exception:
            pass

        hdr = tk.Frame(win, bg=BG2, padx=16, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Internal Debugger", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 13, "bold")).pack(side="left")
        tk.Label(hdr, text="  82 scenarios  |  16 test sections  |  Ctrl+F8",
                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left", padx=(8, 0))

        self._dbg_result_var = tk.StringVar(value="Ready - select a scenario and click Run")
        result_bar = tk.Frame(win, bg=BG3, padx=16, pady=6)
        result_bar.pack(fill="x")
        self._dbg_result_label = tk.Label(result_bar, textvariable=self._dbg_result_var,
                                          bg=BG3, fg=TEXT_DIM, font=(UI_FONT, 9, "bold"))
        self._dbg_result_label.pack(side="left")

        tk.Frame(win, bg=ACCENT, height=2).pack(fill="x")

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=BG3, width=340)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        search_frame = tk.Frame(left, bg=BG3, padx=10, pady=8)
        search_frame.pack(fill="x")
        tk.Label(search_frame, text="SCENARIOS", bg=BG3, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold")).pack(anchor="w")
        search_var = tk.StringVar()
        scenario_widgets = []
        search_var.trace_add("write", lambda *args: self._dbg_filter_scenarios(scenario_widgets, search_var.get()))
        search_entry = tk.Entry(search_frame, textvariable=search_var, bg=BG2, fg=TEXT,
                                font=(UI_FONT, 9), relief="flat", insertbackground=TEXT,
                                highlightbackground=BORDER, highlightthickness=1)
        search_entry.pack(fill="x", pady=(4, 0))
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, "end") if search_entry.get() == "Search..." else None)

        picker_canvas = tk.Canvas(left, bg=BG3, highlightthickness=0)
        picker_sb = tk.Scrollbar(left, orient="vertical", command=picker_canvas.yview,
                                 bg=BG3, relief="flat")
        picker_inner = tk.Frame(picker_canvas, bg=BG3)
        picker_canvas.create_window((0, 0), window=picker_inner, anchor="nw")
        picker_canvas.configure(yscrollcommand=picker_sb.set)
        picker_sb.pack(side="right", fill="y")
        picker_canvas.pack(side="left", fill="both", expand=True)

        scenario_var = tk.StringVar(value="access_violation")

        last_category = None
        for label, key, category in self.DEBUGGER_SCENARIOS:
            if category != last_category:
                cat_label = tk.Label(picker_inner, text=category.upper(), bg=BG3, fg=ACCENT2,
                                     font=(UI_FONT, 7, "bold"), anchor="w")
                cat_label.pack(fill="x", padx=4, pady=(10, 2))
                last_category = category
            rb = tk.Radiobutton(picker_inner, text=label, variable=scenario_var, value=key,
                                bg=BG3, fg=TEXT, selectcolor=BG2,
                                activebackground=BG3, activeforeground=ACCENT,
                                font=(UI_FONT, 8), anchor="w",
                                justify="left", wraplength=280)
            rb.pack(fill="x", padx=4, pady=1)
            scenario_widgets.append((rb, label, key, category))

        def _update_picker_scrollregion(event=None):
            picker_canvas.configure(scrollregion=picker_canvas.bbox("all"))
        picker_inner.bind("<Configure>", _update_picker_scrollregion)

        def _on_picker_wheel(event):
            try:
                if picker_canvas.winfo_exists():
                    picker_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        picker_canvas.bind_all("<MouseWheel>", _on_picker_wheel)

        mid = tk.Frame(body, bg=BG2, width=240)
        mid.pack(side="left", fill="y")
        mid.pack_propagate(False)

        tk.Label(mid, text="TEST SECTIONS", bg=BG2, fg=TEXT_DIM,
                 font=(UI_FONT, 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        section_vars = {}
        sect_scroll = ScrollableFrame(mid, bg=BG2)
        sect_scroll.pack(fill="both", expand=True)
        sect_inner = sect_scroll.inner

        for key, label in self.DEBUGGER_SECTIONS:
            v = tk.BooleanVar(value=True)
            section_vars[key] = v
            tk.Checkbutton(sect_inner, text=label, variable=v,
                           bg=BG2, fg=TEXT, selectcolor=BG3,
                           activebackground=BG2, activeforeground=ACCENT,
                           font=(UI_FONT, 8), anchor="w",
                           wraplength=200).pack(fill="x", padx=8, pady=1)

        sect_btn_row = tk.Frame(mid, bg=BG2, padx=10, pady=8)
        sect_btn_row.pack(fill="x", side="bottom")
        tk.Button(sect_btn_row, text="All",
                  command=lambda: [v.set(True) for v in section_vars.values()],
                  bg=BG3, fg=TEXT_DIM, relief="flat", padx=10, pady=3,
                  font=(UI_FONT, 8), cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(sect_btn_row, text="None",
                  command=lambda: [v.set(False) for v in section_vars.values()],
                  bg=BG3, fg=TEXT_DIM, relief="flat", padx=10, pady=3,
                  font=(UI_FONT, 8), cursor="hand2").pack(side="left")

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        log_frame = tk.Frame(right, bg=BG, padx=8, pady=8)
        log_frame.pack(fill="both", expand=True)

        log = tk.Text(log_frame, bg=BG2, fg=TEXT, font=(UI_MONO, 9),
                      insertbackground=TEXT, relief="flat",
                      wrap="word", state="disabled")
        sb = tk.Scrollbar(log_frame, command=log.yview, bg=BG2, relief="flat")
        log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        log.pack(fill="both", expand=True)

        log.tag_configure("ok",    foreground=GREEN)
        log.tag_configure("fail",  foreground=RED)
        log.tag_configure("warn",  foreground=YELLOW)
        log.tag_configure("head",  foreground=ACCENT, font=(UI_MONO, 9, "bold"))
        log.tag_configure("dim",   foreground=TEXT_DIM)
        log.tag_configure("pass_summary", foreground=GREEN, font=(UI_MONO, 10, "bold"))
        log.tag_configure("fail_summary", foreground=RED, font=(UI_MONO, 10, "bold"))

        def emit(text, tag=""):
            log.configure(state="normal")
            log.insert("end", text + "\n", tag)
            log.see("end")
            log.configure(state="disabled")

        def update_result_bar(passed, failed, warnings=0):
            if failed == 0:
                self._dbg_result_var.set(f"  {passed} passed  |  {failed} failed  |  {warnings} warnings  |  ALL PASSED")
                self._dbg_result_label.configure(fg=GREEN)
            else:
                self._dbg_result_var.set(f"  {passed} passed  |  {failed} failed  |  {warnings} warnings  |  FAILURES")
                self._dbg_result_label.configure(fg=RED)

        def run_one():
            log.configure(state="normal")
            log.delete("1.0", "end")
            log.configure(state="disabled")
            enabled = {k for k, v in section_vars.items() if v.get()}
            p, f = self._run_debugger(scenario_var.get(), emit, win, enabled_sections=enabled)
            update_result_bar(p, f)

        def run_all():
            log.configure(state="normal")
            log.delete("1.0", "end")
            log.configure(state="disabled")
            enabled = {k for k, v in section_vars.items() if v.get()}
            emit("=" * 70, "head")
            emit(f"  RUN ALL SCENARIOS  ({len(self.DEBUGGER_SCENARIOS)} total)", "head")
            emit("=" * 70, "head")
            emit("")
            grand_passed = 0
            grand_failed = 0
            scenario_results = []
            for label, key, category in self.DEBUGGER_SCENARIOS:
                p, f = self._run_debugger(key, emit, win, enabled_sections=enabled,
                                          compact=True)
                grand_passed += p
                grand_failed += f
                scenario_results.append((label, key, p, f))
            emit("")
            emit("=" * 70, "head")
            emit("  RUN ALL - SUMMARY BY SCENARIO", "head")
            emit("=" * 70, "head")
            for label, key, p, f in scenario_results:
                tag = "ok" if f == 0 else "fail"
                marker = "+" if f == 0 else "X"
                emit(f"  {marker}  {label:<40} {p:>3} passed, {f:>3} failed", tag)
            emit("")
            total_tag = "pass_summary" if grand_failed == 0 else "fail_summary"
            emit(f"  GRAND TOTAL: {grand_passed} passed, {grand_failed} failed "
                 f"across {len(self.DEBUGGER_SCENARIOS)} scenarios", total_tag)
            emit("=" * 70, "head")
            update_result_bar(grand_passed, grand_failed)

        bot = tk.Frame(win, bg=BG2, padx=16, pady=10)
        bot.pack(fill="x", side="bottom")
        tk.Frame(bot, bg=BORDER, height=1).pack(fill="x", pady=(0, 6))

        tk.Button(bot, text="Run Selected",
                  command=run_one,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=20, pady=8,
                  font=(UI_FONT, 9, "bold"), cursor="hand2").pack(side="left")
        tk.Button(bot, text="Run All (82)",
                  command=run_all,
                  bg=PURPLE, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=20, pady=8,
                  font=(UI_FONT, 9, "bold"), cursor="hand2").pack(side="left", padx=8)
        tk.Button(bot, text="Apply to Main Window",
                  command=lambda: self._debugger_apply(scenario_var.get()),
                  bg=BG3, fg=TEXT, activebackground=BORDER,
                  relief="flat", padx=16, pady=8,
                  font=(UI_FONT, 9), cursor="hand2").pack(side="left", padx=8)
        tk.Button(bot, text="Clear Log",
                  command=lambda: [log.configure(state="normal"),
                                   log.delete("1.0", "end"),
                                   log.configure(state="disabled"),
                                   self._dbg_result_var.set("Ready"),
                                   self._dbg_result_label.configure(fg=TEXT_DIM)],
                  bg=BG3, fg=TEXT_DIM, relief="flat", padx=14, pady=8,
                  font=(UI_FONT, 9), cursor="hand2").pack(side="right")

    def _dbg_filter_scenarios(self, widgets, search_text):
        search = search_text.lower().strip()
        if search == "search..." or not search:
            for widget, label, key, category in widgets:
                widget.pack()
            return
        for widget, label, key, category in widgets:
            if search in label.lower() or search in key.lower() or search in category.lower():
                widget.pack()
            else:
                widget.pack_forget()

    def _make_synthetic_parsed(self, scenario: str) -> dict:

        BASE_MODULES = [
            {"name": "C:\\Program Files\\Game\\game.exe",
             "base": "0x0000000140000000", "size": 52_428_800,
             "checksum": "0x031A2F40", "timestamp": "2024-03-15", "version": "1.4.0.0"},
            {"name": "C:\\Program Files\\Game\\engine.dll",
             "base": "0x0000000180000000", "size": 35_651_584,
             "checksum": "0x01B4C200", "timestamp": "2024-03-15", "version": "1.4.0.0"},
            {"name": "C:\\Windows\\System32\\ntdll.dll",
             "base": "0x00007FF800000000", "size": 2_097_152,
             "checksum": "0x00210A40", "timestamp": "2024-01-10", "version": "10.0.22621.0"},
            {"name": "C:\\Windows\\System32\\kernel32.dll",
             "base": "0x00007FF7F0000000", "size": 819_200,
             "checksum": "0x000D2A80", "timestamp": "2024-01-10", "version": "10.0.22621.0"},
            {"name": "C:\\Windows\\System32\\msvcp140.dll",
             "base": "0x00007FF700000000", "size": 593_920,
             "checksum": "0x00095A40", "timestamp": "2056-12-30", "version": "14.38.33130.0"},
            {"name": "C:\\Windows\\System32\\vcruntime140.dll",
             "base": "0x00007FF6F0000000", "size": 94_208,
             "checksum": "0x000183C0", "timestamp": "2005-04-16", "version": "14.38.33130.0"},
            {"name": "C:\\Windows\\System32\\vcruntime140_1.dll",
             "base": "0x00007FF6E0000000", "size": 40_960,
             "checksum": "0x000080C0", "timestamp": "2056-12-30", "version": "14.38.33130.0"},
            {"name": "C:\\Windows\\System32\\ucrtbase.dll",
             "base": "0x00007FF6D0000000", "size": 1_048_576,
             "checksum": "0x00102A00", "timestamp": "2014-06-17", "version": "10.0.22621.0"},
            {"name": "C:\\Program Files\\Game\\discord_game_sdk.dll",
             "base": "0x00007FF6C0000000", "size": 2_883_584,
             "checksum": "0x002C1800", "timestamp": "2023-06-01", "version": "3.2.1.0"},
        ]

        CRASH_RIP   = 0x0000000180123456
        CRASH_RSP   = 0x000000C800100000
        CRASH_THREAD_ID = 0x1A2B

        p = {
            "file":         f"[SYNTHETIC] {scenario}.dmp",
            "size_mb":      12.34,
            "version":      "1.0.synthetic",
            "timestamp":    "2026-06-17 12:00:00 UTC",
            "stream_count": 14,
            "process_id":   30155,
            "modules":      [dict(m) for m in BASE_MODULES],
            "memory_map":   [],
            "_raw_path":    None,
            "threads": [
                {
                    "tid":     CRASH_THREAD_ID,
                    "suspend": 0,
                    "pri":     8,
                    "rip":     CRASH_RIP,
                    "rsp":     CRASH_RSP,
                    "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                    "rbp": CRASH_RSP + 0x80, "rsi": 0, "rdi": 0,
                    "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                    "r12": 0, "r13": 0, "r14": 0, "r15": 0,
                },
                {
                    "tid":     0x3C4D,
                    "suspend": 0,
                    "pri":     8,
                    "rip":     0x00007FF800001234,
                    "rsp":     0x000000C800200000,
                    "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                    "rbp": 0, "rsi": 0, "rdi": 0,
                    "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                    "r12": 0, "r13": 0, "r14": 0, "r15": 0,
                },
            ],
            "exception": {
                "code":        "0xc0000005",
                "code_desc":   "EXCEPTION_ACCESS_VIOLATION",
                "address":     f"0x{CRASH_RIP:016X}",
                "thread_id":   CRASH_THREAD_ID,
                "fault_addr":  "0x0000000000000000",
                "is_write":    False,
                "regs": {
                    "rax": 0x0000000000000000,
                    "rbx": 0x0000000000000001,
                    "rcx": 0x0000000000000000,
                    "rdx": 0x0000000000000042,
                    "rsi": 0x0000000000000000,
                    "rdi": 0x00007FF800001234,
                    "r8":  0x0000000000000003,
                    "r9":  0x0000000000000000,
                    "r10": 0x0000000000000000,
                    "r11": 0x0000000000000000,
                    "r12": 0x0000000000000000,
                    "r13": 0x0000000000000000,
                    "r14": 0x0000000000000000,
                    "r15": 0x0000000000000000,
                    "rsp": CRASH_RSP,
                    "rbp": CRASH_RSP + 0x80,
                },
                "params": ["0x0000000000000000", "0x0000000000000000"],
            },
            "system_info": {
                "arch":       "x64",
                "cpu_level":  6,
                "cpu_rev":    0xA701,
                "cpu_count":  8,
                "os_version": "10.0 build 22621",
            },
            "game_root": "C:\\Program Files\\Game",
        }

        if scenario == "stack_overflow":
            p["exception"]["code"]      = "0xc00000fd"
            p["exception"]["code_desc"] = "EXCEPTION_STACK_OVERFLOW"
            p["exception"]["address"]   = "0x0000000180BEEF00"

        elif scenario == "dll_init_fail":
            p["exception"]["code"]      = "0xc0000142"
            p["exception"]["code_desc"] = "STATUS_DLL_INIT_FAILED"
            vcr_base = 0x00007FF6F0000000
            p["exception"]["address"]   = f"0x{vcr_base + 0x1234:016X}"
            p["exception"]["fault_addr"] = "0x0000000000000000"

        elif scenario == "cpp_exception":
            p["exception"]["code"]      = "0xe06d7363"
            p["exception"]["code_desc"] = "Microsoft C++ Exception"
            p["exception"]["address"]   = "0x0000000180456789"

        elif scenario == "heap_corruption":
            p["exception"]["code"]      = "0xc0000374"
            p["exception"]["code_desc"] = "STATUS_HEAP_CORRUPTION"
            p["exception"]["address"]   = "0x00007FF800001234"
            p["exception"]["fault_addr"] = "0xDEADBEEFDEADBEEF"

        elif scenario == "mod_detected":
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\d3d11.dll",
                "base": "0x00007FF6B0000000", "size": 1_200_000,
                "checksum": "0x00126A00", "timestamp": "2023-01-01",
                "version": "0.0.0.1",
            })
            p["modules"].append({
                "name": "C:\\Users\\Player\\AppData\\Local\\GameMods\\override.dll",
                "base": "0x00007FF6A0000000", "size": 450_000,
                "checksum": "0x000744A0", "timestamp": "2024-02-20",
                "version": "1.0.0.0",
            })

        elif scenario == "dll_tamper":
            for m in p["modules"]:
                if "msvcp140" in m["name"].lower():
                    m["checksum"]  = "0x00000000"
                    m["timestamp"] = "2001-01-01"

        elif scenario == "dll_mismatch":
            for m in p["modules"]:
                if "vcruntime140.dll" in m["name"].lower() and "_1" not in m["name"].lower():
                    m["size"]      = 68_000
                    m["timestamp"] = "2019-01-01"
                    m["version"]   = "14.16.27012.0"

        elif scenario == "discord_hijack":
            for m in p["modules"]:
                if "discord_game_sdk" in m["name"].lower():
                    m["name"] = "C:\\Windows\\System32\\discord_game_sdk.dll"

        elif scenario == "single_step_trap":
            p["exception"]["code"]       = "0x80000004"
            p["exception"]["code_desc"]  = "SINGLE_STEP - Single-step trace trap"
            p["exception"]["address"]    = "0x00007FFF04F648C1"
            p["exception"]["fault_addr"] = None
            p["exception"]["params"]     = []
            p["exception"]["regs"]["rdx"] = 0
            p["exception"]["regs"]["rsi"] = 0

        elif scenario == "heap_overflow":
            p["exception"]["code"]       = "0xc0000005"
            p["exception"]["code_desc"]  = "EXCEPTION_ACCESS_VIOLATION"
            p["exception"]["address"]    = "0x0000000180789ABC"
            p["exception"]["fault_addr"] = "0x000001F2A4B01018"
            p["exception"]["is_write"]   = True
            p["exception"]["params"]     = ["0x1", "0x1F2A4B01018"]

        elif scenario == "anticheat_block":
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\EasyAntiCheat.dll",
                "base": "0x0000000183000000",
                "size": 2_400_000,
                "checksum": "0x00248A00", "timestamp": "2025-11-01",
                "version": "5.0.1.0",
            })
            p["exception"]["code"]      = "0xc0000005"
            p["exception"]["code_desc"] = "EXCEPTION_ACCESS_VIOLATION"
            p["exception"]["address"]   = "0x0000000183012340"

        elif scenario == "appdata_mod":
            p["modules"].append({
                "name": "C:\\Users\\Player\\AppData\\Local\\SomeModLoader\\inject.dll",
                "base": "0x00007FF6A8000000", "size": 310_000,
                "checksum": "0x00050A00", "timestamp": "2025-08-15",
                "version": "2.1.0.0",
            })

        elif scenario == "missing_runtime":
            runtime_names = {"msvcp140.dll", "vcruntime140.dll",
                             "vcruntime140_1.dll", "ucrtbase.dll"}
            p["modules"] = [m for m in p["modules"]
                            if PureWindowsPath(m["name"]).name.lower() not in runtime_names]
            p["exception"]["code"]      = "0xc0000142"
            p["exception"]["code_desc"] = "STATUS_DLL_INIT_FAILED"
            p["exception"]["address"]   = "0x0000000140001000"

        elif scenario == "clean_baseline":
            pass

        elif scenario == "kitchen_sink":
            for m in p["modules"]:
                if "msvcp140" in m["name"].lower():
                    m["checksum"] = "0x00000000"
                if "discord_game_sdk" in m["name"].lower():
                    m["name"] = "C:\\Windows\\System32\\discord_game_sdk.dll"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\d3d11.dll",
                "base": "0x00007FF6B0000000", "size": 1_200_000,
                "checksum": "0x00126A00", "timestamp": "2023-01-01",
                "version": "0.0.0.1",
            })

        elif scenario == "multi_signature":
            pass


        elif scenario == "near_null_offset":
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["exception"]["regs"]["rdx"] = 0

        elif scenario == "null_write":
            p["exception"]["params"] = ["0x1", "0x0"]
            p["exception"]["is_write"] = True

        elif scenario == "vtable_dispatch":
            p["exception"]["params"] = ["0x0", "0x0"]
            p["exception"]["regs"]["rcx"] = 0
            p["exception"]["regs"]["rax"] = 0

        elif scenario == "use_after_free":
            uaf_addr = 0x000001F2A4B01018
            p["exception"]["params"] = ["0x0", f"0x{uaf_addr:016X}"]
            p["exception"]["regs"]["rax"] = uaf_addr
            p["exception"]["regs"]["rcx"] = uaf_addr

        elif scenario == "high_address":
            p["exception"]["params"] = ["0x0", "0xFFFFF00000000000"]

        elif scenario == "breakpoint":
            p["exception"]["code"] = "0x80000003"
            p["exception"]["code_desc"] = "BREAKPOINT - Debugger breakpoint hit"
            p["exception"]["params"] = []
            p["exception"]["fault_addr"] = None

        elif scenario == "guard_page":
            p["exception"]["code"] = "0x80000001"
            p["exception"]["code_desc"] = "GUARD_PAGE - Guard page access"
            p["exception"]["params"] = []

        elif scenario == "stack_buffer_overrun":
            p["exception"]["code"] = "0xc0000409"
            p["exception"]["code_desc"] = "STATUS_STACK_BUFFER_OVERRUN"
            p["exception"]["params"] = []

        elif scenario == "dll_not_found":
            p["exception"]["code"] = "0xc0000135"
            p["exception"]["code_desc"] = "STATUS_DLL_NOT_FOUND"
            p["exception"]["address"] = "0x0000000140001000"

        elif scenario == "entry_point":
            p["exception"]["code"] = "0xc0000139"
            p["exception"]["code_desc"] = "STATUS_ENTRYPOINT_NOT_FOUND"
            p["exception"]["address"] = "0x0000000140001000"

        elif scenario == "in_page_error":
            p["exception"]["code"] = "0xc0000006"
            p["exception"]["code_desc"] = "STATUS_IN_PAGE_ERROR"
            p["exception"]["params"] = ["0x0", "0xDEADBEEF"]
            p["exception"]["fault_addr"] = "0xDEADBEEF"

        elif scenario == "int_div_zero":
            p["exception"]["code"] = "0xc0000094"
            p["exception"]["code_desc"] = "STATUS_INTEGER_DIVIDE_BY_ZERO"
            p["exception"]["params"] = []

        elif scenario == "float_div_zero":
            p["exception"]["code"] = "0xc000008e"
            p["exception"]["code_desc"] = "STATUS_FLOAT_DIVIDE_BY_ZERO"
            p["exception"]["params"] = []

        elif scenario == "float_invalid":
            p["exception"]["code"] = "0xc0000090"
            p["exception"]["code_desc"] = "STATUS_FLOAT_INVALID_OPERATION"
            p["exception"]["params"] = []

        elif scenario == "int_overflow":
            p["exception"]["code"] = "0xc0000095"
            p["exception"]["code_desc"] = "STATUS_INTEGER_OVERFLOW"
            p["exception"]["params"] = []

        elif scenario == "privileged_instr":
            p["exception"]["code"] = "0xc0000096"
            p["exception"]["code_desc"] = "STATUS_PRIVILEGED_INSTRUCTION"
            p["exception"]["params"] = []

        elif scenario == "array_bounds":
            p["exception"]["code"] = "0xc000008c"
            p["exception"]["code_desc"] = "STATUS_ARRAY_BOUNDS_EXCEEDED"
            p["exception"]["params"] = []

        elif scenario == "invalid_handle":
            p["exception"]["code"] = "0xc0000008"
            p["exception"]["code_desc"] = "STATUS_INVALID_HANDLE"
            p["exception"]["params"] = []

        elif scenario == "invalid_crt_param":
            p["exception"]["code"] = "0xc0000353"
            p["exception"]["code_desc"] = "STATUS_INVALID_CRUNTIME_PARAMETER"
            p["exception"]["params"] = []

        elif scenario == "access_denied":
            p["exception"]["code"] = "0xc0000022"
            p["exception"]["code_desc"] = "STATUS_ACCESS_DENIED"
            p["exception"]["params"] = []

        elif scenario == "out_of_memory":
            p["exception"]["code"] = "0xc0000017"
            p["exception"]["code_desc"] = "STATUS_NO_MEMORY"
            p["exception"]["params"] = []

        elif scenario == "not_mapped":
            p["exception"]["code"] = "0xc000001a"
            p["exception"]["code_desc"] = "STATUS_NOT_MAPPED_VIEW"
            p["exception"]["params"] = ["0x0", "0x12345678"]

        elif scenario == "assertion_failure":
            p["exception"]["code"] = "0xc0000420"
            p["exception"]["code_desc"] = "STATUS_ASSERTION_FAILURE"
            p["exception"]["params"] = []

        elif scenario == "misalignment":
            p["exception"]["code"] = "0x80000002"
            p["exception"]["code_desc"] = "STATUS_DATATYPE_MISALIGNMENT"
            p["exception"]["params"] = []

        elif scenario == "illegal_instr":
            p["exception"]["code"] = "0xc000001d"
            p["exception"]["code_desc"] = "ILLEGAL_INSTRUCTION"
            p["exception"]["params"] = []

        elif scenario == "suicide_generic":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["exception"]["regs"]["rdx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234

        elif scenario == "suicide_dstorage":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["exception"]["regs"]["rdx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\dstorage.dll",
                "base": "0x00007FF690000000", "size": 221_184,
                "checksum": "0x00035E00", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5001, "suspend": 0, "pri": 8,
                "rip": 0x00007FF690001234, "rsp": 0x000000C800300000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "suicide_lua":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\lua51.dll",
                "base": "0x00007FF688000000", "size": 471_040,
                "checksum": "0x00073000", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5002, "suspend": 0, "pri": 8,
                "rip": 0x00007FF688001234, "rsp": 0x000000C800400000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "suicide_audio":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\wwise_pluginw64_release.dll",
                "base": "0x00007FF687000000", "size": 1_500_000,
                "checksum": "0x0016E360", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5003, "suspend": 0, "pri": 8,
                "rip": 0x00007FF687001234, "rsp": 0x000000C800500000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "suicide_gpu":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Windows\\System32\\nvwgf2umx.dll",
                "base": "0x00007FF686000000", "size": 5_000_000,
                "checksum": "0x004C4B40", "timestamp": "2024-06-01",
            })
            p["threads"].append({
                "tid": 0x5004, "suspend": 0, "pri": 8,
                "rip": 0x00007FF686001234, "rsp": 0x000000C800600000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "suicide_network":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\network.dll",
                "base": "0x00007FF685000000", "size": 800_000,
                "checksum": "0x000C3500", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5005, "suspend": 0, "pri": 8,
                "rip": 0x00007FF685001234, "rsp": 0x000000C800700000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "suicide_physics":
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\physx3_x64.dll",
                "base": "0x00007FF684000000", "size": 3_000_000,
                "checksum": "0x002DC6C0", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5006, "suspend": 0, "pri": 8,
                "rip": 0x00007FF684001234, "rsp": 0x000000C800800000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario in ("suicide_savegame", "suicide_level", "suicide_anim",
                          "suicide_ui", "suicide_entity", "suicide_resource",
                          "suicide_shader"):
            subsystem_map = {
                "suicide_savegame":  ("savegame.dll",       0x00007FF683000000, 600_000),
                "suicide_level":     ("level_streaming.dll", 0x00007FF682000000, 900_000),
                "suicide_anim":      ("animation.dll",      0x00007FF681000000, 1_200_000),
                "suicide_ui":        ("hud_ui.dll",         0x00007FF680000000, 800_000),
                "suicide_entity":    ("entity_system.dll",  0x00007FF67F000000, 1_500_000),
                "suicide_resource":  ("resource_manager.dll",0x00007FF67E000000, 1_000_000),
                "suicide_shader":    ("dxcompiler.dll",    0x00007FF67D000000, 2_500_000),
            }
            sub_name, sub_base, sub_size = subsystem_map[scenario]
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
            hd2_base = int(p["modules"][0]["base"], 16)
            p["exception"]["address"] = f"0x{hd2_base + 0x1234:016X}"
            p["exception"]["regs"]["rip"] = hd2_base + 0x1234
            p["modules"].append({
                "name": f"C:\\Program Files\\Game\\{sub_name}",
                "base": f"0x{sub_base:016X}", "size": sub_size,
                "checksum": "0x00020000", "timestamp": "2024-01-15",
            })
            p["threads"].append({
                "tid": 0x5010, "suspend": 0, "pri": 8,
                "rip": sub_base + 0x1234, "rsp": 0x000000C800900000,
                "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0,
                "rbp": 0, "rsi": 0, "rdi": 0,
                "r8": 0, "r9": 0, "r10": 0, "r11": 0,
                "r12": 0, "r13": 0, "r14": 0, "r15": 0,
            })

        elif scenario == "gpu_driver_crash":
            nv_base = 0x00007FF675000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{nv_base + 0x12345:016X}"
            p["exception"]["params"] = ["0x0", "0x0"]
            p["modules"].append({
                "name": "C:\\Windows\\System32\\nvwgf2umx.dll",
                "base": f"0x{nv_base:016X}", "size": 5_000_000,
                "checksum": "0x004C4B40", "timestamp": "2024-06-01",
            })

        elif scenario == "dxgi_device_hung":
            p["exception"]["code"] = "0x887a0006"
            p["exception"]["code_desc"] = "DXGI_ERROR_DEVICE_HUNG"
            p["exception"]["params"] = []

        elif scenario == "dxgi_device_removed":
            p["exception"]["code"] = "0x887a0005"
            p["exception"]["code_desc"] = "DXGI_ERROR_DEVICE_REMOVED"
            p["exception"]["params"] = []

        elif scenario == "dxgi_driver_error":
            p["exception"]["code"] = "0x887a0020"
            p["exception"]["code_desc"] = "DXGI_ERROR_DRIVER_INTERNAL_ERROR"
            p["exception"]["params"] = []

        elif scenario == "dual_gpu_crash":
            p["modules"].append({
                "name": "C:\\Windows\\System32\\nvwgf2umx.dll",
                "base": "0x00007FF675000000", "size": 5_000_000,
                "checksum": "0x004C4B40", "timestamp": "2024-06-01",
            })
            p["modules"].append({
                "name": "C:\\Windows\\System32\\igd10iumd64.dll",
                "base": "0x00007FF674000000", "size": 3_000_000,
                "checksum": "0x002DC6C0", "timestamp": "2024-03-01",
            })
            nv_base = 0x00007FF675000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{nv_base + 0x12345:016X}"

        elif scenario == "dstorage_crash":
            ds_base = 0x00007FF673000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{ds_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\dstorage.dll",
                "base": f"0x{ds_base:016X}", "size": 221_184,
                "checksum": "0x00035E00", "timestamp": "2024-01-15",
            })

        elif scenario == "ntdll_crash":
            ntdll_base = 0x00007FF800000000
            p["exception"]["code"] = "0xc0000374"
            p["exception"]["address"] = f"0x{ntdll_base + 0x1234:016X}"

        elif scenario == "kernel32_crash":
            k32_base = 0x00007FF7F0000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{k32_base + 0x1234:016X}"

        elif scenario == "anticheat_crash":
            eac_base = 0x0000000183000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{eac_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\EasyAntiCheat.dll",
                "base": f"0x{eac_base:016X}", "size": 2_400_000,
                "checksum": "0x00248A00", "timestamp": "2025-11-01",
            })

        elif scenario == "gameguard_crash":
            gg_base = 0x00007FF670000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{gg_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\GameGuard\\npggNT64.des",
                "base": f"0x{gg_base:016X}", "size": 3_395_584,
                "checksum": "0x0033C500", "timestamp": "2024-05-01",
            })

        elif scenario == "bink_crash":
            bink_base = 0x00007FF66F000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{bink_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\bink2w64.dll",
                "base": f"0x{bink_base:016X}", "size": 434_176,
                "checksum": "0x0006A000", "timestamp": "2024-01-15",
            })

        elif scenario == "steam_api_crash":
            sa_base = 0x00007FF66E000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{sa_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\steam_api64.dll",
                "base": f"0x{sa_base:016X}", "size": 311_296,
                "checksum": "0x0004C000", "timestamp": "2024-01-15",
            })

        elif scenario == "wwise_crash":
            wwise_base = 0x00007FF66D000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{wwise_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\AkSoundEngine.dll",
                "base": f"0x{wwise_base:016X}", "size": 8_000_000,
                "checksum": "0x007A1200", "timestamp": "2024-01-15",
            })

        elif scenario == "fmod_crash":
            fmod_base = 0x00007FF66C000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{fmod_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\fmodstudio64.dll",
                "base": f"0x{fmod_base:016X}", "size": 2_500_000,
                "checksum": "0x002625A0", "timestamp": "2024-01-15",
            })

        elif scenario == "physx_crash":
            px_base = 0x00007FF66B000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{px_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\physx3_x64.dll",
                "base": f"0x{px_base:016X}", "size": 3_000_000,
                "checksum": "0x002DC6C0", "timestamp": "2024-01-15",
            })

        elif scenario == "lua_crash":
            lua_base = 0x00007FF66A000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{lua_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\lua51.dll",
                "base": f"0x{lua_base:016X}", "size": 471_040,
                "checksum": "0x00073000", "timestamp": "2024-01-15",
            })

        elif scenario == "crash_handler_crash":
            crs_base = 0x00007FF669000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{crs_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\crs-client.dll",
                "base": f"0x{crs_base:016X}", "size": 491_520,
                "checksum": "0x00078000", "timestamp": "2024-01-15",
            })

        elif scenario == "pure_virtual":
            vcr_base = 0x00007FF6F0000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{vcr_base + 0x1234:016X}"
            p["exception"]["params"] = ["0x0", "0x0"]

        elif scenario == "reshade_crash":
            proxy_base = 0x00007FF668000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{proxy_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\dxgi.dll",
                "base": f"0x{proxy_base:016X}", "size": 1_500_000,
                "checksum": "0x0016E360", "timestamp": "2023-06-01",
            })

        elif scenario == "reshade_d3d_corrupt":
            d3d12_base = 0x00007FF8002000000
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["address"] = f"0x{d3d12_base + 0x1234:016X}"
            p["modules"].append({
                "name": "C:\\Program Files\\Game\\dxgi.dll",
                "base": "0x00007FF668000000", "size": 1_500_000,
                "checksum": "0x0016E360", "timestamp": "2023-06-01",
            })
            p["modules"].append({
                "name": "C:\\Windows\\System32\\d3d12.dll",
                "base": f"0x{d3d12_base:016X}", "size": 2_000_000,
                "checksum": "0x001E8480", "timestamp": "2024-06-01",
            })

        elif scenario == "empty_modules":
            p["modules"] = []
            p["exception"]["address"] = "0x0000000000000000"

        elif scenario == "no_exception":
            p["exception"] = None

        elif scenario == "corrupt_names":
            for m in p["modules"]:
                m["name"] = "\x00\x01garbage\x00\x02"

        elif scenario == "large_dump":
            p["size_mb"] = 250.0
            for i in range(300):
                p["modules"].append({
                    "name": f"C:\\Program Files\\Game\\mod_{i:03d}.dll",
                    "base": f"0x{0x00007FF660000000 + i * 0x100000:016X}",
                    "size": 100_000 + i * 100,
                    "checksum": f"0x{i:08X}", "timestamp": "2024-01-01",
                })

        elif scenario == "non_stingray":
            p["modules"][0]["name"] = "C:\\Games\\MyGame\\mygame.exe"

        elif scenario == "multi_drive":
            for m in p["modules"]:
                m["name"] = m["name"].replace("C:\\Program Files\\Game\\", "G:\\SteamLibrary\\steamapps\\common\\MyGame\\")
            p["game_root"] = "g:\\steamlibrary\\steamapps\\common\\mygame"

        elif scenario == "hd2_real_style":
            p["modules"][0]["name"] = "G:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\bin\\helldivers2.exe"
            p["modules"][0]["size"] = 60_755_968
            p["modules"].extend([
                {"name": "G:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\bin\\crs-client.dll",
                 "base": "0x00007FFA826C0000", "size": 491_520,
                 "checksum": "0x00078000", "timestamp": "2024-06-15"},
                {"name": "G:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\bin\\dstorage.dll",
                 "base": "0x00007FFA832F0000", "size": 221_184,
                 "checksum": "0x00035E00", "timestamp": "2024-06-15"},
                {"name": "G:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\bin\\lua51.dll",
                 "base": "0x00007FFA82800000", "size": 471_040,
                 "checksum": "0x00073000", "timestamp": "2024-06-15"},
                {"name": "G:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\bin\\GameGuard\\npggNT64.des",
                 "base": "0x00007FFA09B50000", "size": 3_395_584,
                 "checksum": "0x0033C500", "timestamp": "2024-06-15"},
            ])
            p["exception"]["code"] = "0xc0000005"
            p["exception"]["params"] = ["0x0", "0x4"]
            p["exception"]["regs"]["rcx"] = 0
            p["exception"]["regs"]["rdx"] = 0
            p["game_root"] = "g:\\steamlibrary\\steamapps\\common\\helldivers 2"

        return p

    def _run_debugger(self, scenario: str, emit, win, enabled_sections=None, compact=False):
        import traceback, time

        def section_on(key):
            return enabled_sections is None or key in enabled_sections

        if compact:
            emit(f"-- {scenario} " + "-" * max(0, 50 - len(scenario)), "head")
        else:
            emit("=" * 70, "head")
            emit(f"  STINGRAY CRASH ANALYZER - FEATURE TEST", "head")
            emit(f"  Scenario: {scenario}", "head")
            emit("=" * 70, "head")
            emit("")

        passed = 0
        failed = 0
        warned = 0

        def check(label, fn, *args, **kwargs):
            nonlocal passed, failed, warned
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                ms = (time.perf_counter() - t0) * 1000
                emit(f"  [OK]  {label}  ({ms:.1f} ms)", "ok")
                passed += 1
                return result
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                emit(f"  [FAIL]  {label}  ({ms:.1f} ms)", "fail")
                emit(f"       {type(e).__name__}: {e}", "fail")
                for line in traceback.format_exc().splitlines()[-6:]:
                    emit(f"       {line}", "dim")
                failed += 1
                return None

        def check_val(label, value, expected=None, contains=None, min_len=None):
            nonlocal passed, failed, warned
            try:
                ok = True
                note = ""
                if expected is not None and value != expected:
                    ok = False
                    note = f" - expected {expected!r}, got {value!r}"
                if contains is not None and (value is None or contains not in str(value)):
                    ok = False
                    note = f" - expected to contain {contains!r}"
                if min_len is not None and (value is None or len(value) < min_len):
                    ok = False
                    note = f" - expected len >= {min_len}, got {len(value) if value else 0}"
                if ok:
                    emit(f"  [OK]  {label}", "ok")
                    passed += 1
                else:
                    emit(f"  [FAIL]  {label}{note}", "fail")
                    failed += 1
            except Exception as e:
                emit(f"  [FAIL]  {label}  - {e}", "fail")
                failed += 1

        if section_on("synthetic"):
            emit("[ 1 ]  Synthetic Data", "head")
        parsed = self._make_synthetic_parsed(scenario)
        if section_on("synthetic"):
            check("Build synthetic parsed dict", lambda: parsed)
            if parsed is None:
                emit("\nCannot continue - synthetic data construction failed.", "fail")
                return (passed, failed)
            if scenario == "empty_modules":
                check_val("empty_modules has 0 modules (expected)", len(parsed.get("modules", [])), expected=0)
            else:
                check_val("parsed has modules",   parsed.get("modules"),   min_len=5)
            if scenario == "no_exception":
                check_val("no_exception has no exception (expected)", parsed.get("exception"), expected=None)
            else:
                check_val("parsed has exception", parsed.get("exception"), min_len=1)
            check_val("parsed has threads",   parsed.get("threads"),   min_len=1)
            check_val("parsed has system_info", parsed.get("system_info"), min_len=1)
            emit("")
        elif parsed is None:
            return (passed, failed)

        if section_on("pipeline"):
            emit("[ 2 ]  Core Analysis Pipeline", "head")
            summary = check("build_summary()", build_summary, parsed)
            check_val("summary is non-empty string", summary, min_len=10)
            hints = check("quick_patterns()", quick_patterns, parsed)
            check_val("quick_patterns returns list", hints, min_len=0)
            rootcause = check("assess_root_cause()", assess_root_cause, parsed)
            if rootcause:
                check_val("assess_root_cause returns list", rootcause, min_len=1)
                check_val("root cause has title",  rootcause[0].get("title"), min_len=3)
                check_val("root cause has detail", rootcause[0].get("detail"), min_len=5)
                check_val("root cause has conf",   rootcause[0].get("conf")   in ("HIGH","MED","LOW"), expected=True)
            else:
                check_val("assess_root_cause returns list (empty OK for no-exception)",
                          isinstance(rootcause, list), expected=True)
            mods = check("detect_mods()", detect_mods, parsed)
            check_val("detect_mods returns dict", mods is not None, expected=True)
            check_val("detect_mods has has_mods key", "has_mods" in (mods or {}), expected=True)
            check_val("detect_mods has indicators",   "indicators" in (mods or {}), expected=True)
            threads = check("analyse_threads()", analyse_threads, parsed)
            check_val("analyse_threads returns list", threads, min_len=1)
            plain = check("build_plain_english()", build_plain_english, parsed, rootcause, mods, None)
            check_val("plain english has headline key", "headline" in (plain or {}), expected=True)
            dll_verify = check("verify_critical_dlls()", verify_critical_dlls, parsed)
            check_val("dll_verify has msvcp140 key", "msvcp140" in (dll_verify or {}), expected=True)
            check_val("dll_verify has runtime key",  "runtime"  in (dll_verify or {}), expected=True)
            check_val("dll_verify has discord key",  "discord"  in (dll_verify or {}), expected=True)
            emit("")
        else:
            try:
                rootcause  = assess_root_cause(parsed)
            except Exception:
                rootcause = []
            try:
                mods = detect_mods(parsed)
            except Exception:
                mods = {}
            try:
                dll_verify = verify_critical_dlls(parsed)
            except Exception:
                dll_verify = {}

        if section_on("stack"):
            emit("[ 3 ]  Stack Analysis", "head")
            chain = check("_reconstruct_call_chain()", _reconstruct_call_chain, parsed, 12)
            emit(f"  .  Chain frames: {len(chain) if chain is not None else 0} "
                 f"(0 expected - no memory map in synthetic mode)", "dim")
            unwind = parsed.get("_stack_unwind", {})
            emit(f"  .  pdata modules: {unwind.get('pdata_modules', 0)} / "
                 f"{unwind.get('total_modules', 0)}", "dim")
            emit(f"  .  pdata confirmed: {unwind.get('pdata_confirmed', 0)}, "
                 f"heuristic: {unwind.get('heuristic', 0)}", "dim")
            if scenario == "stack_overflow":
                emit("  .  Testing recursion detector:", "dim")
                recursion = check("_detect_recursion()", _detect_recursion, parsed)
                check_val("recursion description non-empty", recursion, min_len=20)
            emit("")

        if section_on("dllinit"):
            emit("[ 4 ]  DLL Init Failure Handler", "head")
            dll_suspect = check("_find_dll_init_suspect()", _find_dll_init_suspect, parsed)
            check_val("returns non-empty string", dll_suspect, min_len=10)
            if scenario == "dll_init_fail":
                check_val("identifies vcruntime140",
                          dll_suspect is not None and "vcruntime140" in dll_suspect.lower(),
                          expected=True)
            emit("")

        if section_on("dllverify"):
            emit("[ 5 ]  DLL Authenticity Verification", "head")
            if dll_verify:
                m140 = dll_verify.get("msvcp140")
                if m140:
                    emit(f"  .  MSVCP140  verdict: {m140.get('verdict','?')}  "
                         f"checksum: {m140.get('checksum','?')}  "
                         f"ts: {m140.get('timestamp_date','?')}", "dim")
                    if scenario == "dll_tamper":
                        check_val("MSVCP140 flagged as LIKELY_TAMPERED",
                                  m140.get("verdict"), expected="LIKELY_TAMPERED")
                    elif scenario == "dll_mismatch":
                        check_val("MSVCP140 flagged due to cross-DLL version mismatch",
                                  m140.get("verdict") != "OK", expected=True)
                    elif scenario == "kitchen_sink":
                        check_val("MSVCP140 flagged (tampered checksum in this scenario)",
                                  m140.get("verdict") != "OK", expected=True)
                    elif scenario != "missing_runtime":
                        check_val("MSVCP140 passes clean on legitimate data",
                                  m140.get("verdict"), expected="OK")
                elif scenario == "missing_runtime":
                    emit("  .  MSVCP140 correctly absent (missing_runtime scenario)", "dim")

                rt = dll_verify.get("runtime", {})
                for dll_key in ("vcruntime140.dll", "vcruntime140_1.dll", "ucrtbase.dll"):
                    r = rt.get(dll_key)
                    if r:
                        emit(f"  .  {dll_key:<26} verdict: {r.get('verdict','?')}  "
                             f"ts: {r.get('timestamp_date','?')}", "dim")
                        if scenario not in ("dll_tamper", "dll_mismatch", "missing_runtime",
                                            "kitchen_sink"):
                            check_val(f"{dll_key} passes clean",
                                      r.get("verdict"), expected="OK")
                    else:
                        emit(f"  .  {dll_key:<26} NOT FOUND in module list", "dim")
                        if scenario == "missing_runtime":
                            check_val(f"{dll_key} correctly absent",
                                      True, expected=True)

                discord_list = dll_verify.get("discord", [])
                if discord_list:
                    dr = discord_list[0]
                    emit(f"  .  {dr.get('name','?'):<26} verdict: {dr.get('verdict','?')}", "dim")
                    if scenario == "discord_hijack":
                        check_val("Discord DLL flagged as LIKELY_TAMPERED",
                                  dr.get("verdict"), expected="LIKELY_TAMPERED")
                    elif scenario not in ("kitchen_sink",):
                        check_val("Discord DLL passes clean", dr.get("verdict"), expected="OK")
            emit("")

        if section_on("patterns"):
            emit("[ 6 ]  Pattern Matching", "head")
            try:
                decoded_instr = None
                if not parsed.get("exception"):
                    emit("  .  No exception data - skipping pattern matching", "dim")
                    pattern = None
                    all_p = []
                    check_val("pattern is None when no exception", pattern is None, expected=True)
                else:
                    pattern = _match_patterns(parsed, decoded_instr, mods, rootcause)
                    emit(f"  .  Pattern match result: {pattern!r}", "dim")
                    emit("  [OK]  _match_patterns() completed without error", "ok")
                    passed += 1
            except Exception as e:
                emit(f"  [FAIL]  _match_patterns() raised: {e}", "fail")
                failed += 1
                pattern = None

            try:
                if not parsed.get("exception"):
                    all_p = []
                else:
                    all_matches = _match_all_patterns(parsed, decoded_instr, mods, rootcause)
                    all_p = all_matches
                    emit(f"  .  _match_all_patterns() returned {len(all_matches)} match(es)", "dim")
                    check_val("_match_all_patterns returns a list", isinstance(all_matches, list), expected=True)
            except Exception as e:
                emit(f"  [FAIL]  _match_all_patterns() raised: {e}", "fail")
                failed += 1
                all_p = []
            emit("")

        if section_on("mods"):
            emit("[ 7 ]  Mod Detection & Severity Ranking", "head")
            if mods:
                emit(f"  .  has_mods:   {mods.get('has_mods')}", "dim")
                emit(f"  .  confidence: {mods.get('confidence')}", "dim")
                for ind in mods.get("indicators", []):
                    sev = ind.get("severity", "?")
                    tag = "fail" if sev == "HIGH" else ("warn" if sev == "MED" else "dim")
                    emit(f"  .  [{sev:4}] {ind.get('type','?')} - {ind.get('detail','')}", tag)
                if scenario in ("mod_detected", "kitchen_sink"):
                    check_val("mod detected - has_mods is True", mods.get("has_mods"), expected=True)
                    check_val("at least one indicator present",
                              mods.get("indicators", []), min_len=1)
                if scenario == "appdata_mod":
                    check_val("mod detected - has_mods is True", mods.get("has_mods"), expected=True)
                    has_appdata = any(i.get("type") == "appdata_mod"
                                      for i in mods.get("indicators", []))
                    check_val("appdata_mod indicator present", has_appdata, expected=True)
                if scenario == "clean_baseline":
                    check_val("clean baseline - has_mods is False",
                              mods.get("has_mods"), expected=False)
            emit("")

        if section_on("sentinel"):
            emit("[ 8 ]  Sentinel Timestamp Whitelist", "head")
            sentinel_tests = [
                ("2005-04-16", "vcruntime140.dll", "0x000183C0"),
                ("2014-06-17", "ucrtbase.dll",     "0x00102A00"),
                ("2056-12-30", "msvcp140.dll",     "0x00095A40"),
            ]
            for ts, dll_name, cs_hex in sentinel_tests:
                test_mod = {
                    "name": f"C:\\Windows\\System32\\{dll_name}",
                    "base": "0x00007FF700000000",
                    "size": 595_000,
                    "checksum": cs_hex,
                    "timestamp": ts,
                }
                test_parsed = {**parsed, "modules": [test_mod]}
                try:
                    test_verify = verify_critical_dlls(test_parsed)
                    if dll_name == "msvcp140.dll":
                        result = test_verify.get("msvcp140")
                    else:
                        result = test_verify.get("runtime", {}).get(dll_name)
                    if result:
                        ts_issues = [i for i in result.get("issues", [])
                                     if "future" in i.lower() or "predates" in i.lower()
                                     or "sentinel" in i.lower()]
                        if not ts_issues:
                            emit(f"  [OK]  {dll_name} ts={ts} not false-flagged (verdict: {result.get('verdict')})", "ok")
                            passed += 1
                        else:
                            emit(f"  [FAIL]  {dll_name} ts={ts} incorrectly flagged:", "fail")
                            for i in ts_issues:
                                emit(f"       {i[:80]}...", "fail")
                            failed += 1
                    else:
                        emit(f"  .  {dll_name} not found in test verify result", "dim")
                except Exception as e:
                    emit(f"  [FAIL]  sentinel test for {dll_name}: {e}", "fail")
                    failed += 1
            emit("")

        if section_on("env"):
            emit("[ 9 ]  Environment & Dependencies", "head")
            try:
                rp = resource_path("assets", "icon.ico")
                emit(f"  .  resource_path('assets', 'icon.ico') -> {rp}", "dim")
                check_val("resource_path returns a Path object",
                          isinstance(rp, Path), expected=True)
            except Exception as e:
                emit(f"  [FAIL]  resource_path() raised: {e}", "fail")
                failed += 1

            try:
                icon_path = resource_path("assets", "icon.ico")
                if icon_path.exists():
                    emit(f"  [OK]  assets/icon.ico found on disk", "ok")
                    passed += 1
                else:
                    emit(f"  [!]  assets/icon.ico NOT found (app will fall back - not a hard failure)", "warn")
                    warned += 1
            except Exception as e:
                emit(f"  [FAIL]  icon path check raised: {e}", "fail")
                failed += 1

            if _DND_AVAILABLE:
                emit(f"  [OK]  tkinterdnd2 available - drag-and-drop active", "ok")
                passed += 1
            else:
                emit(f"  [!]  tkinterdnd2 NOT installed - drag-and-drop disabled", "warn")
                warned += 1

            try:
                pattern_data = _load_pattern_file()
                n_builtin = len(pattern_data.get("builtin_patterns", []))
                n_custom  = len(pattern_data.get("patterns", []))
                emit(f"  .  crash_patterns.json: {n_builtin} builtin, {n_custom} custom patterns", "dim")
                check_val("pattern file loads without error", True, expected=True)
            except Exception as e:
                emit(f"  [!]  crash_patterns.json load raised: {e}", "warn")
                warned += 1

            emit(f"  .  Platform: {sys.platform}, Python {sys.version.split()[0]}", "dim")
            emit("")

        if section_on("suicide"):
            emit("[ 4 ]  Stingray Suicide Detection", "head")
            is_sui, sui_reason = _is_stingray_suicide(parsed)
            emit(f"  .  _is_stingray_suicide() = {is_sui}", "dim")
            if is_sui:
                emit(f"  .  reason: {sui_reason}", "dim")
                check_val("suicide detected for scenario", is_sui, expected=True)
                if rootcause:
                    has_suicide_finding = any(
                        "suicide" in f.get("title", "").lower()
                        for f in rootcause
                    )
                    check_val("root cause contains suicide finding", has_suicide_finding, expected=True)
            else:
                is_sui_code = False
                if rootcause:
                    is_sui_code = any(
                        "suicide" in f.get("title", "").lower()
                        for f in rootcause
                    )
                if scenario.startswith("suicide_"):
                    check_val(f"scenario {scenario} should be detected as suicide",
                              is_sui, expected=True)
                else:
                    check_val(f"scenario {scenario} not flagged as suicide (correct)",
                              is_sui, expected=False)
            emit("")

        if section_on("verdict"):
            emit("[ 9 ]  Verdict Engine & Signature", "head")
            try:
                _pat = pattern if 'pattern' in dir() and pattern else None
                _all_p = all_p if 'all_p' in dir() and all_p else []
                v = compute_verdict(parsed, rootcause or [], mods or {}, _pat,
                                   _all_p, None)
                emit(f"  .  verdict:   {v['verdict']}", "dim")
                emit(f"  .  title:     {v['title'][:60]}", "dim")
                emit(f"  .  confidence: {v['confidence']}", "dim")
                emit(f"  .  signature: {v['signature']}", "dim")
                emit(f"  .  crash_mod: {v['crash_module']} +0x{v['crash_offset']:X}", "dim")
                check_val("verdict is a valid type",
                          v['verdict'] in ("SUICIDE", "GPU", "MOD", "GAME_BUG", "INCONCLUSIVE"),
                          expected=True)
                check_val("signature starts with a valid prefix",
                          any(v['signature'].startswith(p) for p in ("SUI-", "GPU-", "MOD-", "BUG-", "UNK-")),
                          expected=True)
                check_val("signature is 12 chars (PREFIX-8hex)",
                          len(v['signature']), expected=12)
                check_val("verdict has actions list",
                          isinstance(v.get('actions'), list) and len(v['actions']) >= 1,
                          expected=True)
            except Exception as e:
                emit(f"  [FAIL]  compute_verdict() raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("threads"):
            emit("[ 11 ]  Thread Analysis", "head")
            try:
                threads = check("analyse_threads()", analyse_threads, parsed)
                if threads is not None:
                    check_val("analyse_threads returns list", isinstance(threads, list), expected=True)
                    check_val("thread count matches parsed",
                              len(threads), expected=len(parsed.get("threads", [])))
                    if parsed.get("exception"):
                        crash_tid = parsed["exception"].get("thread_id")
                        if threads and crash_tid:
                            crash_thread = next((t for t in threads if t.get("tid") == crash_tid), None)
                            if crash_thread:
                                check_val("crash thread marked is_crashed",
                                          crash_thread.get("is_crashed"), expected=True)
                    purposes = set(t.get("purpose", "") for t in threads if t.get("purpose"))
                    if purposes:
                        emit(f"  .  Thread purposes found: {purposes}", "dim")
            except Exception as e:
                emit(f"  [FAIL]  thread analysis raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("callchain"):
            emit("[ 12 ]  Call Chain Reconstruction", "head")
            try:
                chain = check("_reconstruct_call_chain()", _reconstruct_call_chain, parsed, 12)
                if chain is not None:
                    check_val("call chain returns list", isinstance(chain, list), expected=True)
                    unwind = parsed.get("_stack_unwind", {})
                    emit(f"  .  chain length: {len(chain)}", "dim")
                    emit(f"  .  pdata_modules: {unwind.get('pdata_modules', 0)}/{unwind.get('total_modules', 0)}", "dim")
                    emit(f"  .  pdata_confirmed: {unwind.get('pdata_confirmed', 0)}", "dim")
                    emit(f"  .  heuristic: {unwind.get('heuristic', 0)}", "dim")
            except Exception as e:
                emit(f"  [FAIL]  call chain raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("nullregs"):
            emit("[ 13 ]  Null Register Analysis", "head")
            try:
                null_info = check("_null_registers_at_crash()", _null_registers_at_crash, parsed)
                if null_info:
                    null_count = len(null_info.get("null", {}))
                    near_count = len(null_info.get("near_null", {}))
                    emit(f"  .  null registers: {null_count}", "dim")
                    emit(f"  .  near-null registers: {near_count}", "dim")
                    if null_count > 0:
                        emit(f"  .  null: {list(null_info['null'].keys())}", "dim")
                    check_val("null_info has 'null' key", "null" in null_info, expected=True)
                    check_val("null_info has 'near_null' key", "near_null" in null_info, expected=True)
            except Exception as e:
                emit(f"  [FAIL]  null register analysis raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("instruction"):
            emit("[ 14 ]  Instruction Decoder", "head")
            try:
                test_cases = [
                    (b"\x8b\x5a\x04", "MOV EBX, [RDX+0x4]"),
                    (b"\xc7\x04\x25\x00\x00\x00\x00\x00\x00\x00\x00", "MOV [0x0], imm32 (suicide)"),
                    (b"\xcc", "INT3 (suicide)"),
                    (b"\x0f\x0b", "UD2 (suicide)"),
                    (b"\x48\x89\x04\x25\x00\x00\x00\x00", "MOV [0x0], RAX (suicide SIB)"),
                ]
                for bytes_in, expected_desc in test_cases:
                    try:
                        result = decode_crash_instruction(bytes_in, 0x1000)
                        check_val(f"decode {expected_desc}",
                                  result is not None and "instruction" in result,
                                  expected=True)
                        if result:
                            emit(f"  .  {bytes_in.hex()} -> {result['instruction'][:50]}", "dim")
                    except Exception as e:
                        emit(f"  [FAIL]  decode {expected_desc}: {e}", "fail")
                        failed += 1
            except Exception as e:
                emit(f"  [FAIL]  instruction decoder test raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("dred"):
            emit("[ 15 ]  DRED GPU Log Parser", "head")
            try:
                import tempfile, os
                dred_log = tempfile.NamedTemporaryFile(mode='w', suffix='_dred.txt', delete=False)
                dred_log.write("Device removed, reason: DXGI_ERROR_DEVICE_HUNG (887a0006).\n")
                dred_log.write("Queue: 0, last crumb: 0=5. Crumb count=10, Context count=2\n")
                dred_log.write("\tCrumb: 0 | 3\n")
                dred_log.write("\tCrumb: 1 | 15\n")
                dred_log.write("\tCrumb: 2 | 4\n")
                dred_log.write("\tCrumb: 3 | 6\n")
                dred_log.write("\tCrumb: 4 | 12\n")
                dred_log.write("\tCrumb: 5 | 3\n")
                dred_log.write("\tCrumb: 6 | 4\n")
                dred_log.write("\tCrumb: 7 | 17\n")
                dred_log.write("\tCrumb: 8 | 6\n")
                dred_log.write("\tCrumb: 9 | 4\n")
                dred_log.write("DRED page fault address 0000000000000000 (ambiguous)\n")
                dred_log.close()

                parsed_dred = check("parse_dred_log()", parse_dred_log, dred_log.name)
                if parsed_dred:
                    check_val("DRED has removal_reason_code",
                              "removal_reason_code" in parsed_dred, expected=True)
                    check_val("DRED reason is DEVICE_HUNG",
                              parsed_dred.get("removal_reason_code"), expected="0x887A0006")
                    check_val("DRED has queues",
                              len(parsed_dred.get("queues", [])) >= 1, expected=True)

                    verdict_dred = check("assess_dred()", assess_dred, parsed_dred)
                    if verdict_dred:
                        check_val("DRED verdict has reason_name",
                                  "reason_name" in verdict_dred, expected=True)
                        check_val("DRED verdict has culprit_summary",
                                  "culprit_summary" in verdict_dred, expected=True)
                        emit(f"  .  reason: {verdict_dred.get('reason_name')}", "dim")
                        emit(f"  .  culprit_conf: {verdict_dred.get('culprit_conf')}", "dim")

                os.unlink(dred_log.name)

                dred_log2 = tempfile.NamedTemporaryFile(mode='w', suffix='_dred.txt', delete=False)
                dred_log2.write("Device removed, reason: DXGI_ERROR_DEVICE_REMOVED (887a0005).\n")
                dred_log2.write("Failed to get DRED breadcrumbs: 887a0004.\n")
                dred_log2.write("Failed to get DRED page fault output: 887a0004.\n")
                dred_log2.close()

                parsed_dred2 = check("parse_dred_log() (no breadcrumbs)", parse_dred_log, dred_log2.name)
                if parsed_dred2:
                    check_val("DRED has dred_api_errors",
                              "dred_api_errors" in parsed_dred2, expected=True)
                    if "dred_api_errors" in parsed_dred2:
                        check_val("DRED API errors count",
                                  len(parsed_dred2["dred_api_errors"]), expected=2)

                os.unlink(dred_log2.name)

            except Exception as e:
                emit(f"  [FAIL]  DRED test raised: {e}", "fail")
                failed += 1
            emit("")

        if not compact:
            emit("-" * 70, "dim")
            total = passed + failed + warned
            tag = "ok" if failed == 0 else "fail"
            emit(f"  Results: {passed} passed  |  {failed} failed  |  {warned} warnings  |  {total} total", tag)
            if failed == 0:
                emit("  All tests passed.", "ok")
            else:
                emit(f"  {failed} test(s) failed - see above for details.", "fail")
            emit("-" * 70, "dim")
        else:
            tag = "ok" if failed == 0 else "fail"
            emit(f"  -> {passed} passed, {failed} failed, {warned} warnings", tag)
            emit("")

        return (passed, failed)

    def _debugger_apply(self, scenario: str):
        try:
            parsed = self._make_synthetic_parsed(scenario)
            rootcause = assess_root_cause(parsed)
            decoded_instr = None
            mods = detect_mods(parsed)
            pattern = _match_patterns(parsed, decoded_instr, mods, rootcause)
            all_patterns = _match_all_patterns(parsed, decoded_instr, mods, rootcause)
            verdict_info = compute_verdict(parsed, rootcause, mods, pattern,
                                           all_patterns, decoded_instr)

            self._hide_drop_zone()
            self._display_results(parsed, rootcause, mods, pattern, all_patterns,
                                  verdict_info, decoded_instr)
            self._status(f"[DEBUG] Applied scenario: {scenario}", busy=False)
        except Exception as e:
            import traceback
            messagebox.showerror("Debugger Error",
                                 f"Failed to apply scenario:\n{e}\n\n{traceback.format_exc()[-800:]}")


    def _status(self, msg: str, busy: bool = False):
        self._status_var.set(msg)
        if busy:
            self._prog.start(12)
        else:
            self._prog.stop()

if __name__ == "__main__":
    app = CrashAnalyzerUI()
    app.mainloop()
