import unittest

from backend.runtime.store import InMemoryRunStore, InvalidEventsCursorError, RunNotFoundError


class TestInMemoryRunStore(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryRunStore()

    def test_create_run_and_status_roundtrip(self):
        run = self.store.create_run(conversation_id="conv-1", message="hello", selected_documents=[])
        loaded = self.store.get_run(run.run_id)
        self.assertEqual(loaded.status, "queued")
        self.assertEqual(loaded.conversation_id, "conv-1")

    def test_cursor_pagination(self):
        run = self.store.create_run(conversation_id="conv-1", message="hello", selected_documents=[])
        self.store.append_event(run_id=run.run_id, event_type="queued", status="queued", message="queued")
        self.store.append_event(run_id=run.run_id, event_type="started", status="running", message="started")
        self.store.append_event(run_id=run.run_id, event_type="succeeded", status="succeeded", message="done")

        first_page, cursor, has_more = self.store.list_events(run_id=run.run_id, after=None, limit=2)
        self.assertEqual(len(first_page), 2)
        self.assertTrue(has_more)
        self.assertIsNotNone(cursor)

        second_page, second_cursor, second_has_more = self.store.list_events(run_id=run.run_id, after=cursor, limit=2)
        self.assertEqual(len(second_page), 1)
        self.assertEqual(second_page[0].type, "succeeded")
        self.assertFalse(second_has_more)
        self.assertEqual(second_cursor, second_page[0].event_id)

    def test_invalid_cursor_raises(self):
        run = self.store.create_run(conversation_id="conv-1", message="hello", selected_documents=[])
        with self.assertRaises(InvalidEventsCursorError):
            self.store.list_events(run_id=run.run_id, after="not-a-number", limit=10)

    def test_unknown_run_raises_not_found(self):
        with self.assertRaises(RunNotFoundError):
            self.store.get_run("missing")

    def test_update_run_can_clear_error_and_result(self):
        run = self.store.create_run(conversation_id="conv-1", message="hello", selected_documents=[])
        self.store.update_run(run_id=run.run_id, status="failed", error="boom", result="temp")
        updated = self.store.update_run(run_id=run.run_id, status="succeeded", error=None, result=None)
        self.assertIsNone(updated.error)
        self.assertIsNone(updated.result)

    def test_store_prunes_old_runs_when_capacity_exceeded(self):
        original_max = InMemoryRunStore.MAX_STORED_RUNS
        InMemoryRunStore.MAX_STORED_RUNS = 2
        try:
            # Create and mark as terminal to allow pruning
            run1 = self.store.create_run(conversation_id="conv-1", message="m1", selected_documents=[])
            self.store.update_run(run_id=run1.run_id, status="succeeded", result="done")

            run2 = self.store.create_run(conversation_id="conv-2", message="m2", selected_documents=[])
            self.store.update_run(run_id=run2.run_id, status="succeeded", result="done")

            # Third run triggers pruning of oldest terminal run (run1)
            run3 = self.store.create_run(conversation_id="conv-3", message="m3", selected_documents=[])

            # run1 should be pruned, run2 and run3 remain
            with self.assertRaises(RunNotFoundError):
                self.store.get_run(run1.run_id)
            self.assertEqual(self.store.get_run(run2.run_id).conversation_id, "conv-2")
            self.assertEqual(self.store.get_run(run3.run_id).conversation_id, "conv-3")
        finally:
            InMemoryRunStore.MAX_STORED_RUNS = original_max


if __name__ == "__main__":
    unittest.main()
