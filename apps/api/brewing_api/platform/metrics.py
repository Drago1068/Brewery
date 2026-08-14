from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

_lock = threading.Lock()


@dataclass
class MetricSample:
    name: str
    value_ms: float
    correlation_id: str
    ok: bool = True
    labels: dict[str, str] = field(default_factory=dict)


_samples: list[MetricSample] = []
_counters: dict[str, int] = defaultdict(int)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def record_duration(
    name: str,
    started: float,
    correlation_id: str | None = None,
    ok: bool = True,
    **labels: str,
) -> float:
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    with _lock:
        _samples.append(
            MetricSample(
                name=name,
                value_ms=elapsed_ms,
                correlation_id=correlation_id or new_correlation_id(),
                ok=ok,
                labels=dict(labels),
            )
        )
        _counters[f"{name}:{'ok' if ok else 'error'}"] += 1
    return elapsed_ms


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def snapshot(name: str | None = None) -> dict:
    with _lock:
        rows = [item for item in _samples if name is None or item.name == name]
        counters = dict(_counters)
    by_name: dict[str, list[float]] = defaultdict(list)
    for item in rows:
        if item.ok:
            by_name[item.name].append(item.value_ms)
    summary = {
        key: {
            "count": len(values),
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "max_ms": max(values) if values else 0.0,
        }
        for key, values in by_name.items()
    }
    return {"counters": counters, "operations": summary, "sample_count": len(rows)}


def reset_metrics() -> None:
    with _lock:
        _samples.clear()
        _counters.clear()


def reconstruct_failure(correlation_id: str) -> list[dict]:
    with _lock:
        return [
            {
                "name": item.name,
                "value_ms": item.value_ms,
                "ok": item.ok,
                "labels": item.labels,
                "correlation_id": item.correlation_id,
            }
            for item in _samples
            if item.correlation_id == correlation_id
        ]
