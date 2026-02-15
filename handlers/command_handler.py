# handlers/command_handler.py
import re
import json

class CommandHandler:
    def __init__(self, co_client):
        self.co = co_client
    
    def parse_command(self, command, user_id=None, friends_collection=None):
        """
        Parse user command using AI and heuristics.
        If user_id and friends_collection are provided, resolve friend names to emails first.
        """
        # Resolve friend names if we have user context
        if user_id and friends_collection:
            command = self._resolve_friend_names(command, user_id, friends_collection)
        
        # Try LLM parsing first
        parsed = self._llm_parse(command)
        if parsed:
            return parsed
        
        # Fall back to heuristics
        return self._heuristic_parse(command)
    
    def _resolve_friend_names(self, command, user_id, friends_collection):
        """
        Replace friend names in command with their email addresses.
        """
        import re
        
        # Split the command into words
        words = command.split()
        resolved_words = []
        
        # Common words that should never be treated as friend names
        common_words = {
            'to', 'with', 'for', 'from', 'the', 'a', 'an', 'and', 'or', 'but', 
            'in', 'on', 'at', 'by', 'about', 'file', 'send', 'email', 'draft',
            'schedule', 'meet', 'create', 'list', 'show', 'view', 'delete',
            'task', 'note', 'event', 'image', 'folder', 'summary', 'my', 'all',
            'upcoming', 'today', 'tomorrow', 'next', 'this', 'that', 'please',
            'can', 'you', 'i', 'me', 'help', 'exit', 'quit', 'bye', 'close',
            'what', 'where', 'when', 'who', 'how', 'why', 'is', 'are', 'was',
            'were', 'will', 'would', 'could', 'should', 'have', 'has', 'had',
            'search', 'find', 'for'  # Added search related words
        }
        
        for word in words:
            # Skip if it looks like an email already
            if '@' in word:
                resolved_words.append(word)
                continue
            
            # Skip if it's a common word
            if word.lower() in common_words:
                resolved_words.append(word)
                continue
            
            # Skip if it's a number
            if word.isdigit():
                resolved_words.append(word)
                continue
            
            # Skip if it looks like a date or time
            if re.match(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)?', word.lower()):
                resolved_words.append(word)
                continue
            
            # Check if this word might be a friend name
            # Only check words that are likely names (capitalized or reasonable length)
            if len(word) > 2:  # Names are usually longer than 2 characters
                try:
                    # Case-insensitive search in MongoDB
                    import re as regex
                    pattern = regex.compile(f'^{re.escape(word)}$', regex.IGNORECASE)
                    friend = friends_collection.find_one({
                        'user_id': user_id,
                        'name': pattern
                    })
                    
                    if friend:
                        # Replace with email
                        resolved_words.append(friend['email'])
                        continue
                except Exception as e:
                    print(f"⚠️ Friend resolution error for '{word}': {e}")
                    resolved_words.append(word)
                    continue
            
            # If no match found, keep original word
            resolved_words.append(word)
        
        return ' '.join(resolved_words)
    
    def _llm_parse(self, command):
        """Parse using Cohere LLM."""
        prompt = f"""
You are a command interpreter for a Google Workspace assistant.
Return ONLY a single valid JSON object, no prose, no markdown.

Valid actions:
1. {{"action":"list_files"}}
2. {{"action":"search_files","keyword":"budget"}}
3. {{"action":"show_images"}}
4. {{"action":"show_image","file_name":"image.jpg"}}
5. {{"action":"view_folder","folder_name":"Photos"}}
6. {{"action":"list_tasks"}}
7. {{"action":"add_task","text":"Buy groceries","due":"tomorrow"}}
8. {{"action":"complete_task","task_id":"123"}}
9. {{"action":"delete_task","task_id":"123"}}
10. {{"action":"list_notes"}}
11. {{"action":"create_note","title":"Meeting notes","content":"..."}}
12. {{"action":"get_note","note_id":"123"}}
13. {{"action":"delete_note","note_id":"123"}}
14. {{"action":"search_notes","keyword":"project"}}
15. {{"action":"list_events"}}
16. {{"action":"list_today"}}
17. {{"action":"list_date","date":"march 19"}}
18. {{"action":"create_event","title":"Meeting","date":"tomorrow","time":"2pm"}}
19. {{"action":"get_event","event_id":"123"}}
20. {{"action":"delete_event","event_id":"123"}}
21. {{"action":"delete_all_events"}}
22. {{"action":"confirm_delete_all","event_ids":["id1","id2"]}}
23. {{"action":"schedule_meet","title":"Team sync","date":"tomorrow","time":"2pm","attendees":["email@example.com"]}}
24. {{"action":"send_meet_invite","email":"person@example.com","event_id":"123"}}
25. {{"action":"draft_email","text":"I need to request sick leave"}}
26. {{"action":"draft_summary","file_name":"report.pdf","email":"optional@email.com"}}
27. {{"action":"show_draft"}}
28. {{"action":"clear_draft"}}
29. {{"action":"refine_draft","instruction":"make it more formal"}}
30. {{"action":"send_draft","email":["recipient@example.com"]}}
31. {{"action":"help"}}
32. {{"action":"exit"}}

Parse this command and output JSON only:
Command: {command}
"""

        try:
            resp = self.co.chat(
                model="command-r-plus-08-2024",
                message=prompt,
                temperature=0
            )
            text = (resp.text or "").strip()
            
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
            
            data = json.loads(text)
            if isinstance(data, dict) and "action" in data:
                return data
        except Exception as e:
            print(f"LLM parsing error: {e}")
            pass
        
        return None
    
    def _heuristic_parse(self, command):
        """Parse using pattern matching."""
        low = command.lower().strip()
        orig = command.strip()
        
        # Exit/Help
        if re.search(r"\b(exit|quit|bye|close)\b", low):
            return {"action": "exit"}
        if re.search(r"\b(help|\?|what can you do|commands)\b", low):
            return {"action": "help"}
        
        # Task commands
        if re.search(r"\blist\s+tasks?\b", low):
            return {"action": "list_tasks"}
        
        task_add = re.search(r"add\s+task:?\s*(.+?)(?:\s+due:\s*(.+))?$", low)
        if task_add:
            result = {"action": "add_task", "text": task_add.group(1).strip()}
            if task_add.group(2):
                result["due"] = task_add.group(2).strip()
            return result
        
        task_complete = re.search(r"complete\s+task\s+(\d+)", low)
        if task_complete:
            return {"action": "complete_task", "task_id": task_complete.group(1)}
        
        task_delete = re.search(r"delete\s+task\s+(\d+)", low)
        if task_delete:
            return {"action": "delete_task", "task_id": task_delete.group(1)}
        
        # Note commands
        if re.search(r"\blist\s+notes?\b", low):
            return {"action": "list_notes"}
        
        note_create = re.search(r"create\s+note:?\s*(.+?)\s*-\s*(.+)", low)
        if note_create:
            return {
                "action": "create_note",
                "title": note_create.group(1).strip(),
                "content": note_create.group(2).strip()
            }
        
        note_get = re.search(r"get\s+note\s+(\d+)", low)
        if note_get:
            return {"action": "get_note", "note_id": note_get.group(1)}
        
        note_delete = re.search(r"delete\s+note\s+(\d+)", low)
        if note_delete:
            return {"action": "delete_note", "note_id": note_delete.group(1)}
        
        note_search = re.search(r"search\s+notes?:?\s*(.+)", low)
        if note_search:
            return {"action": "search_notes", "keyword": note_search.group(1).strip()}
        
        # Calendar commands
        if re.search(r"\blist\s+events?\b", low):
            return {"action": "list_events"}
        
        if re.search(r"\blist\s+today\b", low):
            return {"action": "list_today"}
        
        # List events for a specific date
        date_match = re.search(r"what'?s on\s+(.+)", low) or re.search(r"events on\s+(.+)", low)
        if date_match:
            return {"action": "list_date", "date": date_match.group(1).strip()}
        
        event_create = re.search(r"create\s+event:?\s*(.+?)\s+on\s+(.+?)(?:\s+at\s+(.+))?$", low)
        if event_create:
            result = {
                "action": "create_event",
                "title": event_create.group(1).strip(),
                "date": event_create.group(2).strip()
            }
            if event_create.group(3):
                result["time"] = event_create.group(3).strip()
            return result
        
        event_get = re.search(r"get\s+event\s+(\d+)", low)
        if event_get:
            return {"action": "get_event", "event_id": event_get.group(1)}
        
        event_delete = re.search(r"delete\s+event\s+(\d+)", low)
        if event_delete:
            return {"action": "delete_event", "event_id": event_delete.group(1)}
        
        # Delete all events patterns
        delete_keywords = ['delete', 'remove', 'clear', 'erase']
        all_keywords = ['all', 'every', 'everything']
        event_keywords = ['event', 'events', 'calendar', 'appointment', 'appointments']
        
        words = low.split()
        
        # Check for combinations
        has_delete = any(kw in low for kw in delete_keywords)
        has_all = any(kw in low for kw in all_keywords)
        has_event = any(kw in low for kw in event_keywords)
        
        # Also check for phrases like "my calendar" or "upcoming events"
        has_my = 'my' in words
        has_upcoming = 'upcoming' in words
        
        # If we have delete + all + (events or calendar)
        if has_delete and has_all and has_event:
            return {"action": "delete_all_events"}
        
        # If we have clear + calendar
        if 'clear' in words and ('calendar' in words or 'schedule' in words):
            return {"action": "delete_all_events"}
        
        # If we have remove + all + (appointments or events)
        if has_delete and has_all and has_my and has_event:
            return {"action": "delete_all_events"}
        
        # Specific pattern matching for common phrases
        delete_all_patterns = [
            r"delete\s+all\s+(?:my\s+)?(?:upcoming\s+)?events",
            r"remove\s+all\s+(?:my\s+)?(?:upcoming\s+)?events",
            r"clear\s+all\s+(?:my\s+)?(?:upcoming\s+)?events",
            r"erase\s+all\s+(?:my\s+)?(?:upcoming\s+)?events",
            r"delete\s+(?:my\s+)?(?:entire|whole)\s+calendar",
            r"clear\s+(?:my\s+)?calendar",
            r"remove\s+all\s+(?:my\s+)?appointments",
            r"delete\s+everything\s+(?:from\s+)?(?:my\s+)?calendar",
            r"delete\s+all\s+the\s+events",
            r"delete\s+all\s+events",
            r"remove\s+all\s+events",
            r"clear\s+all\s+events",
        ]
        
        for pattern in delete_all_patterns:
            if re.search(pattern, low):
                return {"action": "delete_all_events"}
        
        # Confirmation commands
        if re.search(r"^(yes|yeah|yep|sure|confirm|go ahead)$", low):
            return {"action": "confirm_yes"}
        if re.search(r"^(no|nope|cancel|stop|abort|never mind)$", low):
            return {"action": "confirm_no"}
        
        # Meet commands
        meet_schedule = re.search(r"schedule\s+meet:?\s*(.+?)\s+on\s+(.+?)(?:\s+at\s+(.+?))?(?:\s+with\s+(.+))?$", low)
        if meet_schedule:
            result = {
                "action": "schedule_meet",
                "title": meet_schedule.group(1).strip(),
                "date": meet_schedule.group(2).strip()
            }
            if meet_schedule.group(3):
                result["time"] = meet_schedule.group(3).strip()
            if meet_schedule.group(4):
                emails = [e.strip() for e in meet_schedule.group(4).split(',')]
                result["attendees"] = emails
            return result
        
        meet_invite = re.search(r"send\s+meet\s+invite\s+to\s+([^\s]+@[^\s]+)(?:\s+for\s+(.+))?", low)
        if meet_invite:
            result = {
                "action": "send_meet_invite",
                "email": meet_invite.group(1).strip()
            }
            if meet_invite.group(2):
                result["event_title"] = meet_invite.group(2).strip()
            return result
        
        # Image commands
        if re.search(r"\b(show|view|display)\s+(all\s+)?images?\b", low):
            return {"action": "show_images"}
        
        image_show = re.search(r"\b(show|view|display)\s+image\s+(.+)", low)
        if image_show:
            return {"action": "show_image", "file_name": image_show.group(2).strip()}
        
        folder_view = re.search(r"\b(view|open|show)\s+folder\s+(.+)", low)
        if folder_view:
            return {"action": "view_folder", "folder_name": folder_view.group(2).strip()}
        
        # Summary drafting
        summary_draft = re.search(r"(draft|create|make)\s+(a\s+)?summary\s+(of\s+)?(.+?)(?:\s+to\s+([^\s]+@[^\s]+))?$", low)
        if summary_draft:
            result = {"action": "draft_summary", "file_name": summary_draft.group(4).strip()}
            if len(summary_draft.groups()) > 4 and summary_draft.group(5):
                result["email"] = summary_draft.group(5)
            return result
        
        # Draft commands
        if re.search(r"\b(show|display|view)\b.*\bdraft\b", low):
            return {"action": "show_draft"}
        if re.search(r"\b(clear|delete|discard|erase)\b.*\bdraft\b", low):
            return {"action": "clear_draft"}
        
        draft_patterns = [
            r"^draft\s+(.+)$",
            r"^compose\s+(.+)$",
            r"^write\s+(.+)$",
        ]
        for pattern in draft_patterns:
            match = re.match(pattern, orig, re.IGNORECASE)
            if match:
                context = match.group(1).strip()
                if len(context.split()) <= 2:
                    return {"action": "draft_email", "text": ""}
                return {"action": "draft_email", "text": context}
        
        # File commands - FIXED search patterns
        if re.search(r"\b(list|show).*files?\b", low):
            return {"action": "list_files"}
        
        # Search patterns - handle "search for X" and "search X"
        search_patterns = [
            r"\bsearch\s+for\s+(.+)",
            r"\bfind\s+for\s+(.+)",
            r"\bsearch\s+(.+)",
            r"\bfind\s+(.+)",
            r"\blook\s+up\s+(.+)"
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, low)
            if match:
                keyword = match.group(1).strip().strip('"\'').strip()
                if keyword:
                    return {"action": "search_files", "keyword": keyword}
        
        summary_match = re.search(r"(summari[sz]e|summary)\s+(?:file\s+)?(.+)", low)
        if summary_match:
            return {"action": "summarize_file", "file_name": summary_match.group(2).strip()}
        
        send_draft = re.search(r"(send|email|mail)\s+(?:the\s+)?draft\s+to\s+(.+)", low)
        if send_draft:
            recipients = self._parse_recipients(send_draft.group(2))
            return {
                "action": "send_draft",
                "email": recipients if recipients else [send_draft.group(2).strip()]
            }
        
        return {"action": "unknown"}
    
    def _parse_recipients(self, text):
        """Extract email addresses from text."""
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        return [e.strip().strip(",;") for e in emails if e.strip()]