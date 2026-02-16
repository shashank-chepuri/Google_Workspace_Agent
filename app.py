# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import os
import secrets
import traceback
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests
import json
import io
from flask_socketio import SocketIO, emit
import base64
from datetime import datetime, timedelta
from bson import ObjectId
from bson.json_util import dumps
import re

from services.google_service import init_google_services
from services.cohere_service import init_cohere
from handlers.command_handler import CommandHandler
from handlers.task_handler import TaskHandler
from handlers.note_handler import NoteHandler
from handlers.calendar_handler import CalendarHandler
from handlers.meet_handler import MeetHandler
from handlers.file_handler import FileHandler
from handlers.draft_handler import DraftHandler
from utils.helpers import load_json_file, save_json_file

# MongoDB imports
from flask_pymongo import PyMongo

# Model imports
from models.friend_model import FriendModel
from models.history_model import HistoryModel

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['DEBUG'] = True
app.config['SESSION_TYPE'] = 'filesystem'

# ===== SESSION CONFIGURATION =====
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
# =================================

# ===== MONGODB CONFIGURATION =====
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/workspace_agent")
mongo = PyMongo(app)

# Initialize collections and models
friends_collection = None
history_collection = None
friend_model = None
history_model = None

try:
    # Test the connection
    mongo.db.command('ping')
    
    # Initialize friends collection
    friends_collection = mongo.db.friends
    try:
        friends_collection.create_index([("user_id", 1), ("name", 1)], unique=True)
        friends_collection.create_index([("user_id", 1), ("email", 1)])
        print("✅ Friends collection indexes created")
    except Exception as e:
        print(f"⚠️ Friends index creation warning: {e}")
    
    # Initialize history collection
    history_collection = mongo.db.history
    try:
        history_collection.create_index([("user_id", 1), ("timestamp", -1)])
        history_collection.create_index([("user_id", 1), ("action", 1)])
        print("✅ History collection indexes created")
    except Exception as e:
        print(f"⚠️ History index creation warning: {e}")
    
    # Initialize models
    friend_model = FriendModel(mongo.db)
    history_model = HistoryModel(mongo.db)
    
    print("✅ MongoDB connected successfully")
    print("✅ Models initialized successfully")
    
except Exception as e:
    print(f"⚠️ MongoDB connection error: {e}")
    friends_collection = None
    history_collection = None
    friend_model = None
    history_model = None
# =================================

