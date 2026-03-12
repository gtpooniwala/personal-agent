import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

AVAILABLE = True
IMPORT_ERROR = ""

try:
    from sqlalchemy import create_engine, event, inspect
    from sqlalchemy.orm import sessionmaker

    from backend.database.models import Base, Conversation
    from backend.database.operations import DatabaseOperations
except (ImportError, ModuleNotFoundError) as exc:
    AVAILABLE = False
    IMPORT_ERROR = str(exc)


@unittest.skipUnless(AVAILABLE, f"Database hot-path test dependencies unavailable: {IMPORT_ERROR}")
class TestDatabaseHotPaths(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        self.db_ops = DatabaseOperations.__new__(DatabaseOperations)
        self.db_ops.engine = self.engine
        self.db_ops.SessionLocal = session_local

    def tearDown(self):
        self.db_ops.close()

    def test_get_conversations_uses_single_aggregate_query(self):
        user_id = "hot-path-user"
        older_id = self.db_ops.create_conversation("Older", user_id)
        newer_id = self.db_ops.create_conversation("Newer", user_id)
        empty_id = self.db_ops.create_conversation("Empty", user_id)

        self.db_ops.save_message(older_id, "user", "first older")
        self.db_ops.save_message(older_id, "assistant", "second older")
        self.db_ops.save_message(newer_id, "user", "only newer")

        base_time = datetime.now(timezone.utc)
        session = self.db_ops.get_session()
        try:
            conversations = {
                row.id: row
                for row in session.query(Conversation).filter(
                    Conversation.id.in_([older_id, newer_id, empty_id])
                )
            }
            conversations[older_id].updated_at = base_time - timedelta(minutes=2)
            conversations[empty_id].updated_at = base_time - timedelta(minutes=1)
            conversations[newer_id].updated_at = base_time
            session.commit()
        finally:
            session.close()

        statements = []

        def before_cursor_execute(
            conn,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", before_cursor_execute)
        try:
            conversations = self.db_ops.get_conversations(user_id)
        finally:
            event.remove(self.engine, "before_cursor_execute", before_cursor_execute)

        self.assertEqual([newer_id, empty_id, older_id], [row["id"] for row in conversations])
        self.assertEqual(1, conversations[0]["message_count"])
        self.assertEqual(0, conversations[1]["message_count"])
        self.assertEqual(2, conversations[2]["message_count"])
        self.assertEqual(len(statements), 1, statements)
        self.assertIn("count(", statements[0].lower())

    def test_hot_path_indexes_exist(self):
        inspector = inspect(self.engine)

        conversation_indexes = {
            index["name"] for index in inspector.get_indexes("conversations")
        }
        message_indexes = {
            index["name"] for index in inspector.get_indexes("messages")
        }

        self.assertIn("ix_conversations_user_id_updated_at", conversation_indexes)
        self.assertIn("ix_messages_conversation_id_timestamp", message_indexes)
