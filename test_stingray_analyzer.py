#!/usr/bin/env python3
"""
Pytest test suite for Stingray Crash Analyzer.
Run with: pytest test_stingray_analyzer.py -v
"""
import sys
import os
import types
import importlib.util

# Stub tkinterdnd2
sys.modules['tkinterdnd2'] = types.ModuleType('tkinterdnd2')
sys.modules['tkinterdnd2'].TkinterDnD = type('TkinterDnD', (), {'Tk': object})
sys.modules['tkinterdnd2'].DND_FILES = 'DND_FILES'

# Import the analyzer
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sca", os.path.join(SCRIPT_DIR, "stingray_crash_analyzer_unified.py"))
sca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sca)

import struct

# ═══════════════════════════════════════════════════════════════════════════════
# Test data builder — mirrors the debugger's _make_synthetic_parsed
# ═══════════════════════════════════════════════════════════════════════════════

def make_synthetic(scenario="access_violation"):
    """Build a synthetic parsed dict for testing."""
    BASE_MODULES = [
        {"name": "C:\\Program Files\\Game\\game.exe", "base": "0x0000000140000000", "size": 52_428_800, "checksum": "0x031A2F40", "timestamp": "2024-03-15"},
        {"name": "C:\\Program Files\\Game\\engine.dll", "base": "0x0000000180000000", "size": 35_651_584, "checksum": "0x01B4C200", "timestamp": "2024-03-15"},
        {"name": "C:\\Windows\\System32\\ntdll.dll", "base": "0x00007FF800000000", "size": 2_097_152, "checksum": "0x00210A40", "timestamp": "2024-01-10"},
        {"name": "C:\\Windows\\System32\\msvcp140.dll", "base": "0x00007FF700000000", "size": 593_920, "checksum": "0x00095A40", "timestamp": "2056-12-30"},
        {"name": "C:\\Windows\\System32\\vcruntime140.dll", "base": "0x00007FF6F0000000", "size": 94_208, "checksum": "0x000183C0", "timestamp": "2005-04-16"},
        {"name": "C:\\Windows\\System32\\ucrtbase.dll", "base": "0x00007FF6D0000000", "size": 1_048_576, "checksum": "0x00102A00", "timestamp": "2014-06-17"},
    ]
    p = {
        "file": f"[SYNTHETIC] {scenario}.dmp", "size_mb": 1.0, "version": "1.0",
        "timestamp": "2026-01-01 00:00:00 UTC", "modules": [dict(m) for m in BASE_MODULES],
        "memory_map": [], "_raw_path": None, "_raw_bytes": b"",
        "threads": [{"tid": 0x1A2B, "suspend": 0, "pri": 8, "rip": 0x0000000180123456, "rsp": 0x000000C800100000,
                      "rax": 0, "rcx": 0, "rdx": 0, "rbx": 0, "rbp": 0, "rsi": 0, "rdi": 0,
                      "r8": 0, "r9": 0, "r10": 0, "r11": 0, "r12": 0, "r13": 0, "r14": 0, "r15": 0}],
        "exception": {"code": "0xc0000005", "code_desc": "AV", "address": "0x0000000180123456",
                       "thread_id": 0x1A2B, "params": ["0x0", "0x0"],
                       "regs": {"rax": 0, "rbx": 1, "rcx": 0, "rdx": 0x42, "rsi": 0, "rdi": 0,
                                "r8": 3, "r9": 0, "r10": 0, "r11": 0, "r12": 0, "r13": 0,
                                "r14": 0, "r15": 0, "rsp": 0x000000C800100000, "rbp": 0x000000C800100080}},
        "system_info": {"arch": "x64", "cpu_count": 8, "os_version": "10.0 build 22621"},
    }
    if scenario == "stack_overflow":
        p["exception"]["code"] = "0xc00000fd"
    elif scenario == "heap_corruption":
        p["exception"]["code"] = "0xc0000374"
    elif scenario == "cpp_exception":
        p["exception"]["code"] = "0xe06d7363"
    elif scenario == "int_div_zero":
        p["exception"]["code"] = "0xc0000094"
    elif scenario == "suicide":
        p["modules"][0]["name"] = "C:\\Program Files\\Game\\helldivers2.exe"
        p["exception"]["address"] = "0x0000000140001234"
        p["exception"]["params"] = ["0x0", "0x4"]
        p["exception"]["regs"]["rcx"] = 0
        p["exception"]["regs"]["rdx"] = 0
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseMinidump:
    def test_addr_to_mod(self):
        modules = [{"name": "test.dll", "base": "0x1000", "size": 0x2000}]
        result = sca.addr_to_mod(0x1500, modules)
        assert result is not None
        assert result[0] == "test.dll"
        assert result[1] == 0x500

    def test_addr_to_mod_not_found(self):
        assert sca.addr_to_mod(0x99999, []) is None


