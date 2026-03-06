"""Focused tests for Langfuse context management safety."""

import os
import sys
import unittest
from contextlib import contextmanager

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.observability.langfuse_client import LangfuseClientManager


class _DummyObservation:
    def __init__(self, trace_id="trace-123"):
        self.trace_id = trace_id

    def update(self, **kwargs):
        return None


class _DummyContextManager:
    def __init__(self, obs=None, fail_enter=False, fail_exit=False):
        self._obs = obs or _DummyObservation()
        self._fail_enter = fail_enter
        self._fail_exit = fail_exit

    def __enter__(self):
        if self._fail_enter:
            raise RuntimeError("enter failed")
        return self._obs

    def __exit__(self, exc_type, exc, tb):
        if self._fail_exit:
            raise RuntimeError("exit failed")
        return False


class _DummyClient:
    def __init__(self, *, fail_setup=False, fail_enter=False, fail_exit=False):
        self._fail_setup = fail_setup
        self._fail_enter = fail_enter
        self._fail_exit = fail_exit

    def start_as_current_observation(self, **kwargs):
        if self._fail_setup:
            raise RuntimeError("setup failed")
        return _DummyContextManager(
            fail_enter=self._fail_enter,
            fail_exit=self._fail_exit,
        )


class TestLangfuseClientObserve(unittest.TestCase):
    def setUp(self):
        self.manager = LangfuseClientManager()

    def test_observe_propagates_application_exception_without_runtimeerror(self):
        self.manager._client = _DummyClient()

        with self.assertRaises(ValueError):
            with self.manager.observe(name="test", as_type="span"):
                raise ValueError("application error")

    def test_observe_falls_back_to_noop_when_setup_fails(self):
        self.manager._client = _DummyClient(fail_setup=True)

        with self.manager.observe(name="test", as_type="span") as obs:
            self.assertTrue(hasattr(obs, "update"))
            self.assertEqual(getattr(obs, "trace_id", ""), "")

    def test_observe_falls_back_to_noop_when_enter_fails(self):
        self.manager._client = _DummyClient(fail_enter=True)

        with self.manager.observe(name="test", as_type="span") as obs:
            self.assertTrue(hasattr(obs, "update"))
            self.assertEqual(getattr(obs, "trace_id", ""), "")

    def test_observe_does_not_raise_when_exit_fails(self):
        self.manager._client = _DummyClient(fail_exit=True)

        with self.manager.observe(name="test", as_type="span") as obs:
            self.assertEqual(getattr(obs, "trace_id", ""), "trace-123")


if __name__ == "__main__":
    unittest.main()
