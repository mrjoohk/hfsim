"""Run manifest and evidence-pack schema for experiment reproducibility (REQ-010).

RunManifest records config, seed, hardware profile, and code revision so
that any simulator or learning run can be reproduced exactly.

EvidencePackManifest wraps a RunManifest with per-REQ artifact paths and a
pass/fail verdict, providing the top-level audit record for each requirement.

REQ-010 acceptance criterion: ``capture_run_manifest()`` must complete within 5 s.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HardwareProfile:
    """System resource snapshot for reproducibility.

    ``ram_total_gb`` is 0.0 when OS detection is unavailable; callers should
    treat 0.0 as "unknown" rather than "no RAM".
    ``cpu_freq_mhz`` is 0.0 when the OS does not expose CPU frequency.
    """

    cpu_count: int
    ram_total_gb: float
    platform_str: str
    python_version: str
    cpu_freq_mhz: float = 0.0


@dataclass
class RunManifest:
    """Reproducibility record for one simulator or training run.

    Fields map directly to REQ-010 acceptance criteria:
    ``config``, ``seed``, ``hardware_profile``, ``code_revision``.
    """

    run_id: str
    timestamp_utc: str          # ISO-8601
    seed: int
    config: dict[str, Any]
    hardware_profile: HardwareProfile
    code_revision: str          # 40-char git SHA or "unknown"
    sim_version: str = "hfsim-0.1.0"

    def to_dict(self) -> dict[str, Any]:
        d = {
            "run_id": self.run_id,
            "timestamp_utc": self.timestamp_utc,
            "seed": self.seed,
            "config": dict(self.config),
            "hardware_profile": asdict(self.hardware_profile),
            "code_revision": self.code_revision,
            "sim_version": self.sim_version,
        }
        return d

    def save(self, path: str | Path) -> Path:
        """Write manifest as indented JSON; return the written path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return target


@dataclass
class EvidencePackManifest:
    """Top-level audit record linking a RunManifest to REQ-specific artifacts.

    ``artifact_paths`` maps artifact role to file path, e.g.::

        {
            "benchmark_report":  "reports/time_acceleration/result.json",
            "validation_log":    "reports/dynamics_6dof/rollout.jsonl",
        }
    """

    pack_id: str
    req_id: str                     # e.g. "REQ-004"
    timestamp_utc: str
    run_manifest: RunManifest
    artifact_paths: dict[str, str] = field(default_factory=dict)
    pass_fail: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "req_id": self.req_id,
            "timestamp_utc": self.timestamp_utc,
            "run_manifest": self.run_manifest.to_dict(),
            "artifact_paths": dict(self.artifact_paths),
            "pass_fail": self.pass_fail,
            "notes": list(self.notes),
        }

    def save(self, path: str | Path) -> Path:
        """Write evidence pack as indented JSON; return the written path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return target


# ---------------------------------------------------------------------------
# Hardware detection helpers
# ---------------------------------------------------------------------------

def _detect_ram_gb() -> float:
    """Best-effort RAM detection; returns 0.0 on failure."""
    # Try psutil first (not a hard dependency)
    try:
        import psutil  # type: ignore[import-not-found]
        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except ImportError:
        pass

    # Windows fallback via ctypes
    if sys.platform == "win32":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
            return round(stat.ullTotalPhys / (1024 ** 3), 2)
        except Exception:
            return 0.0

    # Linux / macOS fallback via /proc/meminfo
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    ram_kb = int(line.split()[1])
                    return round(ram_kb / (1024 ** 2), 2)
    except Exception:
        pass

    return 0.0


def _detect_hardware() -> HardwareProfile:
    return HardwareProfile(
        cpu_count=os.cpu_count() or 1,
        ram_total_gb=_detect_ram_gb(),
        platform_str=platform.platform(),
        python_version=sys.version.split()[0],
    )


def _get_code_revision() -> str:
    """Return the current git HEAD SHA, or 'unknown' if unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def capture_run_manifest(
    *,
    run_id: str | None = None,
    seed: int = 0,
    config: dict[str, Any] | None = None,
) -> RunManifest:
    """Capture a RunManifest within 5 s (REQ-010 acceptance criterion).

    Args:
        run_id:  Identifier for this run; auto-generated UUID when omitted.
        seed:    RNG seed used for this run.
        config:  Arbitrary config dict embedded in the manifest.

    Returns:
        A fully populated :class:`RunManifest`.

    Raises:
        RuntimeError: If capture takes longer than 5 s.
    """
    t0 = time.perf_counter()

    manifest = RunManifest(
        run_id=run_id or str(uuid.uuid4()),
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        config=dict(config or {}),
        hardware_profile=_detect_hardware(),
        code_revision=_get_code_revision(),
    )

    elapsed = time.perf_counter() - t0
    if elapsed > 5.0:
        raise RuntimeError(
            f"capture_run_manifest took {elapsed:.2f}s > 5s limit (REQ-010)"
        )

    return manifest


def build_evidence_pack(
    *,
    req_id: str,
    run_manifest: RunManifest,
    artifact_paths: dict[str, str] | None = None,
    pass_fail: bool = False,
    notes: list[str] | None = None,
) -> EvidencePackManifest:
    """Build an :class:`EvidencePackManifest` linking a RunManifest to REQ artifacts."""
    return EvidencePackManifest(
        pack_id=str(uuid.uuid4()),
        req_id=req_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        run_manifest=run_manifest,
        artifact_paths=dict(artifact_paths or {}),
        pass_fail=pass_fail,
        notes=list(notes or []),
    )
