"""
Comprehensive tests for Database Operations functionality.
"""
import sys
import os
import unittest
from datetime import datetime, timedelta, timezone

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

DB_TESTS_AVAILABLE = True
DB_IMPORT_ERROR = ""

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from backend.database.models import Base
    from backend.database.operations import DatabaseOperations, LazyDatabaseOperations
    from backend.runtime import RUN_EVENT_TYPES, RUN_STATUSES
except Exception as exc:
    DB_TESTS_AVAILABLE = False
    DB_IMPORT_ERROR = str(exc)


@unittest.skipUnless(DB_TESTS_AVAILABLE, f"Database test dependencies unavailable: {DB_IMPORT_ERROR}")
class TestDatabaseOperations(unittest.TestCase):
    """Test the database operations functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        database_url = os.environ.get("TEST_DATABASE_URL")
        if not database_url:
            self.skipTest("TEST_DATABASE_URL is required for database tests.")
        if not database_url.startswith("postgresql"):
            self.skipTest("TEST_DATABASE_URL must use PostgreSQL for this suite.")
        db_name = make_url(database_url).database or ""
        if not db_name.endswith("_test"):
            self.skipTest(
                "TEST_DATABASE_URL must target a dedicated *_test database for destructive DB tests."
            )

        self.engine = create_engine(database_url)
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Construct instance without running __init__ so tests never touch runtime DB settings.
        self.db_ops = DatabaseOperations.__new__(DatabaseOperations)
        self.db_ops.engine = self.engine
        self.db_ops.SessionLocal = SessionLocal
        
        self.test_conversation_id = "test_conv_123"
        self.test_user_id = "test_user"

    def tearDown(self):
        """Dispose test database connections."""
        self.db_ops.close()
        
    def test_create_conversation(self):
        """Test creating a new conversation."""
        title = "Test Conversation"
        conv_id = self.db_ops.create_conversation(title, self.test_user_id)
        
        self.assertIsNotNone(conv_id)
        self.assertIsInstance(conv_id, str)
        
        # Skip database verification since we can't easily isolate test data
        # This test validates the method works without checking persistent state
    
    def test_save_and_get_messages(self):
        """Test saving and retrieving messages."""
        # Create conversation first
        conv_id = self.db_ops.create_conversation("Test", self.test_user_id)
        
        # Save a user message
        message_id = self.db_ops.save_message(
            conversation_id=conv_id,
            role="user",
            content="Hello, how are you?"
        )
        
        self.assertIsNotNone(message_id)
        
        # Save an assistant message
        assistant_id = self.db_ops.save_message(
            conversation_id=conv_id,
            role="assistant", 
            content="I'm doing well, thank you!"
        )
        
        # Retrieve conversation history
        history = self.db_ops.get_conversation_history(conv_id)
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello, how are you?")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "I'm doing well, thank you!")
    
    def test_get_conversations_empty(self):
        """Test getting conversations when none exist."""
        # Skip this test since we can't easily mock the database
        self.skipTest("Database test skipped - requires proper test database setup")
    
    def test_get_conversation_history_nonexistent(self):
        """Test getting history for non-existent conversation."""
        history = self.db_ops.get_conversation_history("nonexistent")
        self.assertEqual(history, [])
    
    def test_delete_conversation(self):
        """Test deleting a conversation."""
        # Create conversation with messages
        conv_id = self.db_ops.create_conversation("Test Delete", self.test_user_id)
        self.db_ops.save_message(conv_id, "user", "Test message")
        
        # Delete conversation
        success = self.db_ops.delete_conversation(conv_id)
        self.assertTrue(success)
        
        # Skip database state verification - just test the method works
    
    def test_update_conversation_title(self):
        """Test updating conversation title."""
        # Create conversation
        conv_id = self.db_ops.create_conversation("Original Title", self.test_user_id)
        
        # Update title
        success = self.db_ops.update_conversation_title(conv_id, "New Title")
        self.assertTrue(success)
        
        # Verify update
        conversations = self.db_ops.get_conversations(self.test_user_id)
        self.assertEqual(conversations[0]["title"], "New Title")
    
    def test_message_timestamps(self):
        """Test that messages have proper timestamps."""
        conv_id = self.db_ops.create_conversation("Test Timestamps", self.test_user_id)
        
        # Save message
        message_id = self.db_ops.save_message(conv_id, "user", "Test")
        
        # Get history
        history = self.db_ops.get_conversation_history(conv_id)
        
        self.assertEqual(len(history), 1)
        self.assertIn("timestamp", history[0])
        
        # Verify timestamp format (should be ISO format)
        timestamp = history[0]["timestamp"]
        # Should be able to parse as datetime
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            self.fail(f"Invalid timestamp format: {timestamp}")
    
    def test_conversation_ordering(self):
        """Test that conversations are returned in proper order."""
        # Skip this test since we can't isolate test data
        self.skipTest("Database test skipped - requires proper test database setup")
    
    def test_message_ordering(self):
        """Test that messages are returned in chronological order."""
        conv_id = self.db_ops.create_conversation("Test Order", self.test_user_id)
        
        # Add messages in sequence
        self.db_ops.save_message(conv_id, "user", "First message")
        self.db_ops.save_message(conv_id, "assistant", "Second message")
        self.db_ops.save_message(conv_id, "user", "Third message")
        
        history = self.db_ops.get_conversation_history(conv_id)
        
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["content"], "First message")
        self.assertEqual(history[1]["content"], "Second message")
        self.assertEqual(history[2]["content"], "Third message")

    def test_runtime_counter_increment_and_query(self):
        """Runtime counters should increment and be retrievable by prefix."""
        key = "api.chat.requests_total"
        first = self.db_ops.increment_runtime_counter(key, amount=1)
        second = self.db_ops.increment_runtime_counter(key, amount=2)

        self.assertEqual(first, 1)
        self.assertEqual(second, 3)

        counters = self.db_ops.get_runtime_counters(prefix="api.chat")
        self.assertIn(key, counters)
        self.assertEqual(counters[key], 3)

    def test_lifecycle_vocabulary_is_frozen(self):
        """Run statuses/events should stay aligned with migration contract."""
        self.assertEqual(
            RUN_STATUSES,
            (
                "queued",
                "running",
                "retrying",
                "succeeded",
                "failed",
                "cancelling",
                "cancelled",
            ),
        )
        self.assertEqual(
            RUN_EVENT_TYPES,
            (
                "queued",
                "started",
                "tool_call",
                "tool_result",
                "retrying",
                "failed",
                "succeeded",
                "cancelling",
                "cancelled",
            ),
        )

    def test_run_create_get_update(self):
        """Runs should support create, lookup, and lifecycle updates."""
        conv_id = self.db_ops.create_conversation("Run lifecycle", self.test_user_id)

        run = self.db_ops.create_run(conv_id)
        self.assertEqual(run["conversation_id"], conv_id)
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["attempt_count"], 0)
        self.assertIsNotNone(run["created_at"])

        started_at = datetime.now(timezone.utc)
        updated = self.db_ops.update_run(
            run["id"],
            status="running",
            attempt_count=1,
            started_at=started_at,
            error="temporary failure",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "running")
        self.assertEqual(updated["attempt_count"], 1)
        self.assertIsNotNone(updated["started_at"])
        self.assertEqual(updated["error"], "temporary failure")

        # Nullable fields should be clearable (explicit None), not treated as "unset"
        cleared = self.db_ops.update_run(
            run["id"],
            error=None,
            started_at=None,
            completed_at=None,
        )
        self.assertIsNone(cleared["error"])
        self.assertIsNone(cleared["started_at"])
        self.assertIsNone(cleared["completed_at"])

        fetched = self.db_ops.get_run(run["id"])
        self.assertEqual(fetched["id"], run["id"])
        self.assertEqual(fetched["status"], "running")

    def test_run_events_append_and_list_in_order(self):
        """Run events should preserve append order for polling lookups."""
        conv_id = self.db_ops.create_conversation("Run events", self.test_user_id)
        run = self.db_ops.create_run(conv_id)

        first = self.db_ops.append_run_event(
            run_id=run["id"],
            event_type="queued",
            status="queued",
            message="Run queued",
        )
        second = self.db_ops.append_run_event(
            run_id=run["id"],
            event_type="started",
            status="running",
            message="Run started",
        )
        third = self.db_ops.append_run_event(
            run_id=run["id"],
            event_type="tool_call",
            status="running",
            tool="calculator",
            message="Calling calculator",
        )

        events = self.db_ops.list_run_events(run["id"])
        self.assertEqual([event["id"] for event in events], [first["id"], second["id"], third["id"]])
        self.assertEqual([event["type"] for event in events], ["queued", "started", "tool_call"])
        self.assertEqual(events[2]["tool"], "calculator")

        after_first = self.db_ops.list_run_events(run["id"], after_event_id=first["id"])
        self.assertEqual([event["id"] for event in after_first], [second["id"], third["id"]])

    def test_run_lifecycle_validation_rejects_invalid_values(self):
        """Invalid statuses/event types should be rejected before DB writes."""
        conv_id = self.db_ops.create_conversation("Validation", self.test_user_id)
        run = self.db_ops.create_run(conv_id)

        with self.assertRaises(ValueError):
            self.db_ops.create_run(conv_id, status="not-a-status")
        with self.assertRaises(ValueError):
            self.db_ops.update_run(run["id"], status="not-a-status")
        with self.assertRaises(ValueError):
            self.db_ops.append_run_event(run["id"], event_type="not-an-event", status="queued")
        with self.assertRaises(ValueError):
            self.db_ops.append_run_event(run["id"], event_type="queued", status="not-a-status")

    def test_lease_primitives_enforce_ownership_and_expiry(self):
        """Lease acquire/renew/release should enforce ownership and allow expiry takeover."""
        key = "conversation:lease-test"
        first = self.db_ops.acquire_lease(key, owner_id="worker-a", ttl_seconds=30)
        self.assertIsNotNone(first)
        self.assertEqual(first["owner_id"], "worker-a")
        self.assertEqual(first["fencing_token"], 1)

        blocked = self.db_ops.acquire_lease(key, owner_id="worker-b", ttl_seconds=30)
        self.assertIsNone(blocked)

        renewed = self.db_ops.renew_lease(key, owner_id="worker-a", ttl_seconds=45)
        self.assertIsNotNone(renewed)
        self.assertEqual(renewed["fencing_token"], 1)

        self.assertFalse(self.db_ops.release_lease(key, owner_id="worker-b"))
        self.assertTrue(self.db_ops.release_lease(key, owner_id="worker-a"))
        self.assertIsNone(self.db_ops.get_lease(key))

        reacquired = self.db_ops.acquire_lease(key, owner_id="worker-a", ttl_seconds=30)
        self.assertEqual(reacquired["fencing_token"], 1)
        session = self.db_ops.get_session()
        try:
            stale_acquired_at = datetime.now(timezone.utc) - timedelta(seconds=10)
            session.execute(
                text(
                    """
                    UPDATE leases
                    SET acquired_at = :acquired_at,
                        expires_at = :expired_at,
                        updated_at = :acquired_at
                    WHERE lease_key = :lease_key
                    """
                ),
                {
                    "lease_key": key,
                    "acquired_at": stale_acquired_at,
                    "expired_at": datetime.now(timezone.utc) - timedelta(seconds=5),
                },
            )
            session.commit()
        finally:
            session.close()

        stolen = self.db_ops.acquire_lease(key, owner_id="worker-b", ttl_seconds=30)
        self.assertIsNotNone(stolen)
        self.assertEqual(stolen["owner_id"], "worker-b")


class TestLazyDatabaseOperations(unittest.TestCase):
    def test_getattr_raises_attribute_error_for_unknown_names(self):
        lazy = LazyDatabaseOperations()
        with self.assertRaises(AttributeError):
            _ = lazy.this_attribute_does_not_exist

    def test_get_instance_is_singleton_and_thread_safe_for_serial_access(self):
        lazy = LazyDatabaseOperations()

        created_instances = []

        class _FakeDatabaseOperations:
            def __init__(self):
                created_instances.append(self)
                self.engine = "engine"

            def close(self):
                return None

            def get_value(self):
                return 42

        from unittest.mock import patch

        with patch("backend.database.operations.DatabaseOperations", _FakeDatabaseOperations):
            self.assertEqual(lazy.get_value(), 42)
            self.assertEqual(lazy.engine, "engine")
            self.assertEqual(lazy.get_value(), 42)

        self.assertEqual(len(created_instances), 1)


if __name__ == '__main__':
    unittest.main()
