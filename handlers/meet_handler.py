# handlers/meet_handler.py
from datetime import datetime, timedelta
import pytz
import uuid
from utils.helpers import parse_date, parse_time

class MeetHandler:
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service
    
    def handle(self, action, parsed, command, draft_handler=None, gmail_service=None):
        """Route Meet actions to appropriate methods."""
        if action == 'schedule_meet':
            return self.schedule_meet(parsed, draft_handler, gmail_service)
        elif action == 'send_meet_invite':
            return self.send_meet_invite(parsed, draft_handler, gmail_service)
        else:
            return {'success': False, 'message': 'Unknown Meet action'}
    
    def schedule_meet(self, parsed, draft_handler=None, gmail_service=None):
        """Schedule a Google Meet and optionally send invites."""
        try:
            title = parsed.get('title', 'Meeting')
            date_str = parsed.get('date', '')
            time_str = parsed.get('time', '09:00')
            attendees = parsed.get('attendees', [])
            
            if not date_str:
                return {'success': False, 'message': 'Meeting date is required'}
            
            # Parse date and time
            meeting_date = parse_date(date_str)
            meeting_time = parse_time(time_str) if time_str else parse_time('09:00')
            
            # Get local timezone
            try:
                import tzlocal
                local_tz = str(tzlocal.get_localzone())
            except:
                local_tz = 'UTC'
            
            # Create datetime with timezone
            start_datetime = datetime.combine(meeting_date, meeting_time)
            start_datetime = pytz.timezone(local_tz).localize(start_datetime)
            end_datetime = start_datetime + timedelta(hours=1)
            
            # Create event with Google Meet - this is the key part!
            event = {
                'summary': title,
                'description': f'Meeting scheduled by Workspace Agent',
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': local_tz,
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': local_tz,
                },
                # This is what creates the Google Meet link
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(uuid.uuid4()),  # Unique ID for this request
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'  # This tells Google to create a Meet
                        }
                    }
                },
                'attendees': [{'email': email} for email in attendees] if attendees else [],
                'guestsCanModify': False,
                'reminders': {
                    'useDefault': True
                }
            }
            
            # Create the calendar event with conference data
            # IMPORTANT: conferenceDataVersion=1 is required to create Meet links
            created_event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,  # This parameter is crucial!
                sendUpdates='all' if attendees else 'none'  # Send emails to attendees
            ).execute()
            
            # Extract the Meet link from the response
            meet_link = None
            if 'conferenceData' in created_event:
                entry_points = created_event['conferenceData'].get('entryPoints', [])
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        break
            
            if not meet_link:
                # Fallback: construct from conference ID
                conference_id = created_event['conferenceData'].get('conferenceId')
                if conference_id:
                    meet_link = f"https://meet.google.com/{conference_id}"
            
            result = {
                'success': True,
                'action': 'schedule_meet',
                'data': {
                    'id': created_event['id'],
                    'title': title,
                    'meet_link': meet_link,
                    'date': date_str,
                    'time': time_str,
                    'event_link': created_event.get('htmlLink'),
                    'conference_id': created_event.get('conferenceData', {}).get('conferenceId')
                },
                'message': f'✅ Meeting scheduled: {title}'
            }
            
            # If attendees provided, add to message
            if attendees:
                result['message'] += f'\n📧 Invitations sent to: {", ".join(attendees)}'
                if meet_link:
                    result['message'] += f'\n🔗 Meet link: {meet_link}'
            
            return result
            
        except Exception as e:
            return {'success': False, 'message': f'Error scheduling meeting: {str(e)}'}
    
    def send_meet_invite(self, parsed, draft_handler=None, gmail_service=None):
        """Send a Meet invitation email."""
        try:
            email = parsed.get('email')
            event_title = parsed.get('event_title', '')
            
            if not email:
                return {'success': False, 'message': 'Email address is required'}
            
            # Find the event by title or get the most recent
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                maxResults=20,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            target_event = None
            
            if event_title:
                # Find by title (case-insensitive)
                for event in events:
                    if event_title.lower() in event.get('summary', '').lower():
                        target_event = event
                        break
            
            if not target_event and events:
                # Use the most recent future event
                now = datetime.utcnow().isoformat() + 'Z'
                future_events = [e for e in events if e.get('start', {}).get('dateTime', '') > now]
                if future_events:
                    target_event = future_events[0]
            
            if not target_event:
                return {'success': False, 'message': 'No suitable event found for invitation'}
            
            # Get Meet link from the event
            meet_link = None
            if 'conferenceData' in target_event:
                entry_points = target_event['conferenceData'].get('entryPoints', [])
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        break
            
            if not meet_link:
                return {'success': False, 'message': 'Event does not have a Meet link'}
            
            # Parse start time
            start = target_event['start'].get('dateTime', target_event['start'].get('date'))
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = start_dt.strftime('%A, %B %d at %I:%M %p')
            except:
                formatted_time = start
            
            # Create email draft
            subject = f"Invitation: {target_event['summary']}"
            
            body = f"""Hello,

You're invited to join a Google Meet meeting:

**{target_event['summary']}**

📅 **When:** {formatted_time}
🔗 **Meet Link:** {meet_link}

Click the link above to join the meeting. You can also open Google Calendar to add this event to your calendar.

---
This invitation was sent by Workspace Agent.
"""
            
            if draft_handler:
                draft_handler.draft = {
                    'subject': subject,
                    'body': body,
                    'recipients': [email],
                    'type': 'email'
                }
                draft_handler.save_draft()
                
                return {
                    'success': True,
                    'action': 'send_meet_invite',
                    'message': f'📧 Draft invitation created for {email}',
                    'data': {
                        'subject': subject,
                        'body': body,
                        'meet_link': meet_link,
                        'event': target_event['summary']
                    }
                }
            else:
                return {
                    'success': True,
                    'action': 'send_meet_invite',
                    'data': {'meet_link': meet_link},
                    'message': f'✅ Meet link: {meet_link}'
                }
            
        except Exception as e:
            return {'success': False, 'message': f'Error sending invite: {str(e)}'}
    
    def _create_meet_invite_draft(self, title, meet_link, date, time, attendees):
        """Create a draft email for Meet invitation."""
        if not meet_link:
            return None
        
        subject = f"Invitation: {title}"
        body = f"""Hello,

You're invited to join a Google Meet meeting:

**{title}**

📅 Date: {date}
⏰ Time: {time}
🔗 Meet Link: {meet_link}

Click the link above to join the meeting.

---
This invitation was sent by Workspace Agent.
"""
        
        return {
            'subject': subject,
            'body': body,
            'recipients': attendees
        }