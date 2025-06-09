from langchain.tools import BaseTool
from typing import Dict, Any, Optional
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ScratchpadTool(BaseTool):
    """
    Scratchpad tool for the agent's temporary memory and context management.
    
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

Use this tool as your working memory to:
- Remember important context during complex conversations
- Track progress on multi-step tasks and plans
- Store intermediate results when breaking down problems
- Keep reference notes when handling multiple subtasks
- Maintain important user preferences or details
- Create and reference action plans as work progresses
- Remember key decisions or facts that may be relevant later

You have full autonomy to use this for any memory/context needs.

Commands:
- "save <note>" - Save important context or information
- "read" - Review all your current notes and context
- "search <term>" - Find specific information in your notes
- "delete <number>" - Remove specific notes when no longer needed
- "clear" - Clear all notes when starting fresh or task is complete
- "update <number> <new_content>" - Update existing note

The agent should proactively use this tool for better context management."""
    
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
    
    def _run(self, query: str) -> str:
        """Execute scratchpad operations."""
        try:
            from datetime import datetime
            query = query.strip().lower()
            
            # Load existing notes
            notes = self._load_notes()
            
            # Parse command
            if query.startswith(('save ', 'write ', 'add ')):
                # Save new note
                note_content = query.split(' ', 1)[1] if ' ' in query else ""
                if not note_content:
                    return "Please provide the note content. Example: 'save Remember to buy groceries'"
                
                new_note = {
                    "id": len(notes) + 1,
                    "content": note_content,
                    "timestamp": datetime.now().isoformat(),
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                notes.append(new_note)
                
                if self._save_notes(notes):
                    return f"✅ Note saved: \"{note_content}\"\n\nYou now have {len(notes)} note(s) in your scratchpad."
                else:
                    return "❌ Error: Could not save note. Please try again."
            
            elif query in ['read', 'show', 'show notes', 'list', 'all']:
                # Show all notes
                if not notes:
                    return "📝 Your scratchpad is empty. Use 'save <note>' to add your first note."
                
                response = f"📝 **Your Scratchpad** ({len(notes)} note(s)):\n\n"
                for note in notes:
                    response += f"**{note['id']}.** {note['content']}\n"
                    response += f"   *Saved: {note['created']}*\n\n"
                
                return response.strip()
            
            elif query.startswith('search '):
                # Search notes
                search_term = query.split(' ', 1)[1] if ' ' in query else ""
                if not search_term:
                    return "Please provide a search term. Example: 'search dentist'"
                
                matching_notes = [
                    note for note in notes 
                    if search_term.lower() in note['content'].lower()
                ]
                
                if not matching_notes:
                    return f"🔍 No notes found containing '{search_term}'"
                
                response = f"🔍 **Search results for '{search_term}'** ({len(matching_notes)} found):\n\n"
                for note in matching_notes:
                    response += f"**{note['id']}.** {note['content']}\n"
                    response += f"   *Saved: {note['created']}*\n\n"
                
                return response.strip()
            
            elif query.startswith('update '):
                # Update existing note
                try:
                    parts = query.split(' ', 2)
                    if len(parts) < 3:
                        return "❌ Invalid update format. Example: 'update 2 New content for this note'"
                    
                    note_id = int(parts[1])
                    new_content = parts[2]
                    
                    note_to_update = next((note for note in notes if note['id'] == note_id), None)
                    
                    if not note_to_update:
                        return f"❌ Note #{note_id} not found. Use 'read' to see all notes."
                    
                    old_content = note_to_update['content']
                    note_to_update['content'] = new_content
                    note_to_update['updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    if self._save_notes(notes):
                        return f"✅ Updated note #{note_id}\n\nOld: \"{old_content}\"\nNew: \"{new_content}\""
                    else:
                        return "❌ Error: Could not update note. Please try again."
                        
                except ValueError:
                    return "❌ Invalid note number. Example: 'update 3 Updated note content'"
            
            elif query.startswith('update '):
                # Update existing note
                try:
                    parts = query.split(' ', 2)
                    if len(parts) < 3:
                        return "❌ Invalid update format. Example: 'update 2 New content for this note'"
                    
                    note_id = int(parts[1])
                    new_content = parts[2]
                    
                    note_to_update = next((note for note in notes if note['id'] == note_id), None)
                    
                    if not note_to_update:
                        return f"❌ Note #{note_id} not found. Use 'read' to see all notes."
                    
                    from datetime import datetime
                    old_content = note_to_update['content']
                    note_to_update['content'] = new_content
                    note_to_update['updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    if self._save_notes(notes):
                        return f"✅ Updated note #{note_id}\n\nOld: \"{old_content}\"\nNew: \"{new_content}\""
                    else:
                        return "❌ Error: Could not update note. Please try again."
                        
                except ValueError:
                    return "❌ Invalid note number. Example: 'update 3 Updated note content'"
            
            elif query.startswith('delete '):
                # Delete specific note
                try:
                    note_id = int(query.split(' ', 1)[1])
                    note_to_delete = next((note for note in notes if note['id'] == note_id), None)
                    
                    if not note_to_delete:
                        return f"❌ Note #{note_id} not found. Use 'show notes' to see all notes."
                    
                    notes = [note for note in notes if note['id'] != note_id]
                    
                    if self._save_notes(notes):
                        return f"✅ Deleted note #{note_id}: \"{note_to_delete['content']}\"\n\nYou now have {len(notes)} note(s) remaining."
                    else:
                        return "❌ Error: Could not delete note. Please try again."
                        
                except ValueError:
                    return "❌ Invalid note number. Example: 'delete 3'"
            
            elif query in ['clear', 'clear all', 'delete all']:
                # Clear all notes
                if not notes:
                    return "📝 Your scratchpad is already empty."
                
                if self._save_notes([]):
                    return f"✅ Cleared all {len(notes)} note(s) from your scratchpad."
                else:
                    return "❌ Error: Could not clear notes. Please try again."
            
            elif query in ['help', 'commands']:
                # Show help
                return """📝 **Agent Scratchpad Commands:**

**Save context:**
- `save <note>` - Save important context or information
- `write <note>` - Same as save
- `add <note>` - Same as save

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
                return f"""❌ Unknown scratchpad command: '{query}'

Available commands:
- save <note> - Save important context
- read - Review all notes
- search <term> - Find specific information
- update <number> <content> - Update existing note
- delete <number> - Remove note when no longer needed
- clear - Clear all notes when starting fresh
- help - Show detailed help

Example: "save User prefers morning meetings" """
        
        except Exception as e:
            logger.error(f"Scratchpad tool error: {str(e)}")
            return f"❌ Error in scratchpad: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the scratchpad tool."""
        return self._run(query)