class TestInstructionDecoder:
    def test_mov_read(self):
        result = sca.decode_crash_instruction(b"\x8b\x5a\x04\x00\x00\x00\x00\x00\x00\x00", 0x1000)
        assert "MOV" in result["instruction"]
        assert "RDX" in result["instruction"]

    def test_mov_write_sib(self):
        # MOV [RAX+RBX*4], RCX = 89 0c d8
        result = sca.decode_crash_instruction(b"\x89\x0c\xd8\x00\x00\x00\x00\x00\x00\x00", 0x1000)
        assert "MOV" in result["instruction"]
        assert "RAX" in result["instruction"]
        assert "RBX" in result["instruction"]
        assert "CX" in result["instruction"]

    def test_mov_write_rex_b(self):
        # REX.B MOV [R8], RAX = 41 89 00
        result = sca.decode_crash_instruction(b"\x41\x89\x00\x00\x00\x00\x00\x00\x00\x00", 0x1000)
        assert "MOV" in result["instruction"]
        assert "R8" in result["instruction"]

    def test_suicide_mov_abs_null(self):
        # MOV [0x0], EAX = 89 04 25 00000000
        result = sca.decode_crash_instruction(b"\x89\x04\x25\x00\x00\x00\x00\x00\x00\x00", 0x1000)
        assert result["is_suicide"] == True

    def test_suicide_c7(self):
        # MOV [0x0], imm32 = C7 04 25 00000000 00000000
        result = sca.decode_crash_instruction(b"\xc7\x04\x25\x00\x00\x00\x00\x00\x00\x00\x00", 0x1000)
        assert result["is_suicide"] == True

    def test_int3(self):
        result = sca.decode_crash_instruction(b"\xcc\x00\x00\x00\x00", 0x1000)
        assert result["is_suicide"] == True
        assert "INT3" in result["instruction"]

    def test_ud2(self):
        result = sca.decode_crash_instruction(b"\x0f\x0b\x00\x00", 0x1000)
        assert result["is_suicide"] == True
        assert "UD2" in result["instruction"]

    def test_avx_vmovdqa(self):
        result = sca.decode_crash_instruction(b"\xc5\xf9\x6f\x05\x00\x00\x00\x00\x00\x00", 0x1000)
        assert "VMOVDQA" in result["instruction"]
        assert "XMM0" in result["instruction"]

    def test_avx_vmovups_null(self):
        result = sca.decode_crash_instruction(b"\xc5\xf8\x10\x01\x00\x00\x00\x00", 0x1000)
        assert "VMOVUPS" in result["instruction"]
        assert "CX" in result["instruction"]

    def test_avx_256bit(self):
        result = sca.decode_crash_instruction(b"\xc5\xfd\x6f\x05\x00\x00\x00\x00\x00\x00", 0x1000)
        assert "YMM" in result["instruction"]


class TestStingraySuicide:
    def test_suicide_detected(self):
        p = make_synthetic("suicide")
        is_sui, reason = sca._is_stingray_suicide(p)
        assert is_sui == True
        assert "helldivers2" in reason

    def test_non_suicide_not_flagged(self):
        p = make_synthetic("access_violation")
        is_sui, _ = sca._is_stingray_suicide(p)
        assert is_sui == False


class TestRootCause:
    def test_access_violation(self):
        p = make_synthetic("access_violation")
        findings = sca.assess_root_cause(p)
        assert len(findings) > 0

    def test_stack_overflow(self):
        p = make_synthetic("stack_overflow")
        findings = sca.assess_root_cause(p)
        assert len(findings) > 0

    def test_heap_corruption(self):
        p = make_synthetic("heap_corruption")
        findings = sca.assess_root_cause(p)
        assert len(findings) > 0

    def test_suicide_finding(self):
        p = make_synthetic("suicide")
        findings = sca.assess_root_cause(p)
        assert any("suicide" in f.get("title", "").lower() for f in findings)


