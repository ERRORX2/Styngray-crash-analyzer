import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import json
import re
import struct
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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
MONO      = "Consolas" if sys.platform == "win32" else "Courier New"

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
            osmaj  = struct.unpack_from("<I", data, srva + 16)[0]
            osmin  = struct.unpack_from("<I", data, srva + 20)[0]
            osbld  = struct.unpack_from("<I", data, srva + 24)[0]
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
                    "regs":        ex_ctx_regs,   # ground-truth registers at crash time
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
        return "MinHook (function hooking library — possible mod injection)"

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
    if has("amdxc64", "amdxc32", "amdxx64", "amdxx32", "atidxx64", "atidxx32"):
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
                    return Path(m["name"]).name, addr - base
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
        if Path(m["name"]).name.lower() == "ntdll.dll":
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
                    return m["name"], Path(m["name"]).name, rip - base
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
        if is_crashed:
            state = "CRASHED"
        elif suspend > 0:
            state = f"SUSPENDED (count={suspend})"
        elif wait_label == "NtDelayExecution" or wait_label and "sleeping" in wait_label.lower():
            state = "SLEEPING"
        elif wait_label and "idle" in wait_detail.lower() if wait_detail else False:
            state = "IDLE"
        elif wait_label:
            state = "WAITING"
        elif is_game:
            state = "ACTIVE"
        elif is_handler:
            state = "CRASH HANDLER"
        else:
            state = "WAITING"

        if is_crashed:
            doing = "Raised the crash exception - engine suicide, not the root cause"
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

        # Label thread purpose from all module names visible on the stack
        all_stack_mods = ([short_name] if short_name else []) + [mod for _, mod, _ in frames]
        purpose, purpose_colour_key = label_thread_purpose(all_stack_mods)
        # Crash thread overrides purpose regardless of stack content
        if is_crashed:
            purpose = "CRASHED"

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

