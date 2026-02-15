# handlers/note_handler.py
import json
from datetime import datetime
from utils.helpers import load_json_file, save_json_file, generate_id

NOTES_FILE = 'data/notes.json'

class NoteHandler:
    def __init__(self):
        self.notes = load_json_file(NOTES_FILE, [])
    
    def handle(self, action, parsed, command):
        """Route note actions to appropriate methods."""
        if action == 'list_notes':
            return self.list_notes()
        elif action == 'create_note':
            return self.create_note(parsed)
        elif action == 'get_note':
            return self.get_note(parsed)
        elif action == 'delete_note':
            return self.delete_note(parsed)
        elif action == 'search_notes':
            return self.search_notes(parsed)
        else:
            return {'success': False, 'message': 'Unknown note action'}
    
    def list_notes(self):
        """List all notes."""
        if not self.notes:
            return {
                'success': True,
                'action': 'list_notes',
                'data': [],
                'message': 'No notes found'
            }
        
        # Sort by updated date (newest first)
        sorted_notes = sorted(self.notes, key=lambda x: x.get('updated', ''), reverse=True)
        
        return {
            'success': True,
            'action': 'list_notes',
            'data': sorted_notes,
            'message': f'Found {len(sorted_notes)} notes'
        }
    
    def create_note(self, parsed):
        """Create a new note."""
        title = parsed.get('title', 'Untitled')
        content = parsed.get('content', '')
        
        if not content:
            return {'success': False, 'message': 'Note content is required'}
        
        now = datetime.now().isoformat()
        note = {
            'id': generate_id(),
            'title': title,
            'content': content,
            'created': now,
            'updated': now
        }
        
        self.notes.append(note)
        save_json_file(NOTES_FILE, self.notes)
        
        return {
            'success': True,
            'action': 'create_note',
            'data': note,
            'message': f'Note created: {title}'
        }
    
    def get_note(self, parsed):
        """Get a specific note."""
        note_id = parsed.get('note_id')
        
        for note in self.notes:
            if note['id'] == note_id:
                return {
                    'success': True,
                    'action': 'get_note',
                    'data': note,
                    'message': f'Note: {note["title"]}'
                }
        
        return {'success': False, 'message': f'Note {note_id} not found'}
    
    def delete_note(self, parsed):
        """Delete a note."""
        note_id = parsed.get('note_id')
        
        for i, note in enumerate(self.notes):
            if note['id'] == note_id:
                deleted = self.notes.pop(i)
                save_json_file(NOTES_FILE, self.notes)
                return {
                    'success': True,
                    'action': 'delete_note',
                    'message': f'Note deleted: {deleted["title"]}'
                }
        
        return {'success': False, 'message': f'Note {note_id} not found'}
    
    def search_notes(self, parsed):
        """Search notes by keyword."""
        keyword = parsed.get('keyword', '').lower()
        
        if not keyword:
            return {'success': False, 'message': 'Search keyword is required'}
        
        results = []
        for note in self.notes:
            if (keyword in note['title'].lower() or 
                keyword in note['content'].lower()):
                results.append(note)
        
        return {
            'success': True,
            'action': 'search_notes',
            'data': results,
            'message': f'Found {len(results)} notes matching "{keyword}"'
        }
    
    def get_all_notes(self):
        """API endpoint to get all notes."""
        return {'success': True, 'data': self.notes}
    
    def create_note_api(self, data):
        """API endpoint to create a note."""
        now = datetime.now().isoformat()
        note = {
            'id': generate_id(),
            'title': data.get('title', 'Untitled'),
            'content': data.get('content', ''),
            'created': now,
            'updated': now
        }
        self.notes.append(note)
        save_json_file(NOTES_FILE, self.notes)
        return {'success': True, 'data': note}
    
    def delete_note_api(self, note_id):
        """API endpoint to delete a note."""
        for i, note in enumerate(self.notes):
            if note['id'] == note_id:
                self.notes.pop(i)
                save_json_file(NOTES_FILE, self.notes)
                return {'success': True}
        return {'success': False, 'message': 'Note not found'}