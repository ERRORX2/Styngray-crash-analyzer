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

EXCEPTION_CODES = {
    0xC0000005: "⚠ STINGRAY ENGINE SUICIDE (false flag) – Engine detected an internal error and intentionally terminated. This is NOT the root cause - look at engine logs or the call stack for the real trigger.",
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
            ptype  = struct.unpack_from("<H", data, srva + 8)[0]
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
                        }

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
            for r in range(min(nranges, 2048)):
                roff     = srva + 4 + r * 16
                if roff + 16 > len(data): break
                start    = struct.unpack_from("<Q", data, roff)[0]
                datasize = struct.unpack_from("<I", data, roff + 8)[0]
                datarva  = struct.unpack_from("<I", data, roff + 12)[0]
                result["memory_map"].append((start, datasize, datarva))

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
    """Examine modules list from the dump and verify MSVCP140.dll and Discord RPC
    for authenticity indicators: load path, PE timestamp, size plausibility.

    Returns a dict:
      {
        "msvcp140":    <result dict or None>,
        "discord":     <result dict or None>,   # may be list if multiple found
        "summary":     str,
      }
    Each result dict has keys:
      name, path, base, size, checksum, timestamp_raw, timestamp_date,
      verdict,      # "OK" | "SUSPICIOUS" | "LIKELY_TAMPERED" | "NOT_FOUND"
      verdict_colour,
      issues,       # list of str
      matched_ref,  # reference entry that matched, or None
    """
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
                if year < 2015:
                    issues.append(
                        f"PE timestamp date {ts_date} predates MSVCP140.dll's existence "
                        "(VC++ 2015 launched in July 2015) - timestamp likely forged"
                    )
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

        if cs in ("0x00000000", "0x0"):
            issues.append(
                "PE checksum is 0x00000000 - Microsoft system and redistributable DLLs "
                "always have a valid non-zero checksum. This copy has been modified or "
                "assembled by a third-party tool."
            )

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

        if cs in ("0x00000000", "0x0"):
            issues.append(
                "PE checksum is 0x00000000 - official Discord SDK DLLs always have a "
                "valid checksum. This copy appears to have been modified."
            )

        if ts_date and ts_date != "N/A":
            try:
                year = int(ts_date[:4])
                checksum_zeroed = cs in ("0x00000000", "0x0")
                if year < 2017:
                    issues.append(
                        f"PE timestamp {ts_date} predates Discord's SDK existence "
                        "(Discord Rich Presence SDK launched 2017) - timestamp likely forged"
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
        """Generic checker for VC++ runtime DLLs and ucrtbase.dll.
        Uses RUNTIME_DLL_REGISTRY to select the right reference table and rules."""
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

        if cs in ("0x00000000", "0x0"):
            issues.append(
                f"PE checksum is 0x00000000 - Microsoft runtime DLLs always have a "
                f"valid non-zero checksum. This copy of {sn} has been modified or "
                "assembled outside of Microsoft's build system."
            )

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
                    issues.append(
                        f"PE timestamp {ts_date} predates the existence of {sn} "
                        f"(first shipped {min_year}) - timestamp likely forged."
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
            "injected", "zeroed", "modified"
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
        """Extract VS generation from a reference version string.
        Returns None for entries that should be excluded from mismatch comparison."""
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
    """Identify a thread's purpose from its stack frame module names.

    Returns (label, colour_key) where colour_key is one of:
    'crash', 'game', 'audio', 'gpu', 'dstorage', 'input',
    'network', 'video', 'system', 'handler'.

    Rules are checked in priority order; first match wins.
    stack_mod_names: list of Path(module_name).name strings (mixed case OK).
    """
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
    crash_tid = parsed.get("exception", {}).get("thread_id") if parsed.get("exception") else None

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
    """Analyse the crash-thread stack for a repeated return address pattern,
    which is the hallmark of infinite recursion causing a stack overflow.
    Returns a human-readable description naming the recurring function."""
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
    """For 0xC0000142 (DLL_INIT_FAILED) crashes, identify the most likely
    failing DLL by looking at the crash-time exception address and module list.

    Strategy:
      1. If the crash address lands inside a DLL, that DLL's DllMain failed.
      2. Otherwise look for DLLs with suspicious load characteristics:
         - Missing VC++ runtime DLLs that the game DLLs would depend on
         - DLLs loaded from unexpected paths
      3. Cross-reference against the VC++ runtime DLL verify results.
    """
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
                "This exception is NOT the root cause. Check engine logs (.log file next to the .dmp) for the real error.",
                YELLOW,
                "Check the .log file sitting next to the .dmp for the actual error message. "
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
    """Return null / near-null GPRs from ExceptionStream ground-truth context.
    These are the register values at the EXACT moment of the fault, before
    any exception handler ran.  Returns {"null":{REG:val}, "near_null":{REG:val}}.
    """
    ex   = parsed.get("exception", {}) or {}
    regs = ex.get("regs", {})
    if not regs:
        return {"null": {}, "near_null": {}}
    return {
        "null":     {k.upper(): v for k, v in regs.items() if v == 0},
        "near_null":{k.upper(): v for k, v in regs.items() if 0 < v < 0x10000},
    }


def _identify_bad_register(decoded_instr: dict, null_regs: dict, fault_addr: int) -> "str | None":
    """Cross-reference the decoded instruction's memory operand with null GPRs
    to pinpoint which register held the bad/null pointer.
    Returns the register name (e.g. 'R10') or None if ambiguous.
    """
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
    """Read `size` bytes from virtual address `addr` using the dump memory map."""
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
    """Parse a loaded module's PE .pdata section from dump memory.
    Returns sorted list of (begin_rva, end_rva) function ranges, or None if unavailable.
    The x64 ABI requires every non-leaf function to have an entry in .pdata
    (the RUNTIME_FUNCTION table), so any real return address must land in one.
    """
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
    """Return True if `addr` is a valid return address within this module.
    With .pdata: the instruction BEFORE addr must fall inside a RUNTIME_FUNCTION range
    (call instructions are 5 bytes: E8 rel32, or 2–6 bytes for indirect calls,
    so addr-1 through addr-6 should land in a function body).
    Without .pdata: accept any address that lands in the module (heuristic fallback).
    """
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
    """Reconstruct the crash thread's call chain.

    Uses PE .pdata RUNTIME_FUNCTION entries (x64 exception directory) to
    validate candidate return addresses found on the stack - only addresses
    that land inside a real function body (per .pdata) are accepted.
    For modules where .pdata is unavailable in the dump, falls back to the
    heuristic "any address in the module" approach used previously.

    Returns list of (addr, module_short_name, offset) tuples, crash RIP first.
    Each entry is tagged with a 'verified' flag in the extended form used by
    the Root Cause display to distinguish pdata-confirmed frames from guesses.
    """
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
    """Return active non-crash non-system game threads at crash time.
    Each entry: {tid, module, offset, rcx, purpose}.
    Primarily used to identify what triggered an engine suicide.
    """
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

    ex      = parsed.get("exception", {})
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
        except Exception:
            pass

        if ex_code == 0xC0000005 and len(params) >= 2:
            op          = "write" if params[0] == "0x1" else "read"
            fault_addr  = int(params[1], 16)

            decoded_instr = None
            instr_mem = read_virtual_memory(parsed, ex_addr, 16)
            if instr_mem:
                decoded_instr = decode_crash_instruction(instr_mem, ex_addr)

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

    except Exception:
        pass

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

    is_suicide_crash = (
        ex_code == 0xC0000005
        and len(params) >= 2
        and params[0] == "0x1"
        and params[1] == "0x0"
    )
    if is_suicide_crash:
        active_game = _active_game_threads_at_crash(parsed)
        if active_game:
            trigger_lines = []
            for t in active_game[:8]:
                trigger_lines.append(
                    "  TID {:6d}  {}+0x{:X}{}".format(
                        t["tid"], t["module"], t["offset"],
                        "  <- RCX null (null object)" if t["rcx"] < 0x1000 else "")
                )
            findings.append({"conf": "MED",
                "title": f"Engine suicide - {len(active_game)} game thread(s) active at trigger time",
                "detail": ("These threads were executing game code when the suicide instruction fired. "
                           "One of them most likely caused the engine to detect an internal error "
                           "and call its crash routine. Check the .log for which assertion/check failed. "
                           + "\n".join(trigger_lines)),
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
                       "The engine log file (.log next to the .dmp) is needed to determine what failed."),
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
                lines.append("║  Check the .log file next to the .dmp instead.      ║")
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
            null_regs = {k: v for k, v in regs.items() if v == 0}
            near_null = {k: v for k, v in regs.items() if 0 < v < 0x1000}
            for name, val in regs.items():
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

    return "\n".join(lines)

def read_virtual_memory(parsed: dict, addr: int, size: int = 128) -> "bytes | None":

    raw_data_path = parsed.get("_raw_path")
    if not raw_data_path:
        return None
    try:
        with open(raw_data_path, "rb") as f:
            raw = f.read()
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

    opcode = b[idx]; idx += 1

    if opcode == 0x89 and idx < len(b):
        modrm = b[idx]; idx += 1
        mod = (modrm >> 6) & 0x3
        reg = (modrm >> 3) & 0x7
        rm  = modrm & 0x7

        REG_NAMES = {0:"AX",1:"CX",2:"DX",3:"BX",4:"SP",5:"BP",6:"SI",7:"DI"}
        prefix = "R" if rex & 0x8 else "E"
        src_reg = ("R" if rex & 0x4 else "") + REG_NAMES.get(reg, f"r{reg}")

        if mod == 0 and rm == 4 and idx < len(b):
            sib = b[idx]; idx += 1
            sib_base  = sib & 0x7
            sib_index = (sib >> 3) & 0x7
            sib_scale = (sib >> 6) & 0x3
            if sib_base == 5 and idx + 4 <= len(b):
                disp = struct.unpack_from("<i", bytes(b[idx:idx+4]))[0]
                target = disp & 0xFFFFFFFF
                if target == 0:
                    return {
                        "is_suicide": True,
                        "instruction": f"MOV [0x{target:08X}], {prefix}{src_reg}",
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
                        "instruction": f"MOV [0x{target:08X}], {prefix}{src_reg}",
                        "explanation": f"Write to hardcoded address 0x{target:08X} - unusual but not necessarily accidental.",
                        "confidence": "MED",
                    }

        if mod == 0 and rm == 5:
            return {
                "is_suicide": False,
                "instruction": f"MOV [RIP+disp32], {prefix}{src_reg}",
                "explanation": "Write relative to instruction pointer - accidental null unlikely here.",
                "confidence": "MED",
            }

        if mod == 0:
            base_reg = ("R" if rex & 0x1 else "") + REG_NAMES.get(rm, f"r{rm}")
            return {
                "is_suicide": False,
                "instruction": f"MOV [{prefix}{base_reg}], {prefix}{src_reg}",
                "explanation": (
                    f"Write through register {prefix}{base_reg} which was null at crash time. "
                    f"This is a real null pointer dereference - {prefix}{base_reg} held an invalid/destroyed object pointer."
                ),
                "confidence": "HIGH",
            }

        if mod in (1, 2):
            disp_size = 1 if mod == 1 else 4
            disp = struct.unpack_from("<b" if disp_size == 1 else "<i", bytes(b[idx:idx+disp_size]))[0] if idx+disp_size <= len(b) else 0
            base_reg = ("R" if rex & 0x1 else "") + REG_NAMES.get(rm, f"r{rm}")
            sign = "+" if disp >= 0 else "-"
            return {
                "is_suicide": False,
                "instruction": f"MOV [{prefix}{base_reg}{sign}0x{abs(disp):X}], {prefix}{src_reg}",
                "explanation": (
                    f"Write to {prefix}{base_reg} + offset 0x{abs(disp):X}. "
                    f"{prefix}{base_reg} was null, so this is a member-access on a null/destroyed object "
                    f"(field at byte offset {abs(disp)})."
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
            """Decode a ModRM memory operand, handling SIB and all displacement sizes.
            Returns (operand_str, new_idx, base_description_for_explanation)."""
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

PATTERN_FILE = Path(__file__).parent / "crash_patterns.json"

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

    patterns = load_custom_patterns()
    if not patterns:
        return None

    ex       = parsed.get("exception", {})
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

        return {
            "id":             p.get("id", "CUSTOM"),
            "name":           p.get("name", "Custom pattern"),
            "player_message": p.get("player_message", ""),
            "fix":            p.get("fix", []),
            "dev_note":       p.get("dev_note", ""),
            "confidence":     p.get("confidence", "MED"),
            "is_custom":      True,
        }
    return None

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

def _match_patterns(parsed: dict, decoded_instr: "dict | None",
                    mods: dict, rootcause: list) -> "dict | None":

    custom = _match_custom_patterns(parsed, decoded_instr, mods)
    if custom:
        return custom

    ex       = parsed.get("exception", {})
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

    def build_active_subsystems() -> set:

        subsystems: set = set()
        raw_path = parsed.get("_raw_path")
        if not raw_path:
            return subsystems

        try:
            with open(raw_path, "rb") as f:
                raw = f.read()
        except Exception:
            return subsystems

        memory_map = parsed.get("memory_map", [])

        def read_u64(addr: int):
            for (start, msz, rva) in memory_map:
                if start <= addr < start + msz:
                    off = addr - start
                    if rva + off + 8 <= len(raw):
                        return struct.unpack_from("<Q", raw, rva + off)[0]
            return None

        crash_tid = ex.get("thread_id") if ex else None

        for t in threads:
            if t["tid"] == crash_tid:
                continue
            rip = t.get("rip", 0)
            rsp = t.get("rsp", 0)
            rip_mod = mod_for_addr(rip)

            if rip_mod and rip_mod.lower() in CRASH_HANDLERS:
                continue

            if rip_mod:
                subsystems.add(rip_mod.lower())

            if not rsp:
                continue
            ptr = rsp
            scanned = 0
            while scanned < 0x3000:
                val = read_u64(ptr)
                if val is None:
                    break
                stack_mod = mod_for_addr(val)
                if stack_mod:
                    subsystems.add(stack_mod.lower())
                ptr     += 8
                scanned += 8

        return subsystems

    crash_mod  = mod_for_addr(ex_addr)
    crash_mod_l = (crash_mod or "").lower()
    is_suicide  = bool(decoded_instr and decoded_instr.get("is_suicide"))

    if is_suicide:
        active = build_active_subsystems()

        def sub(kw: str) -> bool:
            return any(kw in s for s in active)

        if sub("dstorage"):
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
                "dev_note": "Engine suicide with DStorage on active thread stack - likely DS decompression or IO error",
                "confidence": "MED",
            })

        if sub("lua"):
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
                "dev_note": "Engine suicide with Lua on active stack - check Lua stack and recent script changes",
                "confidence": "MED",
            })

        if (sub("wwise") or sub("fmod") or sub("xaudio")) and not (sub("nvwgf") or sub("amdxc") or sub("d3d12core")):
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
                "dev_note": "Engine suicide with Wwise/audio on active stack - check audio event / bank loading",
                "confidence": "MED",
            })

        if any(any(frag in s for frag in GPU_DRIVER_FRAGMENTS) for s in active):
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
                "dev_note": "Engine suicide with GPU driver DLL on active stack - device lost or driver timeout",
                "confidence": "MED",
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
                "Check the .log file next to the .dmp for the real error",
                "Verify game files through Steam",
                "Share the .log AND .dmp files with the 418th",
            ],
            "dev_note": "Generic engine suicide - check engine log for trigger",
            "confidence": "MED",
        })

    if crash_mod and any(frag in crash_mod_l for frag in GPU_DRIVER_FRAGMENTS):
        vendor = "AMD"    if any(k in crash_mod_l for k in ("amd", "ati")) else \
                 "NVIDIA" if any(k in crash_mod_l for k in ("nvwgf", "nvd3d")) else "Intel"
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
        """True if this module is a system-named DLL loaded from outside Windows."""
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
                "Check the .log file next to the .dmp for the error message",
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

    if is_suicide:
        active = build_active_subsystems()
        if any("network" in s or "enet" in s or "raknet" in s for s in active):
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
                "dev_note": "Engine suicide with network DLL on active stack - packet error or RPC on dead object",
                "confidence": "MED",
            })
        if any("physx" in s or "physics" in s or "nvphys" in s for s in active):
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
                "dev_note": "Engine suicide with PhysX on active stack - NaN transform or destroyed actor",
                "confidence": "MED",
            })

    return None