class TestPatternMatching:
    def test_stack_overflow_pattern(self):
        p = make_synthetic("stack_overflow")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        assert pattern is not None
        assert pattern["id"] == "STACK_OVERFLOW"

    def test_heap_corruption_pattern(self):
        p = make_synthetic("heap_corruption")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        assert pattern is not None
        assert pattern["id"] == "HEAP_CORRUPTION"

    def test_int_div_zero_pattern(self):
        p = make_synthetic("int_div_zero")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        assert pattern is not None
        assert pattern["id"] == "INT_DIVIDE_BY_ZERO"

    def test_suicide_generic_pattern(self):
        p = make_synthetic("suicide")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        assert pattern is not None
        assert pattern["id"].startswith("SUICIDE_")


class TestDllVerify:
    def test_clean_dlls_pass(self):
        p = make_synthetic("access_violation")
        dv = sca.verify_critical_dlls(p)
        m140 = dv.get("msvcp140", {})
        assert m140.get("verdict") == "OK"

    def test_reproducible_build_not_flagged(self):
        p = make_synthetic("access_violation")
        # MSVCP140 has timestamp 2056-12-30 (reproducible build hash)
        dv = sca.verify_critical_dlls(p)
        m140 = dv.get("msvcp140", {})
        assert m140.get("verdict") == "OK"
        # ucrtbase has timestamp 2014-06-17 (reproducible build hash)
        ucrt = dv.get("runtime", {}).get("ucrtbase.dll", {})
        assert ucrt.get("verdict") == "OK"


class TestVerdictEngine:
    def test_verdict_suicide(self):
        p = make_synthetic("suicide")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        all_p = sca._match_all_patterns(p, None, mods, rc)
        v = sca.compute_verdict(p, rc, mods, pattern, all_p, None)
        assert v["verdict"] == "SUICIDE"
        assert len(v["signature"]) == 12
        assert v["signature"].startswith("SUI-")

    def test_verdict_game_bug(self):
        p = make_synthetic("access_violation")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        all_p = sca._match_all_patterns(p, None, mods, rc)
        v = sca.compute_verdict(p, rc, mods, pattern, all_p, None)
        assert v["verdict"] in ("GAME_BUG", "INCONCLUSIVE")

    def test_signature_format(self):
        p = make_synthetic("suicide")
        rc = sca.assess_root_cause(p)
        mods = sca.detect_mods(p)
        pattern = sca._match_patterns(p, None, mods, rc)
        all_p = sca._match_all_patterns(p, None, mods, rc)
        v = sca.compute_verdict(p, rc, mods, pattern, all_p, None)
        sig = v["signature"]
        assert "-" in sig
        prefix = sig.split("-")[0]
        assert prefix in ("SUI", "GPU", "MOD", "BUG", "UNK")
        assert len(sig.split("-")[1]) == 8


class TestEngineLogParser:
    def test_parse_log_with_errors(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("[2026-01-01 12:00:00] INFO: Game started\n")
            f.write("[2026-01-01 12:01:00] WARNING: Low memory\n")
            f.write("[2026-01-01 12:02:00] ERROR: Assertion failed in lua_call\n")
            f.write("[2026-01-01 12:02:01] FATAL: Engine shutting down\n")
            f.write("[2026-01-01 12:02:02] INFO: Shutdown complete\n")
            path = f.name
        result = sca.parse_engine_log(path)
        os.unlink(path)
        assert result["has_errors"] == True
        assert len(result["errors"]) >= 2
        assert len(result["warnings"]) >= 1
        assert len(result["last_lines"]) <= 20

    def test_parse_log_no_errors(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("[2026-01-01 12:00:00] INFO: Game started\n")
            f.write("[2026-01-01 12:01:00] INFO: All good\n")
            path = f.name
        result = sca.parse_engine_log(path)
        os.unlink(path)
        assert result["has_errors"] == False


class TestNullRegisters:
    def test_null_regs_filtered(self):
        p = make_synthetic("access_violation")
        null_info = sca._null_registers_at_crash(p)
        assert "null" in null_info
        assert "near_null" in null_info
        # _xmm should not appear in null regs
        assert "_XMM" not in null_info["null"]
        assert "_XMM" not in null_info["near_null"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
