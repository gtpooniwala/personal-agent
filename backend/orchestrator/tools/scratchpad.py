from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, Literal
import json
import os
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)


class ScratchpadInput(BaseModel):
    """Input model for scratchpad tool - expects structured commands from LLM."""
    
    action: Literal["save", "read", "search", "delete", "clear", "update", "help"] = Field(
        description="The action to perform: save, read, search, delete, clear, update, or help"
    )
    
    content: Optional[str] = Field(
        default=None,
        description="Content for save/search/update operations. Required for save, search, and update actions."
    )
    
    note_number: Optional[int] = Field(
        default=None,
        description="Note number for delete/update operations. Required for delete and update actions."
    )
    
    @validator('content')
    def validate_content_for_action(cls, v, values):
        """Validate that content is provided when required for specific actions."""
        action = values.get('action')
        
        if action in ['save', 'search', 'update'] and not v:
            raise ValueError(f"Content is required for '{action}' action")
            
        return v
    
    @validator('note_number')
    def validate_note_number_for_action(cls, v, values):
        """Validate that note_number is provided when required for specific actions."""
        action = values.get('action')
        
        if action in ['delete', 'update'] and v is None:
            raise ValueError(f"Note number is required for '{action}' action")
            
        return v


class ScratchpadTool(BaseTool):
    """
    Agent's temporary memory and context management tool with Pydantic input validation.
    
    This tool serves as the agent's working memory for managing context, tasks, and information
    across complex conversations and multi-step operations. The agent should use this tool to:
    
    - Remember important context or information during long conversations
    - Track progress on multi-step tasks or complex requests
    - Store intermediate results when breaking down complex problems
    - Keep reference notes when switching between subtasks
    - Maintain context when conversations span multiple topics
    - Store user preferences or important details mentioned in conversation
    - Create action plans and refer back to them as work progresses
    - Remember key facts or decisions that might be relevant later
    
    The agent has full autonomy to decide when and how to use the scratchpad based on
    the conversation's complexity and context management needs.
    """
    
    name = "scratchpad"
    description = """Agent's temporary memory and context management tool.

Use this tool to manage your working memory with structured commands:

Required parameters:
- action: The action to perform (save/read/search/delete/clear/update/help)
- content: Text content (required for save, search, update actions)  
- note_number: Integer ID (required for delete, update actions)

Examples:
- To save: action="save", content="User prefers morning meetings"
- To read all: action="read"
- To search: action="search", content="meetings" 
- To update: action="update", note_number=2, content="Updated content"
- To delete: action="delete", note_number=3
- To clear all: action="clear"

Use this proactively for context management during complex conversations."""
    
    args_schema = ScratchpadInput
    
    def __init__(self, user_id: str = "default"):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, '_user_id', user_id)
        object.__setattr__(self, '_notes_file', self._get_notes_file_path())
        object.__setattr__(self, '_notes_dir', Path("data/scratchpad"))
        
        # Ensure directory exists
        self._notes_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_notes_file_path(self) -> Path:
        """Get the notes file path for the user."""
        return Path(f"data/scratchpad/{self._user_id}_notes.json")
    
    def _load_notes(self) -> list:
        """Load notes from file."""
        try:
            if self._notes_file.exists():
                with open(self._notes_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading notes: {str(e)}")
            return []
    
    def _save_notes(self, notes: list) -> bool:
        """Save notes to file."""
        try:
            with open(self._notes_file, 'w', encoding='utf-8') as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving notes: {str(e)}")
            return False
    
    def _run(self, action: str, content: Optional[str] = None, note_number: Optional[int] = None) -> str:
        """Execute scratchpad operations using Pydantic-validated input."""
        try:
            from datetime import datetime
            
            # Load existing notes
            notes = self._load_notes()
            
            # Execute action based on structured input
            if action == 'save':
                if not content:
                    return "Please provide the note content. Example: 'save Remember to buy groceries'"
                
                new_note = {
                    "id": len(notes) + 1,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                notes.append(new_note)
                
                if self._save_notes(notes):
                    return f"✅ Note saved: \"{content}\"\n\nYou now have {len(notes)} note(s) in your scratchpad."
                else:
                    return "❌ Error: Could not save note. Please try again."
            
            elif action == 'read':
                # Show all notes
                if not notes:
                    return "📝 Your scratchpad is empty. Use 'save <note>' to add your first note."
                
                response = f"📝 **Your Scratchpad** ({len(notes)} note(s)):\n\n"
                for note in notes:
                    response += f"**{note['id']}.** {note['content']}\n"
                    response += f"   *Saved: {note['created']}*\n\n"
                
                return response.strip()
            
            elif action == 'search':
                # Search notes
                if not content:
                    return "Please provide a search term. Example: 'search dentist'"
                
                matching_notes = [
                    note for note in notes 
                    if content.lower() in note['content'].lower()
                ]
                
                if not matching_notes:
                    return f"🔍 No notes found containing '{content}'"
                
                response = f"🔍 **Search results for '{content}'** ({len(matching_notes)} found):\n\n"
                for note in matching_notes:
                    response += f"**{note['id']}.** {note['content']}\n"
                    response += f"   *Saved: {note['created']}*\n\n"
                
                return response.strip()
            
            elif action == 'update':
                # Update existing note
                if not note_number or not content:
                    return "❌ Invalid update format. Example: 'update 2 New content for this note'"
                
                note_to_update = next((note for note in notes if note['id'] == note_number), None)
                
                if not note_to_update:
                    return f"❌ Note #{note_number} not found. Use 'read' to see all notes."
                
                old_content = note_to_update['content']
                note_to_update['content'] = content
                note_to_update['updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                if self._save_notes(notes):
                    return f"✅ Updated note #{note_number}\n\nOld: \"{old_content}\"\nNew: \"{content}\""
                else:
                    return "❌ Error: Could not update note. Please try again."
            
            elif action == 'delete':
                # Delete specific note
                if not note_number:
                    return "❌ Invalid delete format. Example: 'delete 3'"
                
                note_to_delete = next((note for note in notes if note['id'] == note_number), None)
                
                if not note_to_delete:
                    return f"❌ Note #{note_number} not found. Use 'read' to see all notes."
                
                notes = [note for note in notes if note['id'] != note_number]
                
                if self._save_notes(notes):
                    return f"✅ Deleted note #{note_number}: \"{note_to_delete['content']}\"\n\nYou now have {len(notes)} note(s) remaining."
                else:
                    return "❌ Error: Could not delete note. Please try again."
            
            elif action == 'clear':
                # Clear all notes
                if not notes:
                    return "📝 Your scratchpad is already empty."
                
                note_count = len(notes)
                if self._save_notes([]):
                    return f"✅ Cleared all {note_count} note(s) from your scratchpad."
                else:
                    return "❌ Error: Could not clear notes. Please try again."
            
            elif action == 'help':
                # Show help
                return """📝 **Agent Scratchpad Commands:**

**Save context:**
- `save <note>` - Save important context or information

**Review context:**
- `read` - Review all current notes and context
- `search <term>` - Find specific information in notes

**Manage context:**
- `update <number> <content>` - Update existing note
- `delete <number>` - Remove specific note when no longer needed
- `clear` - Clear all notes when starting fresh

**Examples:**
- "save User wants to plan a trip to Japan in March"
- "save Step 1 complete: gathered requirements"
- "update 2 Updated plan based on new requirements"
- "search Japan"

Use this as your working memory for complex tasks and conversations."""
            
            else:
                # Unknown command
                return f"""❌ Unknown scratchpad action: '{action}'

Available actions:
- save - Save important context (requires content)
- read - Review all notes
- search - Find specific information (requires content)
- update - Update existing note (requires note_number and content)
- delete - Remove note (requires note_number)
- clear - Clear all notes when starting fresh
- help - Show detailed help

Example structured input: action="save", content="User prefers morning meetings" """
        
        except Exception as e:
            logger.error(f"Scratchpad tool error: {str(e)}")
            return f"❌ Error in scratchpad: {str(e)}"

    async def _arun(self, action: str, content: Optional[str] = None, note_number: Optional[int] = None) -> str:
        """Async version of the scratchpad tool."""
        return self._run(action, content, note_number)