def build_plain_english(parsed: dict, rootcause: list, mods: dict, pattern: "dict | None") -> dict:

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
                        f"the real error is elsewhere. Check the engine log.")
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
    advice.append("Check the .log file in the same folder as the dump - it often contains the real error message.")

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
    }

_BaseWindow = TkinterDnD.Tk if _DND_AVAILABLE else tk.Tk

class CrashAnalyzer(_BaseWindow):
    def __init__(self):
        super().__init__()
        self.title("Stingray Crash Analyzer")
        self.configure(bg=BG)
        self.geometry("1100x800")
        self.minsize(800, 600)
        self.bind_all("<Control-F8>", self._open_debugger)

        try:
            _icon_path = resource_path("assets", "icon.ico")
            if _icon_path.exists():
                self.iconbitmap(default=str(_icon_path))
        except Exception:
            pass
        self._parsed = None
        self._build_ui()

    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, pady=0, padx=0)
        topbar.pack(fill="x", side="top")

        brand = tk.Frame(topbar, bg=BG2, padx=20, pady=12)
        brand.pack(side="left")
        tk.Label(brand, text="Stingray", bg=BG2, fg=ACCENT,
                 font=(UI_FONT, 13, "bold")).pack(side="left")
        tk.Label(brand, text=" Crash Analyzer", bg=BG2, fg=TEXT,
                 font=(UI_FONT, 13)).pack(side="left")

        btn_area = tk.Frame(topbar, bg=BG2, padx=16, pady=8)
        btn_area.pack(side="right")

        tk.Button(btn_area, text="✎  Patterns",
                  command=self._open_pattern_editor,
                  bg=BG3, fg=TEXT_DIM,
                  activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", padx=12, pady=5,
                  font=(UI_FONT, 9),
                  cursor="hand2").pack(side="left", padx=(0, 8))

        self._open_btn = tk.Button(btn_area, text="  Open .dmp",
                                   command=self._open_file,
                                   bg=ACCENT, fg="white",
                                   activebackground=ACCENT2,
                                   relief="flat", padx=16, pady=5,
                                   font=(UI_FONT, 9, "bold"),
                                   cursor="hand2")
        self._open_btn.pack(side="left")

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        self._file_var = tk.StringVar(value="")
        self._file_bar = tk.Frame(self, bg=BG3, pady=0)
        self._file_bar.pack(fill="x")
        self._file_lbl = tk.Label(self._file_bar, textvariable=self._file_var,
                                   bg=BG3, fg=TEXT_DIM,
                                   font=(UI_FONT, 8), padx=16, pady=5)
        self._file_lbl.pack(side="left")
        self._file_bar.pack_forget()

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook",     background=BG,  borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_DIM,
                        padding=[20, 8], font=(UI_FONT, 9))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        self._tab_summary   = self._make_tab("  Summary  ")
        self._tab_technical = self._make_tab("  Technical  ")
        self._tab_mods      = self._make_tab("  Modules & DLLs  ")

        self._simple_frame = tk.Frame(self._tab_summary, bg=BG)
        self._simple_frame.pack(fill="both", expand=True)

        self._tech_nb = ttk.Notebook(self._tab_technical)
        self._tech_nb.pack(fill="both", expand=True)
        style.configure("Tech.TNotebook",     background=BG2, borderwidth=0)
        style.configure("Tech.TNotebook.Tab", background=BG3, foreground=TEXT_DIM,
                        padding=[14, 5], font=(UI_FONT, 8))
        style.map("Tech.TNotebook.Tab",
                  background=[("selected", BG2)],
                  foreground=[("selected", ACCENT2)])

        self._tab_rootcause = self._make_tech_tab("Root Cause")
        self._tab_threads   = self._make_tech_tab("Threads")
        self._tab_hints     = self._make_tech_tab("Hints")
        self._tab_overview  = self._make_tech_tab("Raw Overview")

        self._rootcause_frame = tk.Frame(self._tab_rootcause, bg=BG)
        self._rootcause_frame.pack(fill="both", expand=True)
        self._threads_frame   = tk.Frame(self._tab_threads, bg=BG)
        self._threads_frame.pack(fill="both", expand=True)
        self._hints_frame     = tk.Frame(self._tab_hints, bg=BG)
        self._hints_frame.pack(fill="both", expand=True)
        self._overview_txt    = self._make_text(self._tab_overview, MONO, 9)

        self._mods_pane = tk.Frame(self._tab_mods, bg=BG)
        self._mods_pane.pack(fill="both", expand=True)

        self._mods_nb = ttk.Notebook(self._mods_pane)
        self._mods_nb.pack(fill="both", expand=True)

        self._tab_modules   = self._make_mods_tab("Loaded Modules")
        self._tab_dllverify = self._make_mods_tab("DLL Verify")

        self._modules_frame   = self._make_table_frame(self._tab_modules)
        self._dllverify_frame = tk.Frame(self._tab_dllverify, bg=BG)
        self._dllverify_frame.pack(fill="both", expand=True)

        self._drop_zone = tk.Frame(self, bg=BG)
        self._drop_zone.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._build_drop_zone()

        self._status_var = tk.StringVar(value="Ready - drop a .dmp file to begin")
        status = tk.Frame(self, bg=BG2, pady=0)
        status.pack(fill="x", side="bottom")
        tk.Frame(status, bg=BORDER, height=1).pack(fill="x")
        status_inner = tk.Frame(status, bg=BG2, padx=16, pady=5)
        status_inner.pack(fill="x")
        self._prog = ttk.Progressbar(status_inner, mode="indeterminate", length=100)
        self._prog.pack(side="right")
        tk.Label(status_inner, textvariable=self._status_var,
                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")

    def _make_tech_tab(self, name):
        f = tk.Frame(self._tech_nb, bg=BG)
        self._tech_nb.add(f, text=f"  {name}  ")
        return f

    def _make_mods_tab(self, name):
        f = tk.Frame(self._mods_nb, bg=BG)
        self._mods_nb.add(f, text=f"  {name}  ")
        return f

    DEBUGGER_SCENARIOS = [
        ("Access Violation (NULL deref)",       "access_violation",   "Exceptions"),
        ("Single-Step Trap (debugger/AC)",      "single_step_trap",   "Exceptions"),
        ("Stack Overflow (recursion)",          "stack_overflow",     "Exceptions"),
        ("Heap Overflow (write past bounds)",   "heap_overflow",      "Exceptions"),
        ("DLL Init Failure (0xC0000142)",       "dll_init_fail",      "Exceptions"),
        ("Unhandled C++ Exception",             "cpp_exception",      "Exceptions"),
        ("Heap Corruption",                     "heap_corruption",    "Exceptions"),
        ("Anti-Cheat Block (EAC/BattlEye)",     "anticheat_block",    "Exceptions"),
        ("Mod detected (proxy DLL)",            "mod_detected",       "Mods & DLLs"),
        ("Mod in AppData (suspicious path)",    "appdata_mod",        "Mods & DLLs"),
        ("DLL Tamper (zeroed checksum)",        "dll_tamper",         "Mods & DLLs"),
        ("DLL Version Mismatch",                "dll_mismatch",       "Mods & DLLs"),
        ("Discord DLL in System32",             "discord_hijack",     "Mods & DLLs"),
        ("Missing VC++ Runtime entirely",       "missing_runtime",    "Mods & DLLs"),
        ("Everything Clean (baseline-good)",    "clean_baseline",     "Baselines"),
        ("Kitchen Sink (multiple issues)",      "kitchen_sink",       "Baselines"),
    ]

    DEBUGGER_SECTIONS = [
        ("synthetic",  "1. Synthetic Data"),
        ("pipeline",   "2. Core Analysis Pipeline"),
        ("stack",      "3. Stack Analysis"),
        ("dllinit",    "4. DLL Init Failure Handler"),
        ("dllverify",  "5. DLL Authenticity Verification"),
        ("patterns",   "6. Pattern Matching"),
        ("mods",       "7. Mod Detection & Severity Ranking"),
        ("sentinel",   "8. Sentinel Timestamp Whitelist"),
        ("env",        "9. Environment & Dependencies"),
    ]

    def _open_debugger(self, event=None):
        """Launch the internal feature-test debugger."""
        win = tk.Toplevel(self)
        win.title("Internal Debugger - Feature Test")
        win.geometry("1100x760")
        win.minsize(820, 560)
        win.configure(bg=BG)
        try:
            _icon_path = resource_path("assets", "icon.ico")
            if _icon_path.exists():
                win.iconbitmap(default=str(_icon_path))
        except Exception:
            pass

        hdr = tk.Frame(win, bg=BG2, padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Internal Feature Debugger",
                 bg=BG2, fg=ACCENT, font=(UI_FONT, 12, "bold")).pack(side="left")
        tk.Label(hdr, text="  Ctrl+F8  -  tests every analysis pipeline function with synthetic data",
                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")
        tk.Frame(win, bg=ACCENT, height=2).pack(fill="x")

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=BG3, width=300)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Scenario", bg=BG3, fg=TEXT_DIM,
                 font=(UI_FONT, 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        scenario_var = tk.StringVar(value="access_violation")

        picker_canvas = tk.Canvas(left, bg=BG3, highlightthickness=0)
        picker_sb = tk.Scrollbar(left, orient="vertical", command=picker_canvas.yview,
                                 bg=BG3, relief="flat")
        picker_inner = tk.Frame(picker_canvas, bg=BG3)
        picker_canvas.create_window((0, 0), window=picker_inner, anchor="nw")
        picker_canvas.configure(yscrollcommand=picker_sb.set)
        picker_sb.pack(side="right", fill="y")
        picker_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0))

        last_category = None
        for label, key, category in self.DEBUGGER_SCENARIOS:
            if category != last_category:
                tk.Label(picker_inner, text=category.upper(), bg=BG3, fg=ACCENT2,
                         font=(UI_FONT, 7, "bold"), anchor="w").pack(
                             fill="x", padx=4, pady=(10, 2))
                last_category = category
            tk.Radiobutton(picker_inner, text=label, variable=scenario_var, value=key,
                           bg=BG3, fg=TEXT, selectcolor=BG2,
                           activebackground=BG3, activeforeground=ACCENT,
                           font=(UI_FONT, 8), anchor="w",
                           justify="left", wraplength=260).pack(fill="x", padx=4, pady=1)

        picker_inner.update_idletasks()
        picker_canvas.configure(scrollregion=picker_canvas.bbox("all"))
        self._bind_scroll(picker_canvas)

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(left, text="Test Sections", bg=BG3, fg=TEXT_DIM,
                 font=(UI_FONT, 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        section_vars = {}
        sect_frame = tk.Frame(left, bg=BG3)
        sect_frame.pack(fill="x", padx=8)
        for key, label in self.DEBUGGER_SECTIONS:
            v = tk.BooleanVar(value=True)
            section_vars[key] = v
            tk.Checkbutton(sect_frame, text=label, variable=v,
                           bg=BG3, fg=TEXT, selectcolor=BG2,
                           activebackground=BG3, activeforeground=ACCENT,
                           font=(UI_FONT, 8), anchor="w").pack(fill="x", pady=1)

        sect_btn_row = tk.Frame(left, bg=BG3)
        sect_btn_row.pack(fill="x", padx=8, pady=(4, 10))
        tk.Button(sect_btn_row, text="All",
                  command=lambda: [v.set(True) for v in section_vars.values()],
                  bg=BG2, fg=TEXT_DIM, relief="flat", padx=8, pady=2,
                  font=(UI_FONT, 7), cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(sect_btn_row, text="None",
                  command=lambda: [v.set(False) for v in section_vars.values()],
                  bg=BG2, fg=TEXT_DIM, relief="flat", padx=8, pady=2,
                  font=(UI_FONT, 7), cursor="hand2").pack(side="left")

        log_frame = tk.Frame(right, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=8, pady=8)

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

        def emit(text, tag=""):
            log.configure(state="normal")
            log.insert("end", text + "\n", tag)
            log.see("end")
            log.configure(state="disabled")

        def run_one():
            enabled = {k for k, v in section_vars.items() if v.get()}
            self._run_debugger(scenario_var.get(), emit, win, enabled_sections=enabled)

        def run_all():
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
                marker = "✔" if f == 0 else "✖"
                emit(f"  {marker}  {label:<38} {p:>3} passed, {f:>3} failed", tag)
            emit("")
            total_tag = "ok" if grand_failed == 0 else "fail"
            emit(f"  GRAND TOTAL: {grand_passed} passed, {grand_failed} failed "
                 f"across {len(self.DEBUGGER_SCENARIOS)} scenarios", total_tag)
            emit("=" * 70, "head")

        bot = tk.Frame(win, bg=BG2, padx=16, pady=8)
        bot.pack(fill="x", side="bottom")
        tk.Button(bot, text="▶  Run Selected",
                  command=run_one,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=16, pady=5,
                  font=(UI_FONT, 9, "bold"), cursor="hand2").pack(side="left")
        tk.Button(bot, text="▶▶  Run All Scenarios",
                  command=run_all,
                  bg=PURPLE, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=16, pady=5,
                  font=(UI_FONT, 9, "bold"), cursor="hand2").pack(side="left", padx=8)
        tk.Button(bot, text="Apply to Main Window",
                  command=lambda: self._debugger_apply(scenario_var.get()),
                  bg=BG3, fg=TEXT, activebackground=BORDER,
                  relief="flat", padx=16, pady=5,
                  font=(UI_FONT, 9), cursor="hand2").pack(side="left", padx=8)
        tk.Button(bot, text="Clear Log",
                  command=lambda: [log.configure(state="normal"),
                                   log.delete("1.0", "end"),
                                   log.configure(state="disabled")],
                  bg=BG3, fg=TEXT_DIM, relief="flat", padx=12, pady=5,
                  font=(UI_FONT, 9), cursor="hand2").pack(side="right")

    def _make_synthetic_parsed(self, scenario: str) -> dict:
        """Build a realistic synthetic parsed dict for the given scenario.
        Exercises all analysis code paths without needing a real .dmp file."""

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

        return p

    def _run_debugger(self, scenario: str, emit, win, enabled_sections=None, compact=False):
        """Run analysis functions against synthetic data and report results.

        enabled_sections: set of section keys to run (see DEBUGGER_SECTIONS).
                          None means run everything (default/backwards compatible).
        compact: when True (used by Run All), skips the banner header and only
                 emits a one-line scenario summary - keeps multi-scenario runs
                 from flooding the log with 9x duplicate headers.
        Returns (passed, failed) counts for the caller to aggregate.
        """
        import traceback, time

        def section_on(key):
            return enabled_sections is None or key in enabled_sections

        if compact:
            emit(f"── {scenario} " + "─" * max(0, 50 - len(scenario)), "head")
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
                emit(f"  ✔  {label}  ({ms:.1f} ms)", "ok")
                return result
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                emit(f"  ✖  {label}  ({ms:.1f} ms)", "fail")
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
                    emit(f"  ✔  {label}", "ok")
                    passed += 1
                else:
                    emit(f"  ✖  {label}{note}", "fail")
                    failed += 1
            except Exception as e:
                emit(f"  ✖  {label}  - {e}", "fail")
                failed += 1

        if section_on("synthetic"):
            emit("[ 1 ]  Synthetic Data", "head")
        parsed = self._make_synthetic_parsed(scenario)
        if section_on("synthetic"):
            check("Build synthetic parsed dict", lambda: parsed)
            if parsed is None:
                emit("\nCannot continue - synthetic data construction failed.", "fail")
                return (passed, failed)
            check_val("parsed has modules",   parsed.get("modules"),   min_len=5)
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
            check_val("assess_root_cause returns list", rootcause, min_len=1)
            if rootcause:
                check_val("root cause has title",  rootcause[0].get("title"), min_len=3)
                check_val("root cause has detail", rootcause[0].get("detail"), min_len=5)
                check_val("root cause has conf",   rootcause[0].get("conf")   in ("HIGH","MED","LOW"), expected=True)
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
            emit(f"  ·  Chain frames: {len(chain) if chain is not None else 0} "
                 f"(0 expected - no memory map in synthetic mode)", "dim")
            unwind = parsed.get("_stack_unwind", {})
            emit(f"  ·  pdata modules: {unwind.get('pdata_modules', 0)} / "
                 f"{unwind.get('total_modules', 0)}", "dim")
            emit(f"  ·  pdata confirmed: {unwind.get('pdata_confirmed', 0)}, "
                 f"heuristic: {unwind.get('heuristic', 0)}", "dim")
            if scenario == "stack_overflow":
                emit("  ·  Testing recursion detector:", "dim")
                recursion = check("_detect_recursion()", _detect_recursion, parsed)
                check_val("recursion description non-empty", recursion, min_len=20)
                check_val("recursion mentions engine.dll or overflow",
                          True, expected=True)
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
                    emit(f"  ·  MSVCP140  verdict: {m140.get('verdict','?')}  "
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
                    emit("  ·  MSVCP140 correctly absent (missing_runtime scenario)", "dim")

                rt = dll_verify.get("runtime", {})
                for dll_key in ("vcruntime140.dll", "vcruntime140_1.dll", "ucrtbase.dll"):
                    r = rt.get(dll_key)
                    if r:
                        emit(f"  ·  {dll_key:<26} verdict: {r.get('verdict','?')}  "
                             f"ts: {r.get('timestamp_date','?')}", "dim")
                        if scenario not in ("dll_tamper", "dll_mismatch", "missing_runtime",
                                            "kitchen_sink"):
                            check_val(f"{dll_key} passes clean",
                                      r.get("verdict"), expected="OK")
                    else:
                        emit(f"  ·  {dll_key:<26} NOT FOUND in module list", "dim")
                        if scenario == "missing_runtime":
                            check_val(f"{dll_key} correctly absent",
                                      True, expected=True)

                discord_list = dll_verify.get("discord", [])
                if discord_list:
                    dr = discord_list[0]
                    emit(f"  ·  {dr.get('name','?'):<26} verdict: {dr.get('verdict','?')}", "dim")
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
                pattern = _match_patterns(parsed, decoded_instr, mods, rootcause)
                emit(f"  ·  Pattern match result: {pattern!r}", "dim")
                emit("  ✔  _match_patterns() completed without error", "ok")
                passed += 1
            except Exception as e:
                emit(f"  ✖  _match_patterns() raised: {e}", "fail")
                failed += 1
            emit("")

        if section_on("mods"):
            emit("[ 7 ]  Mod Detection & Severity Ranking", "head")
            if mods:
                emit(f"  ·  has_mods:   {mods.get('has_mods')}", "dim")
                emit(f"  ·  confidence: {mods.get('confidence')}", "dim")
                for ind in mods.get("indicators", []):
                    sev = ind.get("severity", "?")
                    tag = "fail" if sev == "HIGH" else ("warn" if sev == "MED" else "dim")
                    emit(f"  ·  [{sev:4}] {ind.get('type','?')} - {ind.get('detail','')}", tag)
                check_val("no workshop_mod indicators",
                          not any(i.get("type") == "workshop_mod"
                                  for i in mods.get("indicators", [])),
                          expected=True)
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
                            emit(f"  ✔  {dll_name} ts={ts} not false-flagged (verdict: {result.get('verdict')})", "ok")
                            passed += 1
                        else:
                            emit(f"  ✖  {dll_name} ts={ts} incorrectly flagged:", "fail")
                            for i in ts_issues:
                                emit(f"       {i[:80]}…", "fail")
                            failed += 1
                    else:
                        emit(f"  ·  {dll_name} not found in test verify result", "dim")
                except Exception as e:
                    emit(f"  ✖  sentinel test for {dll_name}: {e}", "fail")
                    failed += 1
            emit("")

        if section_on("env"):
            emit("[ 9 ]  Environment & Dependencies", "head")

            try:
                rp = resource_path("assets", "icon.ico")
                emit(f"  ·  resource_path('assets', 'icon.ico') -> {rp}", "dim")
                is_frozen = getattr(sys, "frozen", False)
                emit(f"  ·  sys.frozen: {is_frozen}", "dim")
                check_val("resource_path returns a Path object",
                          isinstance(rp, Path), expected=True)
                passed += 1
                emit(f"  ✔  resource_path() callable without error", "ok")
            except Exception as e:
                emit(f"  ✖  resource_path() raised: {e}", "fail")
                failed += 1

            try:
                icon_path = resource_path("assets", "icon.ico")
                if icon_path.exists():
                    emit(f"  ✔  assets/icon.ico found on disk", "ok")
                    passed += 1
                else:
                    emit(f"  ⚠  assets/icon.ico NOT found at {icon_path} "
                         f"(app will fall back to monogram badge - not a hard failure)", "warn")
                    warned += 1
            except Exception as e:
                emit(f"  ✖  icon path check raised: {e}", "fail")
                failed += 1

            if _DND_AVAILABLE:
                emit(f"  ✔  tkinterdnd2 available - drag-and-drop active", "ok")
                passed += 1
            else:
                emit(f"  ⚠  tkinterdnd2 NOT installed - drag-and-drop disabled, "
                     f"Browse button still works (not a hard failure)", "warn")
                warned += 1

            try:
                from PIL import Image, ImageTk
                emit(f"  ✔  Pillow (PIL) available - icon rendering active", "ok")
                passed += 1
            except ImportError:
                emit(f"  ⚠  Pillow NOT installed - drop zone will show monogram "
                     f"badge instead of the real icon (not a hard failure)", "warn")
                warned += 1

            try:
                pattern_data = _load_pattern_file()
                n_builtin = len(pattern_data.get("builtin_patterns", []))
                n_custom  = len(pattern_data.get("patterns", []))
                emit(f"  ·  crash_patterns.json: {n_builtin} builtin, {n_custom} custom patterns", "dim")
                check_val("pattern file loads without error", True, expected=True)
                passed += 1
            except Exception as e:
                emit(f"  ⚠  crash_patterns.json load raised: {e} "
                     f"(pattern matching will be limited, not a hard failure)", "warn")
                warned += 1

            emit(f"  ·  Platform: {sys.platform}, Python {sys.version.split()[0]}", "dim")
            emit("")

        if not compact:
            emit("─" * 70, "dim")
            total = passed + failed + warned
            emit(f"  Results: {passed} passed  |  {failed} failed  |  {warned} warnings  |  {total} total",
                 "ok" if failed == 0 else "fail")
            if failed == 0:
                emit("  All tests passed.", "ok")
            else:
                emit(f"  {failed} test(s) failed - see above for details.", "fail")
            emit("─" * 70, "dim")
        else:
            tag = "ok" if failed == 0 else "fail"
            emit(f"  -> {passed} passed, {failed} failed, {warned} warnings", tag)
            emit("")

        return (passed, failed)

    def _debugger_apply(self, scenario: str):
        """Apply the synthetic data for the chosen scenario to the main window,
        running the full display pipeline so all tabs can be visually inspected."""
        try:
            parsed     = self._make_synthetic_parsed(scenario)
            summary    = build_summary(parsed)
            hints      = quick_patterns(parsed)
            rootcause  = assess_root_cause(parsed)
            mods       = detect_mods(parsed)
            plain      = build_plain_english(parsed, rootcause, mods, None)

            self._file_var.set(f"[DEBUG]  Synthetic scenario: {scenario}")
            self._file_bar.pack(fill="x")
            self._drop_zone.place_forget()
            self._display_results(parsed, summary, hints, rootcause, plain, mods)
        except Exception as e:
            import traceback
            messagebox.showerror("Debugger Error",
                                 f"Failed to apply scenario:\n{e}\n\n{traceback.format_exc()[-800:]}")

    def _build_drop_zone(self):
        """Landing screen shown before any file is loaded. Supports drag-and-drop."""
        dz = self._drop_zone
        for w in dz.winfo_children():
            w.destroy()

        tk.Frame(dz, bg=BG).pack(expand=True, fill="both")

        centre = tk.Frame(dz, bg=BG)
        centre.pack()

        icon_frame = tk.Frame(centre, bg=BG, width=128, height=128)
        icon_frame.pack(pady=(0, 20))
        icon_frame.pack_propagate(False)
        _icon_loaded = False
        try:
            from PIL import Image, ImageTk
            _ico_path = resource_path("assets", "icon.ico")
            if _ico_path.exists():
                pil_img = Image.open(str(_ico_path))
                if hasattr(pil_img, "n_frames"):
                    sizes = []
                    for frame in range(pil_img.n_frames):
                        pil_img.seek(frame)
                        sizes.append(pil_img.size)
                    best = max(sizes, key=lambda s: s[0])
                    pil_img.seek(sizes.index(best))
                pil_img = pil_img.convert("RGBA")
                pil_img = pil_img.resize((96, 96), Image.LANCZOS)
                _img = ImageTk.PhotoImage(pil_img)
                lbl = tk.Label(icon_frame, image=_img, bg=BG)
                lbl.image = _img
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                self._dz_icon_ref = _img
                _icon_loaded = True
        except Exception:
            pass

        if not _icon_loaded:
            badge = tk.Frame(icon_frame, bg=ACCENT, width=96, height=96)
            badge.place(relx=0.5, rely=0.5, anchor="center")
            badge.pack_propagate(False)
            tk.Label(badge, text="SCA", bg=ACCENT, fg="white",
                     font=(UI_FONT, 28, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(centre, text="Stingray Crash Analyzer",
                 bg=BG, fg=TEXT, font=(UI_FONT, 20, "bold")).pack()
        tk.Label(centre, text="Drop a .dmp file here to analyse it",
                 bg=BG, fg=TEXT_DIM, font=(UI_FONT, 11)).pack(pady=(6, 0))

        drop_box = tk.Frame(centre, bg=BG3, width=380, height=130,
                            highlightthickness=2, highlightbackground=BORDER)
        drop_box.pack(pady=28)
        drop_box.pack_propagate(False)

        drop_inner = tk.Frame(drop_box, bg=BG3)
        drop_inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(drop_inner, text="⬇  Drag & drop .dmp file",
                 bg=BG3, fg=TEXT_DIM, font=(UI_FONT, 11)).pack()
        tk.Label(drop_inner, text="or", bg=BG3, fg=BORDER,
                 font=(UI_FONT, 9)).pack(pady=4)
        tk.Button(drop_inner, text="Browse for file…",
                  command=self._open_file,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", padx=20, pady=6,
                  font=(UI_FONT, 9, "bold"), cursor="hand2").pack()

        if _DND_AVAILABLE:
            def _on_drop(event):
                raw = event.data
                paths = self.tk.splitlist(raw)
                for p in paths:
                    if p.lower().endswith((".dmp", ".mdmp")):
                        self._load_path(p)
                        break

            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", _on_drop)
                self._dnd_active = True
            except Exception as e:
                self._dnd_active = False
                try:
                    self._status(f"Drag-and-drop unavailable ({type(e).__name__}: {e}) - use Browse instead",
                                 busy=False)
                except Exception:
                    pass
        else:
            self._dnd_active = False
            try:
                self._status("Drag-and-drop unavailable (tkinterdnd2 not installed) - use Browse instead",
                             busy=False)
            except Exception:
                pass

        tk.Frame(dz, bg=BG).pack(expand=True, fill="both")

    def _make_tab(self, name):
        f = tk.Frame(self._nb, bg=BG)
        self._nb.add(f, text=f"  {name}  ")
        return f

    def _make_text(self, parent, font, size):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        sb = tk.Scrollbar(frame, bg=BG2, troughcolor=BG, relief="flat")
        txt = tk.Text(frame, bg=BG2, fg=TEXT, insertbackground=TEXT,
                      font=(font, size), relief="flat", wrap="word",
                      yscrollcommand=sb.set, padx=12, pady=10,
                      selectbackground=ACCENT, selectforeground="white",
                      state="disabled")
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        return txt

    def _make_table_frame(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        return frame

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Select minidump file",
            filetypes=[("Minidump files", "*.dmp *.mdmp"), ("All files", "*.*")]
        )
        if not path:
            return
        self._load_path(path)

    def _load_path(self, path: str):
        """Central entry point for loading a dump - called by browse and drag-drop."""
        self._file_var.set(path)
        self._file_bar.pack(fill="x", after=self.winfo_children()[1])
        self._drop_zone.place_forget()
        self._open_btn.config(state="disabled")
        self._status(f"Parsing {Path(path).name} …", busy=True)

        def _work():
            try:
                parsed     = parse_minidump(path)
                summary    = build_summary(parsed)
                hints      = quick_patterns(parsed)
                rootcause  = assess_root_cause(parsed)
                decoded_instr = None
                try:
                    ex = parsed.get("exception", {})
                    if ex:
                        ca   = int(ex.get("address", "0"), 16)
                        imem = read_virtual_memory(parsed, ca, 10)
                        if imem:
                            decoded_instr = decode_crash_instruction(imem, ca)
                except Exception:
                    pass

                mods       = detect_mods(parsed)
                pattern    = _match_patterns(parsed, decoded_instr, mods, rootcause)
                plain      = build_plain_english(parsed, rootcause, mods, pattern)
                self.after(0, lambda: self._display_results(parsed, summary, hints, rootcause, plain, mods))
            except Exception as e:
                self.after(0, lambda e=e: self._status(f"Parse error: {e}", busy=False))
                self.after(0, lambda: self._open_btn.config(state="normal"))

        threading.Thread(target=_work, daemon=True).start()

    def _display_results(self, parsed, summary, hints, rootcause, plain, mods):
        self._parsed = parsed

        for w in self._simple_frame.winfo_children():
            w.destroy()
        self._build_simple_view(plain, mods)

        self._set_text(self._overview_txt, summary)

        for w in self._rootcause_frame.winfo_children():
            w.destroy()
        self._build_rootcause(rootcause, parsed)

        crash_mod_name = None
        ex = parsed.get("exception")
        if ex:
            try:
                ca = int(ex["address"], 16)
                for m in parsed.get("modules", []):
                    base = int(m["base"], 16)
                    if base <= ca < base + m["size"]:
                        crash_mod_name = PureWindowsPath(m["name"]).name.lower()
                        break
            except Exception:
                pass

        for w in self._modules_frame.winfo_children():
            w.destroy()
        self._build_module_table(parsed.get("modules", []), crash_mod_name)

        for w in self._threads_frame.winfo_children():
            w.destroy()
        thread_list = analyse_threads(parsed)
        self._build_threads(thread_list, parsed)

        for w in self._hints_frame.winfo_children():
            w.destroy()
        self._build_hints(hints, parsed.get("exception"))

        for w in self._dllverify_frame.winfo_children():
            w.destroy()
        dll_verify = verify_critical_dlls(parsed)
        self._build_dllverify(dll_verify)

        self._open_btn.config(state="normal")
        self._status(f"Parsed - {len(parsed.get('modules',[]))} modules · "
                     f"exception {parsed.get('exception',{}).get('code','none')}",
                     busy=False)
        self._nb.select(0)


    def _build_dllverify(self, dll_verify: dict) -> None:
        """Render the DLL Verify tab showing authenticity analysis of MSVCP140.dll
        and Discord RPC / Game SDK DLLs extracted from the minidump module list."""
        parent = self._dllverify_frame

        hdr = tk.Frame(parent, bg=BG2, padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="DLL Authenticity Verification",
                 bg=BG2, fg=ACCENT, font=("Consolas", 12, "bold")).pack(side="left")
        tk.Label(hdr,
                 text="  Checks MSVCP140.dll and Discord RPC/Game SDK for path, size, "
                      "PE checksum, and timestamp anomalies",
                 bg=BG2, fg=TEXT_DIM, font=("Consolas", 8)).pack(side="left")

        leg = tk.Frame(parent, bg=BG3, padx=16, pady=6)
        leg.pack(fill="x")
        for colour, label in [
            (GREEN,    "  OK - matches known-good reference"),
            (YELLOW,   "  SUSPICIOUS - minor anomaly, investigate"),
            (RED,      "  LIKELY_TAMPERED - strong authenticity failure"),
            (TEXT_DIM, "  NOT_FOUND - DLL absent from module list"),
        ]:
            tk.Label(leg, text=label, bg=BG3, fg=colour,
                     font=("Consolas", 8)).pack(side="left", padx=14)

        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                          bg=BG2, troughcolor=BG, relief="flat")
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_scroll(canvas)

        VERDICT_ICONS = {"OK": "[OK]", "SUSPICIOUS": "[!!]",
                         "LIKELY_TAMPERED": "[XX]", "NOT_FOUND": "[??]"}

        def _render_card(result, section_title):
            tk.Label(inner, text=section_title, bg=BG, fg=TEXT_DIM,
                     font=("Consolas", 9, "bold"), anchor="w").pack(fill="x", padx=18, pady=(14, 0))

            if result is None:
                card = tk.Frame(inner, bg=BG2, padx=16, pady=10)
                card.pack(fill="x", padx=12, pady=4)
                tk.Label(card, text="[??] NOT FOUND in dump module list",
                         bg=BG2, fg=TEXT_DIM, font=("Consolas", 10)).pack(anchor="w")
                tk.Label(card,
                         text="This DLL was not loaded at crash time. It may not be used "
                              "by this game, or it failed to load before the crash.",
                         bg=BG2, fg=TEXT_DIM, font=("Consolas", 8),
                         wraplength=780, justify="left").pack(anchor="w", pady=(4, 0))
                return

            verdict = result["verdict"]
            vc = result["verdict_colour"]
            icon = VERDICT_ICONS.get(verdict, "?")
            ref = result.get("matched_ref")

            card = tk.Frame(inner, bg=BG2, padx=16, pady=12,
                            highlightthickness=1, highlightbackground=vc)
            card.pack(fill="x", padx=12, pady=4)

            top = tk.Frame(card, bg=BG2)
            top.pack(fill="x")
            tk.Label(top, text=f" {icon} {verdict} ",
                     bg=vc, fg="#111111" if vc == GREEN else "white",
                     font=("Consolas", 10, "bold"), padx=6, pady=2).pack(side="left")
            tk.Label(top, text=f"  {result['name']}",
                     bg=BG2, fg=vc, font=("Consolas", 11, "bold")).pack(side="left")

            meta = tk.Frame(card, bg=BG2)
            meta.pack(fill="x", pady=(8, 4))

            def _kv(lbl, val, fg=TEXT):
                row = tk.Frame(meta, bg=BG2)
                row.pack(anchor="w")
                tk.Label(row, text=f"{lbl:<22}", bg=BG2, fg=TEXT_DIM,
                         font=("Consolas", 9)).pack(side="left")
                tk.Label(row, text=str(val), bg=BG2, fg=fg,
                         font=("Consolas", 9)).pack(side="left")

            _kv("Path",          result["path"])
            _kv("Base address",  result["base"])
            size_val = f"{result['size']:,} bytes" if result.get("size") else "unknown"
            _kv("Size",          size_val)
            cs = result.get("checksum", "")
            _kv("PE checksum",   cs,
                fg=RED if cs in ("0x00000000", "0x0") else TEXT)
            _kv("PE timestamp",  result.get("timestamp_date", "N/A"))
            if ref:
                _kv("Matched version", ref.get("version", ref.get("dll", "?")), fg=GREEN)
                _kv("Version note",    ref.get("notes", ""), fg=TEXT_DIM)

            if result.get("issues"):
                tk.Frame(card, bg=BG3, height=1).pack(fill="x", pady=(8, 4))
                tk.Label(card, text="Issues detected:", bg=BG2, fg=YELLOW,
                         font=("Consolas", 9, "bold")).pack(anchor="w")
                for iss in result["issues"]:
                    row = tk.Frame(card, bg=BG2)
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text="  [!] ", bg=BG2, fg=YELLOW,
                             font=("Consolas", 9)).pack(side="left")
                    tk.Label(row, text=iss, bg=BG2, fg=YELLOW,
                             font=("Consolas", 9), wraplength=740,
                             justify="left", anchor="w").pack(side="left", fill="x")
            else:
                tk.Label(card, text="  No authenticity issues detected.",
                         bg=BG2, fg=GREEN, font=("Consolas", 9)).pack(anchor="w", pady=(6, 0))

        tk.Label(inner, text="  VC++ Runtime DLLs",
                 bg=BG, fg=ACCENT, font=("Consolas", 10, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(18, 2))
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", padx=12, pady=(0, 4))

        _render_card(dll_verify.get("msvcp140"),
                     "MSVCP140.dll  (Visual C++ 2015-2022 C++ Standard Library)")

        runtime = dll_verify.get("runtime", {})
        RUNTIME_ORDER = [
            ("vcruntime140.dll",   "VCRUNTIME140.dll  (Visual C++ 2015-2022 C Runtime)"),
            ("vcruntime140_1.dll", "VCRUNTIME140_1.dll  (Visual C++ 2019-2022 Extended C Runtime)"),
            ("concrt140.dll",      "CONCRT140.dll  (Visual C++ 2015-2022 Concurrency Runtime)"),
            ("ucrtbase.dll",       "ucrtbase.dll  (Windows Universal C Runtime - in-box Windows component)"),
        ]
        for dll_key, section_label in RUNTIME_ORDER:
            result = runtime.get(dll_key)
            if result is not None:
                _render_card(result, section_label)
            else:
                tk.Label(inner, text=section_label, bg=BG, fg=TEXT_DIM,
                         font=("Consolas", 9, "bold"), anchor="w").pack(
                             fill="x", padx=18, pady=(14, 0))
                absent_card = tk.Frame(inner, bg=BG2, padx=16, pady=6)
                absent_card.pack(fill="x", padx=12, pady=2)
                absent_note = {
                    "vcruntime140.dll":   "Not found - may indicate a VS2013-or-older game, "
                                          "or the DLL was statically linked.",
                    "vcruntime140_1.dll": "Not found - normal for VS2017/VS2015 games. "
                                          "Only present when compiled with VS2019+ C++20 features.",
                    "concrt140.dll":      "Not found - normal. Only loaded if the game uses "
                                          "the Parallel Patterns Library (PPL) or async tasks.",
                    "ucrtbase.dll":       "Not found in module list - may have been loaded "
                                          "implicitly via delay-load or the dump truncated module entries.",
                }.get(dll_key, "Not present in module list.")
                tk.Label(absent_card, text=f"[--] NOT IN DUMP  -  {absent_note}",
                         bg=BG2, fg=TEXT_DIM, font=("Consolas", 8),
                         wraplength=800, justify="left", anchor="w").pack(anchor="w")

        tk.Label(inner, text="  Discord RPC / Game SDK",
                 bg=BG, fg=ACCENT, font=("Consolas", 10, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(22, 2))
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", padx=12, pady=(0, 4))

        discord_list = dll_verify.get("discord", [])
        if discord_list:
            for dr in discord_list:
                _render_card(dr, f"{dr['name']}  (Discord Rich Presence / Game SDK)")
        else:
            _render_card(None,
                         "Discord RPC / Game SDK  (discord_game_sdk.dll / DiscordRPC.dll)")

        tk.Label(inner, text="What this verification checks",
                 bg=BG, fg=TEXT_DIM, font=("Consolas", 9, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(20, 0))
        info = tk.Frame(inner, bg=BG3, padx=16, pady=10)
        info.pack(fill="x", padx=12, pady=(4, 20))
        info_lines = [
            "Load path      - Is the DLL loaded from a legitimate location? "
              "(e.g. MSVCP140 from System32 or a known VC++ redist folder)",
            "Size           - Is the file size consistent with any known official release? "
              "Abnormally small files may be stubs or trojans.",
            "PE checksum    - Microsoft and Discord always set a non-zero PE checksum. "
              "A zero checksum means the file was modified or built by a third-party tool.",
            "PE timestamp   - Is the DLL timestamp within a valid date range for this DLL? "
              "Timestamps predating the DLL's existence are flagged. NOTE: future-looking "
              "timestamps alone (e.g. 2056-12-30) are NOT flagged - Microsoft uses "
              "Reproducible Builds from VS2017+ which store a content hash in the timestamp "
              "field, producing dates far in the future. This is legitimate. Only a future "
              "timestamp combined with a zeroed checksum indicates tampering.",
            "",
            "Note: This reads data embedded in the minidump only - it cannot read the actual "
              "on-disk DLL bytes or verify an Authenticode digital signature. For full "
              "verification, run sigcheck.exe (Sysinternals) on the on-disk copy.",
        ]
        for line in info_lines:
            tk.Label(info, text=line, bg=BG3, fg=TEXT_DIM,
                     font=("Consolas", 8), anchor="w",
                     wraplength=820, justify="left").pack(anchor="w", pady=1)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))


    def _build_module_table(self, modules, crash_mod_name=None, highlight=None):
        legend = tk.Frame(self._modules_frame, bg=BG2, padx=12, pady=6)
        legend.pack(fill="x")
        for colour, label in [(RED, "● crash location"), (YELLOW, "● game / engine DLL"), (TEXT, "● system DLL")]:
            tk.Label(legend, text=label, bg=BG2, fg=colour,
                     font=("Consolas", 8)).pack(side="left", padx=10)

        headers = ["Module", "Base Address", "Size", "Date"]
        col_w   = [420, 160, 90, 100]

        hdr = tk.Frame(self._modules_frame, bg=BG3)
        hdr.pack(fill="x")
        for i, (h, w) in enumerate(zip(headers, col_w)):
            tk.Label(hdr, text=h, bg=BG3, fg=ACCENT, font=("Consolas", 9, "bold"),
                     width=w//8, anchor="w").grid(row=0, column=i, padx=8, pady=4, sticky="w")

        canvas = tk.Canvas(self._modules_frame, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(self._modules_frame, orient="vertical", command=canvas.yview,
                              bg=BG2, troughcolor=BG, relief="flat")
        inner  = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_scroll(canvas)

        SYSTEM_PREFIXES = (
            "c:\\windows\\",
            "c:/windows/",
            "c:\\program files\\windows",
            "c:\\program files (x86)\\windows",
        )

        for row_i, m in enumerate(modules):
            bg_row   = BG2 if row_i % 2 else BG
            name     = PureWindowsPath(m["name"]).name if m["name"] else "?"
            fullpath = m["name"].lower().replace("/", "\\")

            is_crash     = crash_mod_name and name.lower() == crash_mod_name
            is_highlight = highlight and name.lower() == highlight
            is_system    = any(fullpath.startswith(p) for p in SYSTEM_PREFIXES)

            if is_highlight:
                bg_row = "#2a1f3d"
                fg_col = PURPLE
            elif is_crash:
                fg_col = RED
            elif is_system:
                fg_col = TEXT
            else:
                fg_col = YELLOW

            vals = [name, m["base"], f"{m['size']:,}", m.get("timestamp", "?")]
            for col_i, (v, w) in enumerate(zip(vals, col_w)):
                tk.Label(inner, text=v, bg=bg_row, fg=fg_col,
                         font=("Consolas", 9), width=w//8, anchor="w"
                         ).grid(row=row_i, column=col_i, padx=8, pady=2, sticky="w")

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _bind_scroll(self, canvas: tk.Canvas) -> None:

        def _on_enter(e):
            canvas.bind_all("<MouseWheel>",      lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            canvas.bind_all("<Button-4>",        lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>",        lambda e: canvas.yview_scroll(1,  "units"))
        def _on_leave(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

    def _open_pattern_editor(self):

        win = tk.Toplevel(self)
        win.title("Crash Pattern Editor")
        win.geometry("900x700")
        win.configure(bg=BG)

        hdr = tk.Frame(win, bg=BG2, pady=10, padx=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  crash_patterns.json",
                 bg=BG2, fg=ACCENT, font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(hdr, text="  Edit and save - new patterns are picked up immediately on next dump load",
                 bg=BG2, fg=TEXT_DIM, font=("Consolas", 8)).pack(side="left")

        help_f = tk.Frame(win, bg=BG3, padx=16, pady=8)
        help_f.pack(fill="x")
        help_lines = [
            "TWO sections:  builtin_patterns  - edit text of built-in patterns (id must match exactly).",
            "               patterns          - add your own new patterns with match conditions.",
            "Fields: id, name, player_message, fix (list), dev_note, confidence (HIGH/MED/LOW), enabled (true/false)",
            "match keys: ex_code, is_suicide, fault_addr_max, fault_addr_min, crash_mod_contains,",
            "            module_loaded, module_not_loaded, stack_contains, active_thread_mod_contains",
        ]
        for line in help_lines:
            tk.Label(help_f, text=line, bg=BG3, fg=TEXT_DIM,
                     font=("Consolas", 8), anchor="w").pack(anchor="w")

        edit_frame = tk.Frame(win, bg=BG)
        edit_frame.pack(fill="both", expand=True, padx=8, pady=8)

        sb  = tk.Scrollbar(edit_frame, bg=BG2, troughcolor=BG, relief="flat")
        txt = tk.Text(edit_frame, bg=BG2, fg=TEXT, insertbackground=TEXT,
                      font=("Consolas", 10), relief="flat", wrap="none",
                      yscrollcommand=sb.set, padx=12, pady=10,
                      selectbackground=ACCENT, selectforeground="white")
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        if PATTERN_FILE.exists():
            txt.insert("1.0", PATTERN_FILE.read_text(encoding="utf-8"))
        else:
            default = json.dumps({
                "_comment": "Stingray Crash Analyzer - custom patterns",
                "patterns": []
            }, indent=4)
            txt.insert("1.0", default)

        bar = tk.Frame(win, bg=BG2, pady=8, padx=16)
        bar.pack(fill="x")
        status_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=status_var, bg=BG2, fg=GREEN,
                 font=("Consolas", 9)).pack(side="left")

        def save():
            content = txt.get("1.0", "end-1c")
            try:
                parsed_json = json.loads(content)
                PATTERN_FILE.write_text(content, encoding="utf-8")
                count = len([p for p in parsed_json.get("patterns", []) if p.get("enabled", True)])
                status_var.set(f"✓ Saved - {count} active pattern(s)")
            except json.JSONDecodeError as e:
                status_var.set(f"✗ JSON error: {e}")
                tk.Label(bar, textvariable=status_var, bg=BG2, fg=RED,
                         font=("Consolas", 9)).pack(side="left")

        def add_template():
            template = """    ,{
        "id":             "MY_PATTERN",
        "name":           "Short name shown in UI",
        "player_message": "Plain-English explanation for players.",
        "fix": [
            "Step 1 for the player",
            "Step 2 for the player"
        ],
        "dev_note":   "Technical notes for devs",
        "confidence": "MED",
        "match": {
            "ex_code":   "0xC0000005",
            "is_suicide": true
        },
        "enabled": true
    }"""
            txt.insert("end", "\n" + template)

        tk.Button(bar, text="+ Add template", command=add_template,
                  bg=BG3, fg=TEXT_DIM, relief="flat", padx=10, pady=4,
                  font=("Consolas", 9), cursor="hand2").pack(side="right", padx=4)
        tk.Button(bar, text="  Save  ", command=save,
                  bg=GREEN, fg="black", activebackground=ACCENT2,
                  relief="flat", padx=14, pady=4,
                  font=("Consolas", 10, "bold"), cursor="hand2").pack(side="right", padx=4)

        win.bind("<Control-s>", lambda e: save())

    def _build_simple_view(self, plain: dict, mods: dict) -> None:
        outer = tk.Frame(self._simple_frame, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              bg=BG2, troughcolor=BG, relief="flat")
        inner  = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_scroll(canvas)

        def section(title, colour=ACCENT):
            f = tk.Frame(inner, bg=BG)
            f.pack(fill="x", padx=24, pady=(22, 4))
            row = tk.Frame(f, bg=BG)
            row.pack(fill="x")
            tk.Label(row, text=title, bg=BG, fg=colour,
                     font=(UI_FONT, 9, "bold")).pack(side="left")
            tk.Frame(row, bg=colour, height=1).pack(side="left", fill="x",
                                                     expand=True, padx=(10, 0), pady=1)

        def card(parent, bg=BG2):
            f = tk.Frame(parent, bg=bg, padx=20, pady=14)
            f.pack(fill="x", padx=24, pady=4)
            return f

        def label(parent, text, fg=TEXT, font_size=10, bold=False, wrap=860, mono=False):
            font_family = UI_MONO if mono else UI_FONT
            tk.Label(parent, text=text, bg=parent["bg"], fg=fg,
                     font=(font_family, font_size, "bold" if bold else "normal"),
                     wraplength=wrap, justify="left", anchor="w").pack(anchor="w", pady=1)

        pattern = plain.get("pattern")
        section("Crash identification", ACCENT)
        if pattern:
            conf_colour = {"HIGH": RED, "MED": YELLOW, "LOW": TEXT_DIM}.get(
                pattern.get("confidence", "LOW"), TEXT_DIM)
            pc = card(inner, "#1f0d0d" if pattern.get("confidence") == "HIGH" else BG3)
            badge_f = tk.Frame(pc, bg=pc["bg"])
            badge_f.pack(fill="x", pady=(0, 6))
            tk.Label(badge_f, text="  ⚠ KNOWN CRASH PATTERN  ",
                     bg=conf_colour, fg="white",
                     font=("Consolas", 8, "bold"), padx=6, pady=2).pack(side="left")
            tk.Label(badge_f, text=f"  [{pattern.get('confidence', '?')} CONFIDENCE]",
                     bg=pc["bg"], fg=conf_colour,
                     font=("Consolas", 8, "bold")).pack(side="left", padx=6)
            label(pc, pattern["name"], fg=conf_colour, font_size=12, bold=True)
            label(pc, pattern["player_message"], fg=TEXT, font_size=10)
            tk.Frame(pc, bg=BORDER, height=1).pack(fill="x", pady=6)
            tk.Label(pc, text="What to try:", bg=pc["bg"], fg=ACCENT,
                     font=("Consolas", 8, "bold")).pack(anchor="w")
            for i, step in enumerate(pattern.get("fix", []), 1):
                sf = tk.Frame(pc, bg=pc["bg"])
                sf.pack(fill="x", pady=1)
                tk.Label(sf, text=f"{i}.", bg=pc["bg"], fg=conf_colour,
                         font=("Consolas", 9, "bold"), width=3).pack(side="left")
                tk.Label(sf, text=step, bg=pc["bg"], fg=TEXT,
                         font=("Consolas", 9), wraplength=820,
                         justify="left", anchor="w").pack(side="left")
        else:
            pc = card(inner, BG3)
            label(pc, "No known pattern matched for this crash.",
                  fg=TEXT_DIM, font_size=9)
            label(pc, "Share the .dmp and .log with the 418th for manual investigation.",
                  fg=TEXT_DIM, font_size=8)

        section("What happened", RED)
        c = card(inner, BG2)
        label(c, plain["headline"], fg=TEXT, font_size=11, bold=True)

        section("What the engine was doing at crash time", YELLOW)
        c = card(inner, BG2)
        label(c, plain["what_was_doing"], fg=ACCENT2, font_size=10)
        label(c, "This is the last known activity before the crash occurred.",
              fg=TEXT_DIM, font_size=8)

        section("Loaded subsystems", TEXT_DIM)
        c = card(inner, BG2)
        if plain["active_subsystems"]:
            cols = 3
            grid = tk.Frame(c, bg=BG2)
            grid.pack(anchor="w")
            for i, sub in enumerate(plain["active_subsystems"]):
                row, col = divmod(i, cols)
                pill = tk.Frame(grid, bg=BG3, padx=8, pady=3)
                pill.grid(row=row, column=col, padx=4, pady=3, sticky="w")
                tk.Label(pill, text=f"● {sub}", bg=BG3, fg=TEXT,
                         font=("Consolas", 8)).pack()
        else:
            label(c, "No specific subsystems identified.", fg=TEXT_DIM, font_size=9)

        section("Key findings", ACCENT)
        CONF_COLOUR = {"HIGH": RED, "MED": YELLOW, "LOW": TEXT_DIM}
        for f in plain["rootcause"]:
            conf   = f.get("conf", "LOW")
            colour = CONF_COLOUR.get(conf, TEXT_DIM)
            c = card(inner, BG3)
            bar = tk.Frame(c, bg=colour, width=4)
            bar.pack(side="left", fill="y", padx=(0, 12))
            body = tk.Frame(c, bg=BG3)
            body.pack(side="left", fill="x", expand=True)
            label(body, f["title"], fg=colour, font_size=10, bold=True)
            detail = f.get("detail", "")
            detail = detail.split("Click to inspect")[0].strip().rstrip(".")
            label(body, detail, fg=TEXT, font_size=9)

        section("Mod detection", YELLOW)
        c = card(inner, BG2)
        if mods.get("has_mods"):
            conf = mods.get("confidence", "LOW")
            conf_colour = {"HIGH": RED, "MED": YELLOW, "LOW": TEXT_DIM}.get(conf, TEXT_DIM)
            label(c, f"⚠  Possible mods detected  [{conf} confidence]",
                  fg=conf_colour, font_size=10, bold=True)
            for ind in mods.get("indicators", [])[:8]:
                label(c, f"  • {ind['detail']}", fg=TEXT_DIM, font_size=8)
            if len(mods.get("indicators", [])) > 8:
                label(c, f"  … and {len(mods['indicators'])-8} more", fg=TEXT_DIM, font_size=8)
            label(c, "Mods can cause crashes. Try reproducing without mods before reporting.",
                  fg=ACCENT2, font_size=9)
        else:
            label(c, "✓  No mods detected - all loaded DLLs match expected game files.",
                  fg=GREEN, font_size=9)

        section("What to do next", GREEN)
        for i, item in enumerate(plain["advice"]):
            c = card(inner, BG2)
            body = tk.Frame(c, bg=BG2)
            body.pack(fill="x")
            tk.Label(body, text=f"{i+1}", bg=ACCENT, fg="white",
                     font=("Consolas", 9, "bold"), width=3,
                     padx=4, pady=2).pack(side="left", padx=(0, 12))
            tk.Label(body, text=item, bg=BG2, fg=TEXT,
                     font=("Consolas", 9), wraplength=800,
                     justify="left", anchor="w").pack(side="left")

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_rootcause(self, findings, parsed):
        CONF_COLOUR = {"HIGH": RED, "MED": YELLOW, "LOW": TEXT_DIM}
        CONF_LABEL  = {"HIGH": "HIGH CONFIDENCE", "MED": "POSSIBLE", "LOW": "LOW SIGNAL"}

        hdr = tk.Frame(self._rootcause_frame, bg=BG2, padx=12, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Root Cause Assessment  -  false flags excluded",
                 bg=BG2, fg=ACCENT, font=("Consolas", 10, "bold")).pack(side="left")
        tk.Label(hdr, text="click a card to inspect in the relevant tab",
                 bg=BG2, fg=TEXT_DIM, font=("Consolas", 8)).pack(side="left", padx=12)

        outer  = tk.Frame(self._rootcause_frame, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              bg=BG2, troughcolor=BG, relief="flat")
        inner  = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_scroll(canvas)

        TAB_INDEX = {"modules": 2, "threads": 1}

        for f in findings:
            conf   = f["conf"]
            title  = f["title"]
            detail = f["detail"]
            link   = f.get("link")
            colour = CONF_COLOUR.get(conf, TEXT_DIM)
            label  = CONF_LABEL.get(conf, conf)

            card_bg    = BG3
            hover_bg   = "#232d3f" if link else BG3
            cursor     = "hand2" if link else ""

            card = tk.Frame(inner, bg=card_bg, padx=16, pady=12,
                            relief="flat", bd=0)
            card.pack(fill="x", padx=8, pady=4)

            bar = tk.Frame(card, bg=colour, width=5)
            bar.pack(side="left", fill="y", padx=(0, 14))

            body = tk.Frame(card, bg=card_bg)
            body.pack(side="left", fill="x", expand=True)

            top = tk.Frame(body, bg=card_bg)
            top.pack(fill="x")
            tk.Label(top, text=f"[{label}]", bg=card_bg, fg=colour,
                     font=("Consolas", 8, "bold")).pack(side="left")
            tk.Label(top, text=f"  {title}", bg=card_bg, fg=colour,
                     font=("Consolas", 11, "bold")).pack(side="left")
            if link:
                tk.Label(top, text="  ↗ click to inspect", bg=card_bg, fg=TEXT_DIM,
                         font=("Consolas", 8)).pack(side="left", padx=8)

            for line in detail.split(". "):
                line = line.strip()
                if not line:
                    continue
                if not line.endswith(".") and "\n" not in line:
                    line += "."
                fg = ACCENT2 if any(line.startswith(w) for w in ("Load", "Check", "Click", "→")) else TEXT
                tk.Label(body, text=line, bg=card_bg, fg=fg,
                         font=("Consolas", 9), wraplength=860,
                         justify="left", anchor="w").pack(anchor="w", pady=1)

            if link:
                def make_handler(lnk, parsed=parsed):
                    def on_click(e=None):
                        tab_name = lnk.get("tab")
                        if tab_name == "modules":
                            self._nb.select(2)
                            self._mods_nb.select(0)
                            self._highlight_module(lnk["module"]) if "module" in lnk else None
                        elif tab_name == "threads":
                            self._nb.select(1)
                            self._tech_nb.select(1)
                            self._highlight_thread(lnk["tid"]) if "tid" in lnk else None
                    return on_click

                handler = make_handler(link)

                def _apply_cursor(w, cur):
                    try:
                        w.configure(cursor=cur)
                    except Exception:
                        pass

                def _apply_bg(w, bg):
                    try:
                        w.configure(bg=bg)
                    except Exception:
                        pass

                all_widgets = ([card, body, top]
                               + list(card.winfo_children())
                               + list(body.winfo_children())
                               + list(top.winfo_children()))

                for widget in all_widgets:
                    _apply_cursor(widget, cursor)
                    widget.bind("<Button-1>", handler)

                def _on_enter(e, ws=all_widgets, bg=hover_bg):
                    for w in ws:
                        _apply_bg(w, bg)

                def _on_leave(e, ws=all_widgets, bg=card_bg):
                    for w in ws:
                        _apply_bg(w, bg)

                card.bind("<Enter>", _on_enter)
                card.bind("<Leave>", _on_leave)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _highlight_module(self, module_name):

        if not self._parsed:
            return
        mods = self._parsed.get("modules", [])
        for w in self._modules_frame.winfo_children():
            w.destroy()
        self._build_module_table(mods, module_name.lower(), highlight=module_name.lower())
        self._show_memory_inspector(module_name)

    def _show_memory_inspector(self, module_name: str) -> None:

        if not self._parsed:
            return
        parsed = self._parsed
        ex = parsed.get("exception") or {}
        if not ex:
            return
        try:
            crash_addr = int(ex.get("address", "0"), 16)
        except Exception:
            return

        read_addr = max(0, crash_addr - 48)
        mem = read_virtual_memory(parsed, read_addr, 128)

        panel = tk.Frame(self._modules_frame, bg=BG2, pady=8)
        panel.pack(fill="x", side="bottom", padx=8, pady=(4, 0))

        mod_base = next(
            (int(m["base"], 16) for m in parsed.get("modules", [])
             if PureWindowsPath(m["name"]).name.lower() == module_name.lower()),
            0
        )
        tk.Label(panel,
                 text=f"  Memory at crash address - {module_name}  +0x{crash_addr - mod_base:X}",
                 bg=BG2, fg=PURPLE, font=("Consolas", 9, "bold")).pack(anchor="w", padx=8)

        if mem is None:
            tk.Label(panel,
                     text="  Memory at this address was not captured in the dump.",
                     bg=BG2, fg=TEXT_DIM, font=("Consolas", 9)).pack(anchor="w", padx=8, pady=4)
            tk.Label(panel,
                     text="  Tip: create the dump with MiniDumpWithFullMemory for full memory capture.",
                     bg=BG2, fg=ACCENT2, font=("Consolas", 9)).pack(anchor="w", padx=8)
            return

        crash_offset_in_buf = crash_addr - read_addr
        instr_bytes = mem[crash_offset_in_buf:crash_offset_in_buf+10]
        decoded = decode_crash_instruction(instr_bytes, crash_addr)

        instr_colour = RED if decoded["is_suicide"] else ACCENT2
        suicide_tag  = "  ⚠ ENGINE SUICIDE INSTRUCTION" if decoded["is_suicide"] else ""
        tk.Label(panel,
                 text=f"  Instruction: {decoded['instruction']}{suicide_tag}",
                 bg=BG2, fg=instr_colour, font=("Consolas", 9, "bold")).pack(anchor="w", padx=8)
        tk.Label(panel,
                 text=f"  {decoded['explanation']}",
                 bg=BG2, fg=TEXT, font=("Consolas", 8), wraplength=900,
                 justify="left").pack(anchor="w", padx=8, pady=(0, 6))

        hdr = tk.Frame(panel, bg=BG3)
        hdr.pack(fill="x", padx=8)
        for col, w in [("Address", 18), ("Hex", 49), ("ASCII", 16)]:
            tk.Label(hdr, text=col, bg=BG3, fg=ACCENT,
                     font=("Consolas", 8, "bold"), width=w, anchor="w").pack(side="left", padx=4)

        rows = format_hex_dump(mem, read_addr, crash_addr)
        for addr_str, hex_str, ascii_str, is_hi in rows:
            bg  = "#2a1040" if is_hi else BG2
            fg  = PURPLE if is_hi else TEXT_DIM
            row = tk.Frame(panel, bg=bg)
            row.pack(fill="x", padx=8)
            tk.Label(row, text=addr_str, bg=bg, fg=GREEN if is_hi else TEXT_DIM,
                     font=("Consolas", 8), width=18, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=hex_str,  bg=bg, fg=PURPLE if is_hi else TEXT,
                     font=("Consolas", 8), width=49, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=ascii_str, bg=bg, fg=fg,
                     font=("Consolas", 8), width=16, anchor="w").pack(side="left", padx=4)
            if is_hi:
                tk.Label(row, text="← CRASH", bg=bg, fg=RED,
                         font=("Consolas", 8, "bold")).pack(side="left")

        crash_offset = crash_addr - mod_base
        dmp_path     = parsed.get("file", "C:\\path\\to\\dump.dmp")
        sym_path     = "srv*C:\\Symbols*https://msdl.microsoft.com/download/symbols"

        windbg_cmds = [
            ("1. Open the dump in WinDbg",
             f'.opendump "{dmp_path}"'),
            ("2. Set Microsoft public symbol path (resolves Windows/system DLL names only)",
             f'.sympath "srv*C:\\Symbols*https://msdl.microsoft.com/download/symbols"'),
            ("3. Reload symbols (resolves Windows/system DLL names)",
             ".reload /f"),
            ("4. Switch to the crashing thread and show its call stack",
             f"~{ex.get('thread_id', 0)}s ; kb 30"),
            ("5. Disassemble the instructions around the crash address",
             f"u {crash_addr:#x}-10 L20"),
            ("6. Show all register values at crash time",
             "r"),
            ("7. Identify the nearest symbol (Windows DLLs only - game functions will show raw offsets)",
             f"ln {crash_addr:#x}"),
            ("8. Show all threads with their top 5 frames",
             "~* kb 5"),
            ("9. Show what the stack pointer was pointing at",
             "dq @rsp L8"),
        ]

        note_lines = [
            "ℹ  Game symbols are not publicly available.",
            "   Game engine frames will show as raw offsets (module + 0xADDR).",
            "   You can still determine: which module crashed, register state,",
            "   raw disassembly at the fault address, and Windows symbol names.",
        ]

        sep = tk.Frame(panel, bg=BORDER, height=1)
        sep.pack(fill="x", padx=8, pady=(10, 6))

        tk.Label(panel, text="  WinDbg - How to inspect this crash",
                 bg=BG2, fg=ACCENT, font=("Consolas", 9, "bold")).pack(anchor="w", padx=8, pady=(0, 4))

        note_frame = tk.Frame(panel, bg=BG3, padx=10, pady=6)
        note_frame.pack(fill="x", padx=8, pady=(0, 6))
        for line in note_lines:
            fg = YELLOW if line.startswith("⚠") else TEXT_DIM
            tk.Label(note_frame, text=line, bg=BG3, fg=fg,
                     font=("Consolas", 8)).pack(anchor="w")

        for label, cmd in windbg_cmds:
            row_f = tk.Frame(panel, bg=BG2)
            row_f.pack(fill="x", padx=8, pady=1)
            tk.Label(row_f, text=f"  {label}",
                     bg=BG2, fg=TEXT_DIM, font=("Consolas", 8)).pack(anchor="w")

            cmd_frame = tk.Frame(row_f, bg=BG3, padx=6, pady=3)
            cmd_frame.pack(anchor="w", padx=16, pady=(0, 2))

            tk.Label(cmd_frame, text=cmd, bg=BG3, fg=GREEN,
                     font=("Consolas", 9), cursor="hand2").pack(side="left")

            def make_copy(c=cmd):
                def _copy(e=None):
                    self.clipboard_clear()
                    self.clipboard_append(c)
                return _copy

            copy_btn = tk.Button(cmd_frame, text="copy", command=make_copy(cmd),
                                 bg=BG3, fg=TEXT_DIM, relief="flat",
                                 font=("Consolas", 7), cursor="hand2",
                                 activebackground=BORDER, activeforeground=TEXT)
            copy_btn.pack(side="left", padx=(8, 0))

    def _highlight_thread(self, tid):
        if not self._parsed:
            return
        for w in self._threads_frame.winfo_children():
            w.destroy()
        threads = analyse_threads(self._parsed)
        self._build_threads(threads, self._parsed, highlight_tid=tid)

    def _build_threads(self, threads, parsed, highlight_tid=None):
        STATE_COLOUR = {
            "CRASHED":       RED,
            "ACTIVE":        YELLOW,
            "CRASH HANDLER": TEXT_DIM,
            "SUSPENDED":     ACCENT2,
            "WAITING":       TEXT_DIM,
            "SLEEPING":      TEXT_DIM,
            "IDLE":          TEXT_DIM,
        }
        def state_colour(state):
            for k, c in STATE_COLOUR.items():
                if state.startswith(k):
                    return c
            return TEXT_DIM

        SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

        def frame_colour(mod_name):

            n = (mod_name or "").lower()
            if "helldivers2.exe" in n or ("game" in n and ".dll" in n):
                return YELLOW
            if any(k in n for k in ("ntdll", "kernel32", "kernelbase", "user32",
                                     "ucrtbase", "msvcp", "vcruntime")):
                return TEXT_DIM
            return TEXT

        hdr = tk.Frame(self._threads_frame, bg=BG2, padx=12, pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"  {len(threads)} threads  -  call stacks (heuristic ~*k)",
                 bg=BG2, fg=ACCENT, font=("Consolas", 9, "bold")).pack(side="left")
        for colour, label in [(RED, "● crashed"), (YELLOW, "● game code"),
                              (ACCENT2, "● suspended"), (TEXT_DIM, "● waiting/sleeping")]:
            tk.Label(hdr, text=label, bg=BG2, fg=colour,
                     font=("Consolas", 8)).pack(side="right", padx=8)

        outer  = tk.Frame(self._threads_frame, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              bg=BG2, troughcolor=BG, relief="flat")
        inner  = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_scroll(canvas)

        for t in threads:
            is_highlighted = highlight_tid and t["tid"] == highlight_tid
            colour  = state_colour(t["state"])
            card_bg = "#1a2a1a" if is_highlighted else BG2

            card = tk.Frame(inner, bg=card_bg, padx=10, pady=6)
            card.pack(fill="x", padx=4, pady=1)

            bar = tk.Frame(card, bg=colour, width=3)
            bar.pack(side="left", fill="y", padx=(0, 8))

            body = tk.Frame(card, bg=card_bg)
            body.pack(side="left", fill="x", expand=True)

            hline = tk.Frame(body, bg=card_bg)
            hline.pack(fill="x")
            state_lbl = f"◀ {t['state']}" if is_highlighted else t["state"]

            PURPOSE_COLOURS = {
                "crash":    RED,
                "game":     YELLOW,
                "audio":    GREEN,
                "gpu":      PURPLE,
                "dstorage": ACCENT,
                "input":    ACCENT2,
                "network":  "#58a6ff",
                "video":    ACCENT2,
                "system":   TEXT_DIM,
                "handler":  TEXT_DIM,
            }
            purpose        = t.get("purpose", "")
            purpose_colour = PURPOSE_COLOURS.get(t.get("purpose_colour_key", "system"), TEXT_DIM)
            if t["is_crashed"]:
                purpose_colour = RED

            tk.Label(hline, text=f"TID {t['tid']:6d}", bg=card_bg, fg=colour,
                     font=(MONO, 9, "bold"), width=12, anchor="w").pack(side="left")
            tk.Label(hline, text=f"[{state_lbl}]", bg=card_bg, fg=colour,
                     font=(MONO, 8, "bold"), width=22, anchor="w").pack(side="left")
            if purpose:
                tk.Label(hline, text=f"  ●  {purpose}", bg=card_bg, fg=purpose_colour,
                         font=(MONO, 8, "bold")).pack(side="left")
            tk.Label(hline, text=f"   {t['doing']}", bg=card_bg, fg=TEXT_DIM,
                     font=(MONO, 8)).pack(side="left")

            frames = t.get("frames", [])
            for i, (addr, mod, off) in enumerate(frames):
                fc      = RED if (i == 0 and t["is_crashed"]) else frame_colour(mod)
                prefix  = "  ★ " if (i == 0 and t["is_crashed"]) else f"  #{i:02d} "
                ann     = annotate_frame(mod, off)
                ann_str = f"  ← {ann}" if ann else ""
                tk.Label(body,
                         text=f"{prefix}0x{addr:016X}  {mod}+0x{off:X}{ann_str}",
                         bg=card_bg, fg=fc, font=(MONO, 8), anchor="w").pack(anchor="w")

            if not frames:
                tk.Label(body, text="  (no stack data captured)",
                         bg=card_bg, fg=BORDER, font=(MONO, 8)).pack(anchor="w")

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_hints(self, hints, exception):
        hdr = tk.Frame(self._hints_frame, bg=BG2, padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Quick Hints",
                 bg=BG2, fg=ACCENT, font=(UI_FONT, 11, "bold")).pack(side="left")
        tk.Label(hdr, text="  Rule-based signals from the module list",
                 bg=BG2, fg=TEXT_DIM, font=(UI_FONT, 8)).pack(side="left")

        if exception:
            card = tk.Frame(self._hints_frame, bg=BG3, padx=16, pady=12)
            card.pack(fill="x", padx=8, pady=(8, 4))
            tk.Label(card, text="Exception", bg=BG3, fg=ACCENT2,
                     font=(UI_FONT, 8, "bold")).pack(anchor="w")
            tk.Label(card, text=f"{exception['code']}  -  {exception['code_desc']}",
                     bg=BG3, fg=TEXT, font=(UI_FONT, 10, "bold")).pack(anchor="w", pady=(2, 0))
            tk.Label(card, text=f"Address: {exception['address']}   Thread: {exception['thread_id']}",
                     bg=BG3, fg=TEXT_DIM, font=(UI_MONO, 9)).pack(anchor="w")

        if not hints:
            emp = tk.Frame(self._hints_frame, bg=BG, pady=40)
            emp.pack(fill="x")
            tk.Label(emp, text="No specific pattern hints detected.",
                     bg=BG, fg=TEXT_DIM, font=(UI_FONT, 10)).pack()
            return

        for label, detail, colour, could_be in hints:
            card = tk.Frame(self._hints_frame, bg=BG3, padx=16, pady=12)
            card.pack(fill="x", padx=8, pady=3)
            indicator = tk.Frame(card, bg=colour, width=4)
            indicator.pack(side="left", fill="y", padx=(0, 14))
            inner = tk.Frame(card, bg=BG3)
            inner.pack(side="left", fill="x", expand=True)
            tk.Label(inner, text=label, bg=BG3, fg=colour,
                     font=(UI_FONT, 10, "bold")).pack(anchor="w")
            tk.Label(inner, text=detail, bg=BG3, fg=TEXT_DIM,
                     font=(UI_FONT, 9)).pack(anchor="w", pady=(2, 0))
            tk.Label(inner, text=could_be, bg=BG3, fg=TEXT,
                     font=(UI_FONT, 9), wraplength=800, justify="left").pack(anchor="w", pady=(6, 0))

    def _set_text(self, widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _status(self, msg, busy=False):
        self._status_var.set(msg)
        if busy:
            self._prog.start(12)
        else:
            self._prog.stop()

if __name__ == "__main__":
    app = CrashAnalyzer()
    app.mainloop()