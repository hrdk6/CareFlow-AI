"""Process and container memory, read from Linux /proc and cgroup files (None elsewhere).

Hosts such as Render stop a container that exceeds its memory limit; these numbers show how close it runs.
"""
from pathlib import Path


def _status_kb(field: str) -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith(field + ":"):
                return int(line.split()[1])
    except OSError:
        return None
    return None


def _read_int(*paths: str) -> int | None:
    for path in paths:
        try:
            value = Path(path).read_text().strip()
        except OSError:
            continue
        if value.isdigit():
            return int(value)
    return None


def memory_snapshot() -> dict[str, int | None]:
    """Megabytes: this process now and at its peak, and the whole container now and against its limit."""
    def mb(v: int | None, scale: int) -> int | None:
        return None if v is None else round(v * scale / (1024 * 1024))

    return {
        "process_mb": mb(_status_kb("VmRSS"), 1024),
        "process_peak_mb": mb(_status_kb("VmHWM"), 1024),
        "container_mb": mb(_read_int("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"), 1),
        "container_peak_mb": mb(_read_int("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"), 1),
        "container_limit_mb": mb(_read_int("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"), 1),
    }


def memory_line() -> str:
    snap = memory_snapshot()
    return " ".join(f"{k}={v}" for k, v in snap.items() if v is not None) or "memory stats unavailable on this OS"
