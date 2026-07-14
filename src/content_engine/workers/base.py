"""Worker framework contracts.

Sprint 1 defines the framework only. Business workers will be added later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol
import logging

from content_engine.config import Settings


class WorkerState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class WorkerContext:
    settings: Settings
    logger: logging.Logger


@dataclass(frozen=True)
class WorkerResult:
    worker_name: str
    state: WorkerState
    message: str
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseWorker(Protocol):
    name: str

    def start(self, context: WorkerContext) -> WorkerResult:
        """Start worker activity."""

    def stop(self) -> WorkerResult:
        """Stop worker activity."""


@dataclass
class WorkerRegistry:
    workers: list[BaseWorker] = field(default_factory=list)

    def register(self, worker: BaseWorker) -> None:
        self.workers.append(worker)

    def names(self) -> list[str]:
        return [worker.name for worker in self.workers]