def quick_patterns(parsed: dict) -> list[tuple[str, str, str, str]]:

    hints = []
    modules   = parsed.get("modules", [])
    all_names = " ".join(Path(m["name"]).name.lower() for m in modules)

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
                    n = Path(m["name"]).name.lower()
                    if n in GPU_DRIVER_DLLS:
                        crash_in_driver = (Path(m["name"]).name, GPU_DRIVER_DLLS[n], ca - base)
                    elif n in GPU_RUNTIME_DLLS:
                        crash_in_runtime = (Path(m["name"]).name, GPU_RUNTIME_DLLS[n], ca - base)
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
                    mod_name = Path(m["name"]).name.lower()
                    offset   = crash_addr - base
                    for kw, (label, colour, could_be) in STINGRAY_PATTERNS.items():
                        if kw in mod_name:
                            hints.append((
                                label,
                                f"Crash address landed inside {Path(m['name']).name}  +0x{offset:X}",
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
                    mname = Path(m["name"]).name.lower()
                    if "dstorage" in mname:
                        base = int(m["base"], 16)
                        if base <= crash_addr < base + m["size"]:
                            hints.insert(0, (
                                "⚠ DIRECTSTORAGE FAILURE",
                                f"Crash address landed inside {Path(m['name']).name} - DirectStorage itself crashed.",
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
            hints.append(("Stack Overflow", "Likely infinite recursion or very deep call stack", RED,
                "Could be: infinite recursion in Lua or C++, extremely deep call chain during level load, "
                "or a very large stack allocation inside a function."))
        if "c0000374" in code:
            hints.append(("Heap Corruption", "Memory stomped before crash – use heap profiler", RED,
                "Could be: buffer overrun corrupting heap metadata, double-free, "
                "or a use-after-free that stomped an allocator's internal freelist."))
        if "e06d7363" in code:
            hints.append(("Unhandled C++ Exception", "Exception thrown but not caught – check throw sites", YELLOW,
                "Could be: std::bad_alloc (out of memory), std::out_of_range, "
                "or a custom engine exception thrown in a codepath with no try/catch."))
        if "80000003" in code:
            hints.append(("Breakpoint in Release Build", "__debugbreak() or assert left in shipping code", YELLOW,
                "Could be: a debug assert accidentally shipped, an __debugbreak() in error handling code, "
                "or an anti-cheat / DRM trigger firing incorrectly."))

    return hints

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
                    n = Path(m["name"]).name
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

        if ex_code == 0xC0000005 and len(params) >= 2:
            op          = "write" if params[0] == "0x1" else "read"
            fault_addr  = int(params[1], 16)

            decoded_instr = None
            instr_mem = read_virtual_memory(parsed, ex_addr, 16)  # 16 bytes to catch vtable pattern
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
                    "title": f"Virtual method called on null 'this' pointer — vtable dispatch crashed",
                    "detail": (
                        f"The crash instruction is MOV RAX, [RCX] followed by CALL [RAX+0x{ib[5]:02X}] "
                        f"— the standard x64 C++ virtual dispatch sequence. "
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

        rcx = t.get("rcx", 0)
        rax = t.get("rax", 0)
        rdx = t.get("rdx", 0)
        this_null = rcx < 0x1000
        findings.append({"conf": "MED" if not this_null else "HIGH",
            "title": f"Active game thread in {mod} +0x{off:X}",
            "detail": (f"This thread was executing game code when the crash occurred - "
                       f"it is the most likely location of the root cause. "
                       + (f"RCX (likely 'this' pointer) = 0x{rcx:016X} - near zero, suggesting a null object was being called on. "
                          if this_null else
                          f"RCX=0x{rcx:016X}  RDX=0x{rdx:016X}  RAX=0x{rax:016X}. ")
                       + f"Click to inspect in Threads tab."),
            "link": {"tab": "threads", "tid": t["tid"]},
        })

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
                    crash_mod = f"{Path(m['name']).name}  +0x{crash_addr - base:X}"
                    break
            lines.append(f"  In      : {crash_mod or '(address outside all known modules)'}")
        except Exception:
            pass
        regs = ex.get("regs", {})
        if regs:
            lines.append("")
            lines.append("── REGISTERS AT CRASH (ExceptionStream — ground truth) ─")
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
            name = Path(m["name"]).name if m["name"] else "?"
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
                f"The base address ({base_str}) was null or near-null at crash time — "
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
                    "The destination is hardcoded as null — this is an intentional Stingray engine suicide."
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
                f"If {pfx}{base_str} was null at crash time this is a null pointer write — "
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
                align_note = " MOVAPS requires 16-byte alignment — misalignment also causes this crash." if "MOVAPS" in mnemonic else ""
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
    for m in modules:
        name = m["name"]
        nl   = name.lower().replace("/", "\\")
        p    = Path(name)
        if p.suffix.lower() == ".exe" and ("steamapps" in nl or "games" in nl or "program files" in nl):
            parts = p.parts
            for j, part in enumerate(parts):
                if part.lower() in ("bin", "binaries", "win64", "win32", "x64"):
                    game_root = "\\".join(parts[:j]).lower()
                    break
            if game_root:
                break

    SAFE_PREFIXES = [
        "c:\\windows\\",
        "c:\\program files (x86)\\steam\\",
        "c:\\program files\\steam\\",
        "c:\\program files\\windows",
        "c:\\programdata\\",
    ]
    if game_root:
        SAFE_PREFIXES.append(game_root)

    KNOWN_GAME_DLLS = {
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
        "fmodstudio64.dll", "fmodstudioL64.dll", "fmod64.dll", "fmodL64.dll",
        "physxdevice64.dll", "physx3_x64.dll", "physx3common_x64.dll",
        "nvphysxgpu64.dll",
        "level_generation_pluginw64_release.dll",
        "level_generation_pluginw64_debug.dll",
        "easyanticheat.dll", "easyanticheat_launcher.dll",
        "dxcompiler.dll", "dxil.dll", "d3d12core.dll",
        "nvapi64.dll", "amd_ags_x64.dll",
        "winpixeventruntime.dll",
        "xaudio2_9.dll", "xaudio2_8.dll", "x3daudio1_7.dll",
        "mfplat.dll", "mfreadwrite.dll",
        "concrt140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
        "vcruntime140_1.dll",
        "playfabmultiplayerwin.dll", "partywin.dll",
        "amd_fidelityfx_upscaler_dx12.dll",
        "amd_fidelityfx_upscaler_dx11.dll",
        "libxess.dll",
        "nvspcap64.dll", "nvspcap.dll",
        "nvgpucomp64.dll",
        "nvldumdx.dll",
        "nvppex.dll",
        "nvmemmapmapstoragex.dll",
        "nvmessagebus.dll",
        "d3d11on12.dll",
        "dxilconv.dll",
        "d3dscache.dll",
        "dxcore.dll",
        "msvcr110.dll", "msvcr120.dll", "msvcr100.dll",
        "xaudio2_7.dll", "xaudio2_8.dll",
    }

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
        "nexusmods":        "Nexus Mods",
        "modengine2":       "ModEngine2 (Souls modding framework)",
        "reshade":          "ReShade (post-processing / D3D hook)",
        "minhook":          "MinHook (function hooking - common mod injection vector)",
        "\\xinput\\":        "XInput hook (common mod injection point)",
    }

    for m in modules:
        name  = m["name"]
        nl    = name.lower().replace("/", "\\")
        sn    = Path(name).name
        snl   = sn.lower()

        is_safe = any(nl.startswith(p) for p in SAFE_PREFIXES)
        is_known_dll = snl in {k.lower() for k in KNOWN_GAME_DLLS}
        is_plugin = "\\plugins\\" in nl

        if not is_safe and not is_known_dll and not is_plugin:
            indicators.append({
                "type":   "unknown_dll",
                "path":   name,
                "detail": f"DLL loaded from unexpected location: {name}",
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

        if "\\workshop\\content\\" in nl:
            indicators.append({
                "type":   "workshop_mod",
                "path":   name,
                "detail": f"Steam Workshop content loaded: {name}",
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

    has_mods   = len(unique) > 0
    confidence = "HIGH" if any(i["type"] in ("workshop_mod", "mod_manager") for i in unique) else \
                 "MED"  if any(i["type"] == "unknown_dll" for i in unique) else "LOW"

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
    all_mods = " ".join(Path(m["name"]).name.lower() for m in modules)
    CRASH_HANDLERS = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    def mod_for_addr(addr):
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return Path(m["name"]).name
            except Exception:
                pass
        return None

    crash_mod  = mod_for_addr(ex_addr) or ""
    is_suicide = bool(decoded_instr and decoded_instr.get("is_suicide"))

    active_mods = []
    for t in threads:
        rip = t.get("rip", 0)
        mod = mod_for_addr(rip)
        if not mod: continue
        full = next((m["name"] for m in modules if Path(m["name"]).name == mod), "")
        fl   = full.lower().replace("/", "\\")
        if "\\windows\\" in fl or mod.lower() in CRASH_HANDLERS: continue
        active_mods.append(mod.lower())

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
                kw = m["stack_contains"].lower()
                if not any(kw in mod.lower() for mod in active_mods): continue
            if "module_loaded" in m:
                if m["module_loaded"].lower() not in all_mods: continue
            if "module_not_loaded" in m:
                if m["module_not_loaded"].lower() in all_mods: continue
            if "active_thread_mod_contains" in m:
                kw = m["active_thread_mod_contains"].lower()
                if not any(kw in mod for mod in active_mods): continue
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
    all_mods   = " ".join(Path(m["name"]).name.lower() for m in modules)

    CRASH_HANDLERS  = {"crs-client.dll", "crashpad_handler.exe", "crashrpt.dll",
                       "sentry.dll", "backtrace.dll"}
    SYSTEM_PREFIXES = ("c:\\windows\\", "c:\\program files\\windows")

    GPU_DRIVER_FRAGMENTS = (
        "amdxc64", "amdxc32", "amdxx64", "amdxx32",
        "atidxx64", "atidxx32", "amdihk64",
        "nvwgf2umx", "nvwgf2um", "nvd3dumx", "nvd3dum",
        "nvgpucomp64", "nvldumdx", "nvppex",
        "igdumd64", "igdumd32", "igxelpicd64",
        "igd10um64", "igd10iumd64", "igc64", "igdgmm64",
        "igd12dxva64",
    )

    def mod_for_addr(addr: int) -> "str | None":
        for m in modules:
            try:
                base = int(m["base"], 16)
                if base <= addr < base + m["size"]:
                    return Path(m["name"]).name
            except Exception:
                pass
        return None

    def full_path_for_mod(mod_name: str) -> str:
        return next((m["name"] for m in modules
                     if Path(m["name"]).name == mod_name), "").lower().replace("/", "\\")

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
                "This is a game bug — a C++ object was used after its lifetime ended."
            ),
            "fix": [
                "This is a game bug — please report it with the dump file",
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
            "name": "Null pointer read — object was null or already destroyed",
            "player_message": (
                "The game tried to read from a null pointer. "
                "This means an object that was expected to exist was null — "
                "it was never created, already destroyed, or a function returned null "
                "and the caller didn't check before using it."
            ),
            "fix": [
                "This is a game bug — please report it with the dump file",
                "Share both the .dmp and the .log file with the 418th",
                "Note exactly what you were doing when it crashed",
                "Check if it happens consistently or randomly",
            ],
            "dev_note": (
                "AV read from 0x0 — the base pointer itself was null (not a field offset). "
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
            "name": "Null pointer write — destroyed or uninitialised object",
            "player_message": (
                "The game tried to write to memory through a null or invalid pointer. "
                "This is a game bug — an object was used after being destroyed, "
                "or was never properly initialised."
            ),
            "fix": [
                "This is a game bug — please report it with the dump file",
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
                "Update your NVIDIA drivers — use DDU for a clean install if issues persist",
            ],
            "dev_note": (
                "Crash in GPU driver DLL on dual-GPU system (NVIDIA + Intel iGPU both loaded). "
                "Check which adapter D3D12 is selecting at runtime — possible iGPU fallback."
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
                    "Try again — intermittent network issues often resolve themselves",
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
                    return Path(m["name"]).name, addr - base
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
                     if Path(m["name"]).name == mod), "")
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
    all_mod_names = " ".join(Path(m["name"]).name.lower() for m in modules)
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

class CrashAnalyzer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Stingray Crash Analyzer")
        self.configure(bg=BG)
        self.geometry("1100x800")
        self.minsize(800, 600)
        self._parsed = None
        self._build_ui()

    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, pady=10, padx=16)
        topbar.pack(fill="x", side="top")

        title_lbl = tk.Label(topbar, text="STINGRAY CRASH ANALYZER",
                             bg=BG2, fg=ACCENT, font=("Consolas", 14, "bold"))
        title_lbl.pack(side="left")

        subtitle = tk.Label(topbar, text="minidump → crash analysis",
                            bg=BG2, fg=TEXT_DIM, font=("Consolas", 9))
        subtitle.pack(side="left", padx=12, pady=4)

        self._open_btn = tk.Button(topbar, text="  Open .dmp …",
                                   command=self._open_file,
                                   bg=ACCENT, fg="white",
                                   activebackground=ACCENT2,
                                   relief="flat", padx=14, pady=4,
                                   font=("Consolas", 10, "bold"),
                                   cursor="hand2")
        self._open_btn.pack(side="right", padx=4)

        tk.Button(topbar, text="  ✎ Patterns",
                  command=self._open_pattern_editor,
                  bg=BG3, fg=TEXT_DIM,
                  activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", padx=10, pady=4,
                  font=("Consolas", 9),
                  cursor="hand2").pack(side="right", padx=4)

        self._file_var = tk.StringVar(value="No file loaded")
        file_bar = tk.Frame(self, bg=BG3, pady=5, padx=16)
        file_bar.pack(fill="x")
        tk.Label(file_bar, textvariable=self._file_var,
                 bg=BG3, fg=TEXT_DIM, font=("Consolas", 9)).pack(side="left")

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook",       background=BG,  borderwidth=0)
        style.configure("TNotebook.Tab",   background=BG2, foreground=TEXT_DIM,
                        padding=[14, 6], font=("Consolas", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self._tab_simple    = self._make_tab("⚡ Simple View")
        self._tab_overview  = self._make_tab("Overview")
        self._tab_rootcause = self._make_tab("Root Cause")
        self._tab_modules   = self._make_tab("Modules")
        self._tab_threads   = self._make_tab("Threads")
        self._tab_hints     = self._make_tab("Quick Hints")

        self._simple_frame   = tk.Frame(self._tab_simple,   bg=BG); self._simple_frame.pack(fill="both", expand=True)
        self._overview_txt   = self._make_text(self._tab_overview, MONO, 10)
        self._rootcause_frame= tk.Frame(self._tab_rootcause, bg=BG); self._rootcause_frame.pack(fill="both", expand=True)
        self._modules_frame  = self._make_table_frame(self._tab_modules)
        self._threads_frame  = tk.Frame(self._tab_threads, bg=BG); self._threads_frame.pack(fill="both", expand=True)
        self._hints_frame    = tk.Frame(self._tab_hints,   bg=BG); self._hints_frame.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="Ready – open a .dmp file to begin")
        status = tk.Frame(self, bg=BG2, pady=4, padx=16)
        status.pack(fill="x", side="bottom")
        self._prog = ttk.Progressbar(status, mode="indeterminate", length=120)
        self._prog.pack(side="right", padx=8)
        tk.Label(status, textvariable=self._status_var,
                 bg=BG2, fg=TEXT_DIM, font=("Consolas", 9)).pack(side="left")

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
        self._file_var.set(path)
        # FIX BUG-6: Disable the open button while parsing to prevent races
        # if the user clicks again before the background thread finishes.
        self._open_btn.config(state="disabled")
        self._status("Parsing minidump …", busy=True)

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
                        crash_mod_name = Path(m["name"]).name.lower()
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

        self._open_btn.config(state="normal")
        self._status(f"Parsed OK – {len(parsed.get('modules',[]))} modules, "
                     f"exception: {parsed.get('exception',{}).get('code','none')}",
                     busy=False)
        self._nb.select(0)

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
            name     = Path(m["name"]).name if m["name"] else "?"
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
            f.pack(fill="x", padx=24, pady=(18, 4))
            tk.Label(f, text=title.upper(), bg=BG, fg=colour,
                     font=("Consolas", 8, "bold")).pack(anchor="w")
            tk.Frame(f, bg=colour, height=1).pack(fill="x", pady=(2, 0))

        def card(parent, bg=BG2):
            f = tk.Frame(parent, bg=bg, padx=20, pady=14)
            f.pack(fill="x", padx=24, pady=4)
            return f

        def label(parent, text, fg=TEXT, font_size=10, bold=False, wrap=860):
            tk.Label(parent, text=text, bg=parent["bg"], fg=fg,
                     font=("Consolas", font_size, "bold" if bold else "normal"),
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

        TAB_INDEX = {"modules": 2, "threads": 3}

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
                if not line.endswith("."):
                    line += "."
                fg = ACCENT2 if any(line.startswith(w) for w in ("Load", "Check", "Click", "→")) else TEXT
                tk.Label(body, text=line, bg=card_bg, fg=fg,
                         font=("Consolas", 9), wraplength=860,
                         justify="left", anchor="w").pack(anchor="w", pady=1)

            if link:
                def make_handler(lnk, parsed=parsed):
                    def on_click(e=None):
                        tab_name = lnk.get("tab")
                        tab_idx  = TAB_INDEX.get(tab_name)
                        if tab_idx is not None:
                            self._nb.select(tab_idx)
                        if tab_name == "modules" and "module" in lnk:
                            self._highlight_module(lnk["module"])
                        elif tab_name == "threads" and "tid" in lnk:
                            self._highlight_thread(lnk["tid"])
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
             if Path(m["name"]).name.lower() == module_name.lower()),
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
            ("2. Set Microsoft public symbol path (no game PDBs needed for this)",
             f'.sympath "srv*C:\\Symbols*https://msdl.microsoft.com/download/symbols"'),
            ("3. Reload symbols (resolves Windows/system DLL names)",
             ".reload /f"),
            ("4. Switch to the crashing thread and show its call stack",
             f"~{ex.get('thread_id', 0)}s ; kb 30"),
            ("5. Disassemble the instructions around the crash address",
             f"u {crash_addr:#x}-10 L20"),
            ("6. Show all register values at crash time",
             "r"),
            ("7. Try to identify the function (may show only offset without PDBs)",
             f"ln {crash_addr:#x}"),
            ("8. Show all threads with their top 5 frames",
             "~* kb 5"),
            ("9. Show what the stack pointer was pointing at",
             "dq @rsp L8"),
        ]

        note_lines = [
            "⚠  No public PDBs available for this game.",
            "   Steps 4, 5, 7 will show raw addresses instead of function names.",
            "   You can still see: which DLL crashed, register values, raw disassembly,",
            "   and whether the crash address is near any known Windows symbols.",
            "   If you have access to internal build PDBs, add their folder to step 2.",
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
        tk.Label(self._hints_frame,
                 text="  Rule-Based Quick Hints  ",
                 bg=BG2, fg=ACCENT, font=("Consolas", 11, "bold"),
                 anchor="w").pack(fill="x", padx=8, pady=(8, 4))

        if exception:
            card = tk.Frame(self._hints_frame, bg=BG3, padx=16, pady=10)
            card.pack(fill="x", padx=8, pady=4)
            tk.Label(card, text="EXCEPTION", bg=BG3, fg=ACCENT2,
                     font=("Consolas", 9, "bold")).pack(anchor="w")
            tk.Label(card, text=f"{exception['code']}  –  {exception['code_desc']}",
                     bg=BG3, fg=TEXT, font=("Consolas", 10)).pack(anchor="w")
            tk.Label(card, text=f"Crash address: {exception['address']}   Thread: {exception['thread_id']}",
                     bg=BG3, fg=TEXT_DIM, font=("Consolas", 9)).pack(anchor="w")

        if not hints:
            tk.Label(self._hints_frame,
                     text="  No specific pattern hints detected from module names.",
                     bg=BG, fg=TEXT_DIM, font=("Consolas", 10)).pack(pady=12, anchor="w", padx=16)
            return

        for label, detail, colour, could_be in hints:
            card = tk.Frame(self._hints_frame, bg=BG3, padx=16, pady=10)
            card.pack(fill="x", padx=8, pady=3)
            indicator = tk.Frame(card, bg=colour, width=4)
            indicator.pack(side="left", fill="y", padx=(0, 12))
            inner = tk.Frame(card, bg=BG3)
            inner.pack(side="left", fill="x", expand=True)
            tk.Label(inner, text=label, bg=BG3, fg=colour,
                     font=("Consolas", 10, "bold")).pack(anchor="w")
            tk.Label(inner, text=detail, bg=BG3, fg=TEXT_DIM,
                     font=("Consolas", 9)).pack(anchor="w")
            tk.Label(inner, text=could_be, bg=BG3, fg=TEXT,
                     font=("Consolas", 9), wraplength=800, justify="left").pack(anchor="w", pady=(4, 0))

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