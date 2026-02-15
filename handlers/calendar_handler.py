# handlers/calendar_handler.py
from datetime import datetime, timedelta
import pytz
from utils.helpers import parse_date, parse_time, format_datetime
import traceback

class CalendarHandler:
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service
        # Get local timezone
        self.timezone = self._get_local_timezone()
        print(f"📅 Calendar handler initialized with timezone: {self.timezone}")
    
    def _get_local_timezone(self):
        """Get local timezone string."""
        try:
            import tzlocal
            local_tz = tzlocal.get_localzone()
            return str(local_tz)
        except:
            try:
                import time
                is_dst = time.daylight and time.localtime().tm_isdst > 0
                offset = time.altzone if is_dst else time.timezone
                return f'Etc/GMT{int(-offset/3600):+d}'
            except:
                return 'UTC'
    
    def handle(self, action, parsed, command):
        """Route calendar actions to appropriate methods."""
        try:
            if action == 'list_events':
                return self.list_events()
            elif action == 'list_today':
                return self.list_today()
            elif action == 'list_date':
                return self.list_date(parsed)
            elif action == 'create_event':
                return self.create_event(parsed)
            elif action == 'get_event':
                return self.get_event(parsed)
            elif action == 'delete_event':
                return self.delete_event(parsed)
            elif action == 'delete_all_events':
                return self.delete_all_events(parsed)
            elif action == 'confirm_delete_all':
                return self.confirm_delete_all(parsed)
            else:
                return {'success': False, 'message': 'Unknown calendar action'}
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Calendar error: {str(e)}'}
    
    def list_events(self, max_results=20):
        """List upcoming events."""
        try:
            # Get current time in RFC3339 format
            now = datetime.utcnow().isoformat() + 'Z'
            # Get events for next 30 days
            later = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
            
            print(f"📅 Fetching events from {now} to {later}")
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=later,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return {
                    'success': True,
                    'action': 'list_events',
                    'data': [],
                    'message': 'No upcoming events found'
                }
            
            formatted_events = self._format_events(events)
            
            return {
                'success': True,
                'action': 'list_events',
                'data': formatted_events,
                'message': f'Found {len(formatted_events)} upcoming events'
            }
            
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Error listing events: {str(e)}'}
    
    def list_today(self):
        """List today's events."""
        try:
            # Get today's range in local timezone
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            
            start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
            end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=tz)
            
            # Convert to RFC3339 format
            time_min = start_of_day.isoformat()
            time_max = end_of_day.isoformat()
            
            print(f"📅 Fetching today's events: {time_min} to {time_max}")
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            formatted_events = self._format_events(events)
            
            return {
                'success': True,
                'action': 'list_today',
                'data': formatted_events,
                'message': f'Found {len(formatted_events)} events today'
            }
            
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Error listing today\'s events: {str(e)}'}
    
    def list_date(self, parsed):
        """List events for a specific date."""
        try:
            date_str = parsed.get('date', '')
            if not date_str:
                return {'success': False, 'message': 'Date is required'}
            
            # Parse the date
            event_date = parse_date(date_str)
            if not event_date:
                return {'success': False, 'message': f'Could not parse date: {date_str}'}
            
            # Create time range for the date in local timezone
            tz = pytz.timezone(self.timezone)
            start_of_day = datetime(event_date.year, event_date.month, event_date.day, 0, 0, 0, tzinfo=tz)
            end_of_day = datetime(event_date.year, event_date.month, event_date.day, 23, 59, 59, tzinfo=tz)
            
            time_min = start_of_day.isoformat()
            time_max = end_of_day.isoformat()
            
            print(f"📅 Fetching events for {event_date}: {time_min} to {time_max}")
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            formatted_events = self._format_events(events)
            
            date_display = event_date.strftime('%B %d, %Y')
            
            return {
                'success': True,
                'action': 'list_date',
                'data': formatted_events,
                'message': f'Found {len(formatted_events)} events on {date_display}'
            }
            
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Error listing events: {str(e)}'}
    
    def create_event(self, parsed):
        """Create a new calendar event."""
        try:
            # Extract event details
            title = parsed.get('title', 'Untitled Event')
            date_str = parsed.get('date', '')
            time_str = parsed.get('time', '')
            description = parsed.get('description', 'Created by Workspace Agent')
            
            if not title:
                return {'success': False, 'message': 'Event title is required'}
            
            if not date_str:
                return {'success': False, 'message': 'Event date is required'}
            
            print(f"📅 Creating event: {title} on {date_str} at {time_str}")
            
            # Parse date
            event_date = parse_date(date_str)
            if not event_date:
                return {'success': False, 'message': f'Could not parse date: {date_str}'}
            
            # Parse time if provided
            event_time = parse_time(time_str) if time_str else None
            
            # Create timezone-aware datetime
            tz = pytz.timezone(self.timezone)
            
            if event_time:
                # Event with specific time
                start_datetime = tz.localize(datetime.combine(event_date, event_time))
                end_datetime = start_datetime + timedelta(hours=1)
                
                event_body = {
                    'summary': title,
                    'description': description,
                    'start': {
                        'dateTime': start_datetime.isoformat(),
                        'timeZone': self.timezone,
                    },
                    'end': {
                        'dateTime': end_datetime.isoformat(),
                        'timeZone': self.timezone,
                    }
                }
                event_type = 'timed'
            else:
                # All-day event
                event_body = {
                    'summary': title,
                    'description': description,
                    'start': {
                        'date': event_date.isoformat(),
                    },
                    'end': {
                        'date': (event_date + timedelta(days=1)).isoformat(),
                    }
                }
                event_type = 'all_day'
            
            # Create the event
            created_event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            
            print(f"✅ Event created successfully: {created_event['id']}")
            
            # Format response
            response_data = {
                'id': created_event['id'],
                'summary': created_event['summary'],
                'link': created_event.get('htmlLink'),
                'meet_link': self._extract_meet_link(created_event),
                'type': event_type
            }
            
            if event_type == 'timed':
                response_data['start'] = start_datetime.strftime('%b %d, %Y at %I:%M %p')
                response_data['end'] = end_datetime.strftime('%b %d, %Y at %I:%M %p')
                display_date = start_datetime.strftime('%B %d, %Y at %I:%M %p')
            else:
                response_data['date'] = event_date.strftime('%b %d, %Y')
                display_date = event_date.strftime('%B %d, %Y (All day)')
            
            return {
                'success': True,
                'action': 'create_event',
                'data': response_data,
                'message': f'Event created: {title} on {display_date}'
            }
            
        except Exception as e:
            traceback.print_exc()
            error_msg = str(e)
            if 'invalid' in error_msg.lower():
                return {'success': False, 'message': f'Invalid date/time format. Please use format like "tomorrow at 2pm" or "2024-12-31 at 15:30"'}
            return {'success': False, 'message': f'Error creating event: {error_msg}'}
    
    def get_event(self, parsed):
        """Get a specific event by ID."""
        try:
            event_id = parsed.get('event_id')
            if not event_id:
                return {'success': False, 'message': 'Event ID is required'}
            
            event = self.calendar_service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            formatted_event = self._format_event(event)
            
            return {
                'success': True,
                'action': 'get_event',
                'data': formatted_event,
                'message': f'Event: {event["summary"]}'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error getting event: {str(e)}'}
    
    def delete_event(self, parsed):
        """Delete an event."""
        try:
            event_id = parsed.get('event_id')
            if not event_id:
                return {'success': False, 'message': 'Event ID is required'}
            
            # First get the event to confirm it exists
            event = self.calendar_service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            event_title = event.get('summary', 'Unknown')
            
            # Delete the event
            self.calendar_service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            return {
                'success': True,
                'action': 'delete_event',
                'message': f'Event deleted: {event_title}'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error deleting event: {str(e)}'}
    
    def delete_all_events(self, parsed):
        """Delete all upcoming events (asks for confirmation)."""
        try:
            # Get upcoming events
            now = datetime.utcnow().isoformat() + 'Z'
            later = (datetime.utcnow() + timedelta(days=365)).isoformat() + 'Z'
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=later,
                maxResults=100,
                singleEvents=True
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return {
                    'success': True,
                    'message': 'No upcoming events to delete'
                }
            
            # Store event IDs in session for confirmation
            event_ids = [event['id'] for event in events]
            event_count = len(events)
            
            # Return confirmation request
            return {
                'success': True,
                'action': 'confirm_delete_all',
                'requires_confirmation': True,
                'confirmation_type': 'delete_all_events',
                'data': {
                    'event_ids': event_ids,
                    'event_count': event_count
                },
                'message': f'⚠️ Are you sure you want to delete all {event_count} upcoming events? Say "yes" to confirm or "no" to cancel.'
            }
            
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def confirm_delete_all(self, parsed):
        """Confirm and execute delete all events."""
        try:
            event_ids = parsed.get('event_ids', [])
            if not event_ids:
                return {'success': False, 'message': 'No events to delete'}
            
            deleted_count = 0
            errors = []
            
            for event_id in event_ids:
                try:
                    self.calendar_service.events().delete(
                        calendarId='primary',
                        eventId=event_id
                    ).execute()
                    deleted_count += 1
                except Exception as e:
                    errors.append(str(e))
            
            if errors:
                return {
                    'success': True,
                    'message': f'✅ Deleted {deleted_count} events, but encountered {len(errors)} errors'
                }
            else:
                return {
                    'success': True,
                    'message': f'✅ Successfully deleted all {deleted_count} upcoming events'
                }
            
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def _format_events(self, events):
        """Format a list of events for display."""
        formatted = []
        for event in events:
            formatted.append(self._format_event(event))
        return formatted
    
    def _format_event(self, event):
        """Format a single event for display."""
        # Parse start and end times
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        # Determine if it's an all-day event
        is_all_day = 'date' in event['start'] and 'dateTime' not in event['start']
        
        # Format for display
        try:
            if is_all_day:
                # All-day event
                start_dt = datetime.fromisoformat(start)
                display_start = start_dt.strftime('%B %d, %Y (All day)')
                display_date = start_dt.strftime('%B %d, %Y')
            else:
                # Timed event
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                # Convert to local time for display
                local_tz = pytz.timezone(self.timezone)
                start_local = start_dt.astimezone(local_tz)
                display_start = start_local.strftime('%B %d, %Y at %I:%M %p')
                display_date = start_local.strftime('%B %d, %Y')
        except Exception as e:
            print(f"Error formatting date {start}: {e}")
            display_start = start
            display_date = start
        
        return {
            'id': event['id'],
            'summary': event['summary'],
            'description': event.get('description', ''),
            'start': start,
            'end': end,
            'display_start': display_start,
            'display_date': display_date,
            'is_all_day': is_all_day,
            'link': event.get('htmlLink'),
            'meet_link': self._extract_meet_link(event)
        }
    
    def _extract_meet_link(self, event):
        """Extract Google Meet link from event if present."""
        if 'conferenceData' in event:
            for entry_point in event['conferenceData'].get('entryPoints', []):
                if entry_point.get('entryPointType') == 'video':
                    return entry_point.get('uri')
        return None
    
    def get_all_events(self):
        """API endpoint to get all events."""
        return self.list_events(max_results=50)
    
    def create_event_api(self, data):
        """API endpoint to create an event from form data."""
        return self.create_event(data)
    
    def delete_event_api(self, event_id):
        """API endpoint to delete an event."""
        return self.delete_event({'event_id': event_id})