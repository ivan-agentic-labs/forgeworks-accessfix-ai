from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from accessfix_ai.infrastructure.store import Store


@dataclass(frozen=True)
class WorkerConfig:
    lease_seconds: float = 0.25
    timeout_seconds: float = 1.0
    max_attempts: int = 3


class ScanWorker:
    """One-shot worker loop for local fixture scans.

    The worker never performs network/browser I/O.  A processor may be injected by
    tests, but production's default processor only writes deterministic fixture
    findings through Store.complete_scan.
    """

    def __init__(self, store: Store, config: WorkerConfig | None = None, processor: Callable[[dict], None] | None = None):
        self.store = store
        self.config = config or WorkerConfig()
        self.processor = processor

    def run_once(self) -> bool:
        row = self.store.claim_scan(self.config.lease_seconds, self.config.timeout_seconds)
        if not row:
            return False
        tenant, scan_id = row["tenant_id"], row["id"]
        if row["cancel_requested"]:
            self.store.fail_scan(tenant, scan_id, "CANCELLED", max_attempts=self.config.max_attempts, lease_until=row["lease_until"])
            return True
        started = time.monotonic()
        try:
            if self.processor:
                self.processor(dict(row))
            elapsed = time.monotonic() - started
            if elapsed > self.config.timeout_seconds:
                self.store.fail_scan(tenant, scan_id, "WORKER_TIMEOUT", max_attempts=self.config.max_attempts, lease_until=row["lease_until"])
            else:
                self.store.complete_scan(tenant, scan_id, row["lease_until"])
        except Exception:
            self.store.fail_scan(tenant, scan_id, "WORKER_ERROR", max_attempts=self.config.max_attempts, lease_until=row["lease_until"])
        return True

    def drain(self, max_steps: int = 100) -> int:
        steps = 0
        while steps < max_steps and self.run_once():
            steps += 1
        return steps
