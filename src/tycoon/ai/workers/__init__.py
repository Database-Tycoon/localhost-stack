"""AI worker factory for tycoon.

Each worker is a focused, single-responsibility AI agent that operates on
one discrete part of the data pipeline. Workers are programmatic — they are
called by pipeline orchestrators and commands, not directly by users.
"""

from tycoon.ai.workers.base import BaseWorker, WorkerPipeline, WorkerResult
from tycoon.ai.workers.ingestion import PipelineDebugger, SchemaDriftDetector
from tycoon.ai.workers.staging import ColumnDocumenter, ColumnRenamer, NullHandler, StagingImprover
from tycoon.ai.workers.tests import TestFixer, TestWriter

__all__ = [
    "BaseWorker",
    "WorkerPipeline",
    "WorkerResult",
    "TestWriter",
    "TestFixer",
    "StagingImprover",
    "NullHandler",
    "ColumnDocumenter",
    "ColumnRenamer",
    "PipelineDebugger",
    "SchemaDriftDetector",
]
