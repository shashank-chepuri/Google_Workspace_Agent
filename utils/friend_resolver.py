# utils/friend_resolver.py
import re

def resolve_friend_names(command, user_id, friends_collection):
    """
    Replace friend names in command with their email addresses.
    
    Args:
        command: The original command string
        user_id: Current user's email
        friends_collection: MongoDB friends collection
    
    Returns:
        Command with friend names replaced by emails
    """
    # Fix: Check if collection is None, not just if it exists
    if user_id is None or friends_collection is None:
        return command
    
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
        'hai', 'hello', 'hi', 'hey', 'mail', 'email'  # Added more words
    }
    
    try:
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
            # Only check words that are likely names (reasonable length)
            if len(word) > 1:  # Names are usually longer than 1 character
                try:
                    # Case-insensitive search in MongoDB
                    import re as regex
                    pattern = regex.compile(f'^{re.escape(word)}$', regex.IGNORECASE)
                    friend = friends_collection.find_one({
                        'user_id': user_id,
                        'name': pattern
                    })
                    
                    if friend is not None:
                        # Replace with email
                        resolved_words.append(friend['email'])
                        continue
                except Exception as e:
                    print(f"⚠️ Friend resolution error for '{word}': {e}")
                    resolved_words.append(word)
                    continue
            
            # If no match found, keep original word
            resolved_words.append(word)
    except Exception as e:
        print(f"⚠️ Error in friend resolver: {e}")
        return command  # Return original command on error
    
    return ' '.join(resolved_words)