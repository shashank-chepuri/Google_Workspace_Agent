# services/google_service.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import traceback

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar"
]

def init_google_services():
    """Initialize all Google API services."""
    services = {
        'drive': None,
        'sheets': None,
        'docs': None,
        'slides': None,
        'gmail': None,
        'tasks': None,
        'calendar': None,
        'initialized': False
    }
    
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        services['drive'] = build("drive", "v3", credentials=creds)
        services['sheets'] = build("sheets", "v4", credentials=creds)
        services['docs'] = build("docs", "v1", credentials=creds)
        services['slides'] = build("slides", "v1", credentials=creds)
        services['gmail'] = build("gmail", "v1", credentials=creds)
        services['tasks'] = build("tasks", "v1", credentials=creds)
        services['calendar'] = build("calendar", "v3", credentials=creds)
        
        services['initialized'] = True
        print("✅ Google services initialized successfully")
        
    except FileNotFoundError:
        print("❌ token.json not found. Please run Google API auth flow first.")
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        traceback.print_exc()
    
    return services

def get_service(services, name):
    """Get a specific service by name."""
    return services.get(name)