# Initialize SocketIO for voice - using threading mode for Render compatibility
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Google OAuth Configuration - COMPREHENSIVE SCOPES INCLUDING ALL NEEDED
SCOPES = [
    # Drive scopes
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    
    # Gmail scopes - INCLUDING the ones causing the error
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://mail.google.com/",  # Added to match the error
    "https://www.googleapis.com/auth/gmail.readonly",  # Added to match the error
    
    # Tasks scopes
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/tasks.readonly",
    
    # Calendar scopes
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.events.owned",
    
    # User info scopes
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

# REMOVED: CLIENT_SECRETS_FILE = "credentials.json"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only

# Initialize services (will be set after login)
co = init_cohere()
google_services = {'initialized': False}
command_handler = CommandHandler(co)
task_handler = TaskHandler()
note_handler = NoteHandler()
calendar_handler = None
meet_handler = None
file_handler = None
draft_handler = DraftHandler()

# ===== CLEAN UP TOKEN ON STARTUP =====
# Clean up token.json on startup to force fresh authentication
if os.path.exists('token.json'):
    try:
        os.remove('token.json')
        print("🧹 Removed old token.json to force fresh authentication")
    except Exception as e:
        print(f"⚠️ Could not remove token.json: {e}")
# =====================================

# ===== FRIEND RESOLVER HELPER FUNCTION =====
def resolve_friend_names(command, user_id, friend_model):
    """Replace friend names in command with their email addresses."""
    if user_id is None or friend_model is None:
        return command
    
    words = command.split()
    resolved_words = []
    
    common_words = {
        'to', 'with', 'for', 'from', 'the', 'a', 'an', 'and', 'or', 'but', 
        'in', 'on', 'at', 'by', 'about', 'file', 'send', 'email', 'draft',
        'schedule', 'meet', 'create', 'list', 'show', 'view', 'delete',
        'task', 'note', 'event', 'image', 'folder', 'summary', 'my', 'all',
        'upcoming', 'today', 'tomorrow', 'next', 'this', 'that', 'please',
        'can', 'you', 'i', 'me', 'help', 'exit', 'quit', 'bye', 'close',
        'what', 'where', 'when', 'who', 'how', 'why', 'is', 'are', 'was',
        'were', 'will', 'would', 'could', 'should', 'have', 'has', 'had',
        'hai', 'hello', 'hi', 'hey', 'mail', 'email', 'search', 'find', 'for'
    }
    
    try:
        for word in words:
            if '@' in word or word.lower() in common_words or word.isdigit():
                resolved_words.append(word)
                continue
            
            if re.match(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)?', word.lower()):
                resolved_words.append(word)
                continue
            
            if len(word) > 1:
                email = friend_model.resolve_name_to_email(user_id, word)
                if email:
                    resolved_words.append(email)
                    continue
            
            resolved_words.append(word)
    except Exception as e:
        print(f"⚠️ Error in friend resolver: {e}")
        return command
    
    return ' '.join(resolved_words)

def parse_json(data):
    """Convert MongoDB ObjectId to string for JSON serialization."""
    return json.loads(dumps(data))

# ===== UPDATED: get_flow function using environment variables =====
def get_flow():
    """Create and return a Google OAuth flow instance using environment variables."""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    project_id = os.getenv('GOOGLE_PROJECT_ID', '')
    
    if not client_id or not client_secret:
        print("❌ GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set in environment")
        return None
    
    # Create flow from client config (not from file)
    client_config = {
        "web": {
            "client_id": client_id,
            "project_id": project_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [url_for('oauth2callback', _external=True)],
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES
    )
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    return flow
# ==================================================================

@app.route('/')
def index():
    """Main page - shows login if not authenticated, otherwise shows the app."""
    session.permanent = True
    
    if 'credentials' not in session:
        return render_template('login.html')
    return render_template('index.html', user=session.get('user', {}))

@app.route('/history')
def history_page():
    """Show user's command history."""
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('history.html', user=session.get('user', {}))

@app.route('/login')
def login():
    """Initiate Google OAuth login with forced consent for scope changes."""
    flow = get_flow()
    if flow is None:
        return jsonify({'error': 'OAuth configuration missing'}), 500
        
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Always force consent to handle scope changes
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Handle the OAuth callback."""
    try:
        flow = get_flow()
        if flow is None:
            return jsonify({'error': 'OAuth configuration missing'}), 500
            
        flow.fetch_token(authorization_response=request.url)
        
        if not session['state'] == request.args['state']:
            return jsonify({'error': 'Invalid state parameter'}), 401
        
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        session.permanent = True
        
        # Save credentials to token.json for backward compatibility
        creds = Credentials.from_authorized_user_info(session['credentials'])
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
        
        # Get user info from Google's UserInfo API
        headers = {'Authorization': f'Bearer {credentials.token}'}
        response = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers)
        
        if response.status_code == 200:
            user_info = response.json()
            session['user'] = {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture')
            }
            print(f"✅ User authenticated: {user_info.get('email')}")
        else:
            print(f"⚠️ Could not get user info: {response.status_code}")
            session['user'] = {
                'email': 'unknown@email.com',
                'name': 'Unknown User',
                'picture': None
            }
        
        # Verify all scopes were granted
        granted_scopes = credentials.scopes
        expected_scopes = SCOPES.copy()
        missing_scopes = [s for s in expected_scopes if s not in granted_scopes]
        
        if missing_scopes:
            print(f"⚠️ Warning: Some scopes were not granted: {missing_scopes}")
            session['missing_scopes'] = missing_scopes
        else:
            print("✅ All required scopes granted!")
        
        # Initialize Google services
        global google_services, calendar_handler, meet_handler, file_handler
        google_services = init_google_services()
        
        if google_services['initialized']:
            calendar_handler = CalendarHandler(google_services.get('calendar'))
            meet_handler = MeetHandler(google_services.get('calendar'))
            file_handler = FileHandler(google_services)
            print("✅ Google services initialized successfully")
        else:
            print("⚠️ Google services initialization failed")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@app.route('/logout')
def logout():
    """Log out the user."""
    session.clear()
    if os.path.exists('token.json'):
        os.remove('token.json')
        print("✅ Token file removed")
    return redirect(url_for('index'))

@app.route('/api/reauthenticate')
def reauthenticate():
    """Force re-authentication when scopes have changed."""
    if 'user' in session:
        # Clear credentials to force re-auth
        session.pop('credentials', None)
        if os.path.exists('token.json'):
            os.remove('token.json')
    
    # Redirect to login with force consent
    flow = get_flow()
    if flow is None:
        return jsonify({'error': 'OAuth configuration missing'}), 500
        
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent select_account'  # Force consent and account selection
    )
    session['state'] = state
    return redirect(authorization_url)

# ========== FRIENDS API ENDPOINTS ==========
@app.route('/api/friends', methods=['GET'])
def get_friends():
    """Get all friends for current user."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if friend_model is None:
        return jsonify({'success': False, 'message': 'Database not available'}), 503
    
    user_id = session['user']['email']
    friends = friend_model.get_all(user_id)
    return jsonify({'success': True, 'data': friends})

@app.route('/api/friends', methods=['POST'])
def add_friend():
    """Add a new friend."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if friend_model is None:
        return jsonify({'success': False, 'message': 'Database not available'}), 503
    
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    
    if not name or not email:
        return jsonify({'success': False, 'message': 'Name and email are required'}), 400
    
    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'message': 'Please enter a valid email address'}), 400
    
    user_id = session['user']['email']
    result = friend_model.create(user_id, name, email)
    
    if result['success']:
        return jsonify({
            'success': True,
            'data': result['data'],
            'message': f'Friend {name} added successfully'
        })
    else:
        return jsonify({'success': False, 'message': result['message']}), 400

@app.route('/api/friends/<friend_id>', methods=['PUT'])
def update_friend(friend_id):
    """Update a friend."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if friend_model is None:
        return jsonify({'success': False, 'message': 'Database not available'}), 503
    
    data = request.json
    user_id = session['user']['email']
    
    result = friend_model.update(
        friend_id, 
        user_id,
        name=data.get('name'),
        email=data.get('email')
    )
    
    if result['success']:
        return jsonify({
            'success': True,
            'data': result['data'],
            'message': 'Friend updated successfully'
        })
    else:
        return jsonify({'success': False, 'message': result['message']}), 404

@app.route('/api/friends/<friend_id>', methods=['DELETE'])
def delete_friend(friend_id):
    """Delete a friend."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if friend_model is None:
        return jsonify({'success': False, 'message': 'Database not available'}), 503
    
    user_id = session['user']['email']
    result = friend_model.delete(friend_id, user_id)
    
    if result['success']:
        return jsonify({'success': True, 'message': 'Friend deleted successfully'})
    else:
        return jsonify({'success': False, 'message': 'Friend not found'}), 404

@app.route('/api/friends/search', methods=['GET'])
def search_friends():
    """Search friends by name or email."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if friend_model is None:
        return jsonify({'success': False, 'message': 'Database not available'}), 503
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': True, 'data': []})
    
    user_id = session['user']['email']
    results = friend_model.search(user_id, query)
    
    return jsonify({'success': True, 'data': results})

# ========== HISTORY API ENDPOINTS ==========
@app.route('/api/history', methods=['GET'])
def get_history():
    """Get user's command history."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if history_model is None:
        return jsonify({'success': False, 'message': 'History service unavailable'}), 503
    
    user_id = session['user']['email']
    limit = int(request.args.get('limit', 50))
    skip = int(request.args.get('skip', 0))
    
    history = history_model.get_user_history(user_id, limit, skip)
    return jsonify({'success': True, 'data': history})

@app.route('/api/history/search', methods=['GET'])
def search_history():
    """Search user's command history."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if history_model is None:
        return jsonify({'success': False, 'message': 'History service unavailable'}), 503
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': True, 'data': []})
    
    user_id = session['user']['email']
    history = history_model.search_history(user_id, query)
    return jsonify({'success': True, 'data': history})

@app.route('/api/history/stats', methods=['GET'])
def get_history_stats():
    """Get history statistics for user."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if history_model is None:
        return jsonify({'success': False, 'message': 'History service unavailable'}), 503
    
    user_id = session['user']['email']
    stats = history_model.get_stats(user_id)
    return jsonify({'success': True, 'data': stats})

@app.route('/api/history/clear', methods=['DELETE'])
def clear_history():
    """Clear user's command history."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if history_model is None:
        return jsonify({'success': False, 'message': 'History service unavailable'}), 503
    
    user_id = session['user']['email']
    deleted_count = history_model.clear_history(user_id)
    
    return jsonify({
        'success': True,
        'message': f'Cleared {deleted_count} history entries'
    })

@app.route('/api/mongodb-status')
def mongodb_status():
    """Check MongoDB connection status."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'friends_connected': friend_model is not None,
        'history_connected': history_model is not None,
        'database': app.config["MONGO_URI"].split('/')[-1].split('?')[0]
    })

# ========== VOICE ENDPOINTS ==========
@socketio.on('connect')
def handle_connect():
    print('🎤 Voice client connected')
    emit('connected', {'message': 'Voice server connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('🎤 Voice client disconnected')

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        emit('transcription', {'text': 'Audio received, processing...'})
        emit('transcription', {
            'text': 'Voice command received. Processing...',
            'confidence': 0.9
        })
    except Exception as e:
        print(f"🎤 Error processing audio: {e}")
        emit('error', {'message': str(e)})

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        return send_file(
            audio_buffer,
            mimetype='audio/mp3',
            as_attachment=False,
            download_name='response.mp3'
        )
        
    except ImportError:
        return jsonify({'error': 'Text-to-speech service unavailable'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== COMMAND HANDLING ==========
@app.route('/api/command', methods=['POST'])
def handle_command():
    data = request.json
    command = data.get('command', '')
    
    session.permanent = True
    
    if 'credentials' not in session:
        return jsonify({
            'success': False,
            'message': 'Please login first',
            'action': 'login_required'
        })
    
    if not google_services['initialized']:
        return jsonify({
            'success': False,
            'message': 'Google services not initialized. Please try logging in again.',
            'action': 'error'
        })
    
    try:
        user_id = session['user']['email']
        user_name = session['user'].get('name', 'Unknown')
        
        # Resolve friend names in the command
        if friend_model is not None:
            resolved_command = resolve_friend_names(command, user_id, friend_model)
            if resolved_command != command:
                print(f"📇 Resolved friend names: '{command}' -> '{resolved_command}'")
        else:
            resolved_command = command
        
        # Parse the command
        parsed = command_handler.parse_command(resolved_command)
        action = parsed.get('action', 'unknown')
        
        response_data = None
        
        # Route to appropriate handler with error handling for scope issues
        try:
            if action == 'exit':
                response_data = {'success': True, 'action': 'exit', 'message': 'Goodbye!'}
            
            elif action == 'help':
                response_data = {
                    'success': True, 
                    'action': 'help', 
                    'message': get_help_text()
                }
            
            elif action in ['list_tasks', 'add_task', 'complete_task', 'delete_task']:
                response_data = task_handler.handle(action, parsed, command)
            
            elif action in ['list_notes', 'create_note', 'get_note', 'delete_note', 'search_notes']:
                response_data = note_handler.handle(action, parsed, command)
            
            elif action in ['list_events', 'create_event', 'get_event', 'delete_event', 'list_today', 'list_date']:
                if calendar_handler:
                    response_data = calendar_handler.handle(action, parsed, command)
                else:
                    response_data = {'success': False, 'message': 'Calendar service not available'}
            
            elif action in ['schedule_meet', 'send_meet_invite']:
                if meet_handler:
                    response_data = meet_handler.handle(action, parsed, command, draft_handler, google_services.get('gmail'))
                else:
                    response_data = {'success': False, 'message': 'Meet service not available'}
            
            # File operations - with special handling for search
            elif action in ['list_files', 'search_files', 'show_images', 'show_image', 'view_folder']:
                if file_handler:
                    # For search_files, ensure we have a proper parsed dictionary
                    if action == 'search_files':
                        # Make sure parsed has the keyword
                        if isinstance(parsed, dict) and 'keyword' not in parsed:
                            # Try to extract keyword from command
                            words = command.split()
                            if len(words) > 1:
                                # Remove the first word (search/find)
                                keyword = ' '.join(words[1:]).strip()
                                parsed['keyword'] = keyword
                            else:
                                response_data = {'success': False, 'message': 'Please provide a search keyword'}
                                # Log to history
                                if history_model is not None:
                                    history_model.log(
                                        user_id=user_id,
                                        user_name=user_name,
                                        command=command,
                                        response='Please provide a search keyword',
                                        action='search_files',
                                        success=False
                                    )
                                return jsonify(response_data)
                    
                    response_data = file_handler.handle(action, parsed, command)
                else:
                    response_data = {'success': False, 'message': 'File service not available'}
            
            elif action in ['draft_email', 'draft_summary', 'show_draft', 'clear_draft', 'refine_draft', 'send_draft']:
                response_data = draft_handler.handle(action, parsed, command, co, google_services.get('gmail'))
            
            elif action == 'summarize_file':
                if file_handler:
                    response_data = file_handler.handle_summarize(parsed, command)
                else:
                    response_data = {'success': False, 'message': 'File service not available'}
            
            else:
                response_data = {
                    'success': False,
                    'message': 'Command not recognized. Try "help"'
                }
        
        except Exception as e:
            # Check if it's a scope-related error
            error_str = str(e)
            if 'Scope has changed' in error_str or 'unauthorized_client' in error_str or 'access_denied' in error_str:
                response_data = {
                    'success': False,
                    'message': 'Your permissions have changed. Please re-authenticate.',
                    'action': 'reauthenticate',
                    'requires_reauth': True
                }
            else:
                # Re-raise other errors to be caught by outer try-except
                raise e
        
        # Log to history
        if history_model is not None:
            history_model.log(
                user_id=user_id,
                user_name=user_name,
                command=command,
                response=response_data.get('message', ''),
                action=action,
                success=response_data.get('success', False),
                error_msg=None if response_data.get('success', False) else response_data.get('message')
            )
        
        return jsonify(response_data)
            
    except Exception as e:
        traceback.print_exc()
        
        # Check if it's a scope-related error
        error_str = str(e)
        if 'Scope has changed' in error_str:
            error_response = {
                'success': False,
                'message': 'Your permissions have changed. Please re-authenticate.',
                'action': 'reauthenticate',
                'requires_reauth': True
            }
        else:
            error_response = {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
        
        if 'user' in session and history_model is not None:
            history_model.log(
                user_id=session['user']['email'],
                user_name=session['user'].get('name', 'Unknown'),
                command=command,
                response=str(e),
                action='error',
                success=False,
                error_msg=str(e)
            )
        
        return jsonify(error_response)

# ========== USER INFO ENDPOINTS ==========
@app.route('/api/user')
def get_user():
    session.permanent = True
    if 'user' in session:
        return jsonify({'authenticated': True, 'user': session['user']})
    return jsonify({'authenticated': False})

@app.route('/api/check-auth')
def check_auth():
    session.permanent = True
    return jsonify({'authenticated': 'credentials' in session})

@app.route('/api/scopes')
def get_scopes():
    if 'credentials' not in session:
        return jsonify({'authenticated': False})
    
    creds = Credentials.from_authorized_user_info(session['credentials'])
    granted = creds.scopes
    expected = SCOPES
    missing = [s for s in expected if s not in granted]
    
    return jsonify({
        'authenticated': True,
        'granted_scopes': granted,
        'expected_scopes': expected,
        'missing_scopes': missing,
        'all_granted': len(missing) == 0
    })

@app.route('/api/debug-token')
def debug_token():
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'})
    
    try:
        creds = Credentials.from_authorized_user_info(session['credentials'])
        headers = {'Authorization': f'Bearer {creds.token}'}
        response = requests.get('https://www.googleapis.com/oauth2/v1/tokeninfo', headers=headers)
        
        token_info = response.json() if response.status_code == 200 else {'error': 'Token invalid'}
        
        return jsonify({
            'has_token': True,
            'token_valid': response.status_code == 200,
            'token_info': token_info,
            'scopes': creds.scopes,
            'has_refresh_token': bool(creds.refresh_token)
        })
    except Exception as e:
        return jsonify({'error': str(e)})

def get_help_text():
    """Return properly formatted help text."""
    return """
📋 <strong>TASKS</strong><br>
• <code>list tasks</code> - Show all tasks<br>
• <code>add task: [description] due: [date]</code> - Create a new task<br>
• <code>complete task [id]</code> - Mark task as complete<br>
• <code>delete task [id]</code> - Remove a task<br>
<br>
📝 <strong>NOTES (KEEP)</strong><br>
• <code>list notes</code> - Show all notes<br>
• <code>create note: [title] - [content]</code> - Create a new note<br>
• <code>get note [id]</code> - View a specific note<br>
• <code>delete note [id]</code> - Delete a note<br>
• <code>search notes: [keyword]</code> - Find notes by keyword<br>
<br>
📅 <strong>CALENDAR</strong><br>
• <code>list events</code> - Show upcoming events<br>
• <code>list today</code> - Show today's events<br>
• <code>create event: [title] on [date] at [time]</code> - Create an event<br>
• <code>get event [id]</code> - View event details<br>
• <code>delete event [id]</code> - Delete an event<br>
<br>
🎥 <strong>MEET</strong><br>
• <code>schedule meet: [title] on [date] at [time] with [emails]</code> - Create Google Meet<br>
• <code>send meet invite to [email] for [event]</code> - Send meeting invitation<br>
<br>
🖼️ <strong>IMAGES</strong><br>
• <code>show images</code> - Display all images<br>
• <code>show image [filename]</code> - View a specific image<br>
• <code>view folder [folder name]</code> - Browse folder contents<br>
<br>
📁 <strong>FILES</strong><br>
• <code>list all files</code> - Show all Drive files<br>
• <code>search [keyword]</code> - Search for files<br>
• <code>summarize [file name]</code> - Generate a summary<br>
<br>
📧 <strong>DRAFTS</strong><br>
• <code>draft [your request]</code> - Create email draft<br>
• <code>draft summary of [file] to [email]</code> - Create summary draft<br>
• <code>show draft</code> - View current draft<br>
• <code>clear draft</code> - Discard current draft<br>
• <code>send draft to [email]</code> - Send the draft<br>
<br>
👥 <strong>FRIENDS</strong><br>
• Add friends with names and emails<br>
• Use friend names in commands like "send email to Venkat"<br>
<br>
📊 <strong>HISTORY</strong><br>
• View your command history and stats<br>
• Search past commands<br>
• Track your usage patterns<br>
<br>
❓ <strong>OTHER</strong><br>
• <code>help</code> - Show this help message<br>
• <code>exit</code> - Close the application<br>
"""

if __name__ == '__main__':
    # Get port from environment variable (Render sets this automatically)
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "=" * 60)
    print("🚀 Starting Workspace Agent on Render")
    print("=" * 60)
    print(f"📍 Port: {port}")
    print(f"📍 MongoDB: {'✅ Connected' if friend_model is not None else '❌ Disconnected'}")
    print(f"📍 SocketIO Mode: threading")
    print(f"📍 OAuth Mode: Environment Variables")
    print(f"📍 Scopes: {len(SCOPES)} scopes configured")
    print("=" * 60)
    
    # IMPORTANT: debug must be False in production
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
