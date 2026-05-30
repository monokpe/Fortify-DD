from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

from app.config import Settings
from app.schemas import DeltaReport, RiskBrief


def vendor_key(vendor: str) -> str:
    return " ".join(vendor.lower().strip().split())


@dataclass
class VendorMemoryRecord:
    assessments: list[RiskBrief] = field(default_factory=list)
    deltas: list[DeltaReport] = field(default_factory=list)


class InMemoryVendorMemory:
    def __init__(self) -> None:
        self._records: dict[str, VendorMemoryRecord] = defaultdict(VendorMemoryRecord)
        self._lock = Lock()

    def latest_brief(self, vendor: str) -> RiskBrief | None:
        with self._lock:
            assessments = self._records[vendor_key(vendor)].assessments
            return assessments[-1] if assessments else None

    def history(self, vendor: str) -> VendorMemoryRecord:
        with self._lock:
            record = self._records[vendor_key(vendor)]
            return VendorMemoryRecord(
                assessments=list(record.assessments),
                deltas=list(record.deltas),
            )

    def store(self, brief: RiskBrief, delta: DeltaReport | None = None) -> None:
        with self._lock:
            record = self._records[vendor_key(brief.company)]
            record.assessments.append(brief)
            if delta:
                record.deltas.append(delta)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


vendor_memory = InMemoryVendorMemory()


class CogneeMemoryClient:
    def __init__(
        self,
        settings: Settings,
        memory: InMemoryVendorMemory = vendor_memory,
    ) -> None:
        self.settings = settings
        self.memory = memory

    async def get_latest_brief(self, vendor: str) -> RiskBrief | None:
        return self.memory.latest_brief(vendor)

    async def get_history(self, vendor: str) -> VendorMemoryRecord:
        return self.memory.history(vendor)

    async def store_brief(self, brief: RiskBrief, delta: DeltaReport | None = None) -> None:
        self.memory.store(brief, delta)
