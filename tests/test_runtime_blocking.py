import asyncio
import os
import sys
import time
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.runtime.blocking import BlockingCall, offload_blocking_calls


class TestRuntimeBlockingHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_offload_blocking_calls_runs_independent_reads_in_parallel(self):
        def slow_read(value):
            time.sleep(0.08)
            return value

        started = time.perf_counter()
        first, second = await offload_blocking_calls(
            BlockingCall(slow_read, args=("first",)),
            BlockingCall(slow_read, args=("second",)),
        )
        elapsed = time.perf_counter() - started

        self.assertEqual((first, second), ("first", "second"))
        self.assertLess(elapsed, 0.13, elapsed)
