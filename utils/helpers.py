# utils/helpers.py
import json
import os
import uuid
from datetime import datetime, timedelta
import re

def load_json_file(filepath, default=None):
    """Load data from a JSON file."""
    if default is None:
        default = []
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json_file(filepath, data):
    """Save data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def generate_id():
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]

def parse_date(date_str):
    """Parse date string into datetime.date object."""
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    today = datetime.now().date()
    
    # Handle relative dates
    if date_str == 'today':
        return today
    elif date_str == 'tomorrow':
        return today + timedelta(days=1)
    elif date_str == 'day after tomorrow':
        return today + timedelta(days=2)
    elif date_str == 'next week':
        return today + timedelta(weeks=1)
    elif date_str == 'next month':
        return today + timedelta(days=30)
    
    # Handle "next Monday", "next Friday", etc.
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    for day_name, day_num in day_map.items():
        if f'next {day_name}' in date_str:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead + 7)
    
    # Try to parse specific date formats
    date_formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%b %d, %Y',
        '%B %d, %Y',
        '%d %b %Y',
        '%d %B %Y',
        '%Y/%m/%d',
        '%m-%d-%Y',
        '%d-%m-%Y',
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    # Try to extract date from natural language
    patterns = [
        r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})',
    ]
    
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    for pattern in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            groups = match.groups()
            if groups[0].isalpha():
                month = month_map[groups[0].lower()]
                day = int(groups[1])
            else:
                day = int(groups[0])
                month = month_map[groups[1].lower()]
            
            year = today.year
            if datetime(year, month, day).date() < today:
                year += 1
            return datetime(year, month, day).date()
    
    print(f"⚠️ Could not parse date: {date_str}")
    return today

def parse_time(time_str):
    """Parse time string into datetime.time object."""
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()
    
    # Handle formats like "10:00 p.m.", "10pm", "10:00pm", "10:00 pm", "22:00"
    try:
        # Clean up the string - remove dots and extra spaces
        time_str = time_str.replace('.', '').strip()
        
        # Pattern for 12-hour format with am/pm
        # This handles: "10pm", "10:00pm", "10:00 pm", "10 p.m.", "10:00 p.m."
        ampm_match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
        if ampm_match:
            hour = int(ampm_match.group(1))
            minute = int(ampm_match.group(2)) if ampm_match.group(2) else 0
            ampm = ampm_match.group(3).lower()
            
            # Validate hour
            if hour < 1 or hour > 12:
                raise ValueError(f"Invalid hour: {hour}")
            
            # Convert to 24-hour format
            if ampm == 'pm':
                if hour != 12:
                    hour += 12
            else:  # am
                if hour == 12:
                    hour = 0
            
            # Validate minute
            if minute < 0 or minute > 59:
                raise ValueError(f"Invalid minute: {minute}")
            
            return datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
        
        # Try 24-hour format (HH:MM)
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2:
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
        
        # Try just hour (e.g., "14" or "2")
        if time_str.isdigit():
            hour = int(time_str)
            if 1 <= hour <= 12 and 'pm' not in time_str and 'am' not in time_str:
                # Assume it's 24-hour format if >12, otherwise assume it's ambiguous and use 24-hour
                if hour <= 12:
                    # Could be 2am or 2pm - we'll assume it's the next occurrence
                    # For simplicity, treat as 24-hour format
                    pass
            if 0 <= hour <= 23:
                return datetime.strptime(f"{hour:02d}:00", "%H:%M").time()
        
    except Exception as e:
        print(f"⚠️ Time parsing error: {e}")
    
    # Default to 9 AM if parsing fails
    print(f"⚠️ Could not parse time: '{time_str}', using 09:00")
    return datetime.strptime("09:00", "%H:%M").time()

def format_datetime(dt):
    """Format datetime for display."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    
    now = datetime.now(dt.tzinfo if dt.tzinfo else None)
    
    if dt.date() == now.date():
        return f"Today at {dt.strftime('%I:%M %p')}"
    elif dt.date() == now.date() + timedelta(days=1):
        return f"Tomorrow at {dt.strftime('%I:%M %p')}"
    else:
        return dt.strftime('%b %d, %Y at %I:%M %p')

def is_image_file(mime_type, filename=None):
    """Check if file is an image."""
    image_types = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
        'image/bmp', 'image/webp', 'image/svg+xml', 'image/tiff'
    ]
    
    if mime_type and mime_type in image_types:
        return True
    
    if filename:
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff']
        return ext in image_extensions
    
    return False