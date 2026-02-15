# handlers/draft_handler.py
from flask import session
from email_operations import (
    parse_recipients, send_email_with_attachments,
    generate_email_draft, refine_email_draft
)

class DraftHandler:
    def __init__(self):
        self.draft_key = 'draft'
    
    @property
    def draft(self):
        """Get current draft from session."""
        if self.draft_key not in session:
            session[self.draft_key] = {
                "subject": None,
                "body": None,
                "recipients": [],
                "context": "",
                "type": "email"
            }
        return session[self.draft_key]
    
    @draft.setter
    def draft(self, value):
        """Set draft in session."""
        session[self.draft_key] = value
        session.modified = True
    
    def save_draft(self):
        """Save current draft to session."""
        session.modified = True
    
    def handle(self, action, parsed, command, co_client, gmail_service):
        """Route draft actions to appropriate methods."""
        if action == 'draft_email':
            return self.draft_email(parsed, co_client)
        elif action == 'draft_summary':
            return self.draft_summary(parsed, command)
        elif action == 'show_draft':
            return self.show_draft()
        elif action == 'clear_draft':
            return self.clear_draft()
        elif action == 'refine_draft':
            return self.refine_draft(parsed, command, co_client)
        elif action == 'send_draft':
            return self.send_draft(parsed, command, gmail_service)
        else:
            return {'success': False, 'message': 'Unknown draft action'}
    
    def draft_email(self, parsed, co_client):
        """Create an email draft."""
        context = parsed.get('text', '').strip()
        
        if not context or len(context.split()) <= 2:
            return {
                'success': False,
                'action': 'draft_email',
                'needs_interactive': True,
                'message': 'Please provide more details'
            }
        
        subject, body = generate_email_draft(co_client, context)
        if not body or body.startswith('⚠️'):
            return {'success': False, 'message': body or 'Failed to create draft'}
        
        self.draft.update({
            'subject': subject or 'Drafted Email',
            'body': body,
            'recipients': parse_recipients(context),
            'context': context,
            'type': 'email'
        })
        self.save_draft()
        
        return {
            'success': True,
            'action': 'draft_email',
            'data': {'subject': subject, 'body': body},
            'message': 'Draft created'
        }
    
    def draft_summary(self, parsed, command):
        """Create a summary draft."""
        # This will be handled by file_handler and then call back
        # For now, return a special response
        return {
            'success': False,
            'needs_file_handler': True,
            'parsed': parsed,
            'command': command
        }
    
    def show_draft(self):
        """Show current draft."""
        if not self.draft.get('body'):
            return {'success': False, 'message': 'No draft exists'}
        
        return {
            'success': True,
            'action': 'show_draft',
            'data': self.draft,
            'message': 'Current draft'
        }
    
    def clear_draft(self):
        """Clear current draft."""
        self.draft.clear()
        self.draft.update({'subject': None, 'body': None, 'recipients': [], 'context': '', 'type': 'email'})
        self.save_draft()
        return {'success': True, 'message': 'Draft cleared'}
    
    def refine_draft(self, parsed, command, co_client):
        """Refine current draft."""
        if not self.draft.get('body'):
            return {'success': False, 'message': 'No draft exists'}
        
        instruction = parsed.get('instruction', command)
        subject, body = refine_email_draft(co_client, instruction, 
                                          self.draft['subject'], 
                                          self.draft['body'])
        
        self.draft['subject'] = subject or self.draft['subject']
        self.draft['body'] = body or self.draft['body']
        self.save_draft()
        
        return {
            'success': True,
            'action': 'refine_draft',
            'data': {'subject': self.draft['subject'], 'body': self.draft['body']},
            'message': 'Draft refined'
        }
    
    def send_draft(self, parsed, command, gmail_service):
        """Send current draft."""
        if not self.draft.get('body'):
            return {'success': False, 'message': 'No draft exists'}
        
        recipients = parsed.get('email') or parse_recipients(command) or self.draft['recipients']
        
        if not recipients:
            return {
                'success': False,
                'needs_recipients': True,
                'message': 'Please provide recipients'
            }
        
        try:
            send_email_with_attachments(
                gmail_service,
                recipients,
                self.draft['subject'] or 'Drafted Message',
                self.draft['body']
            )
            
            draft_type = self.draft.get('type', 'email')
            self.clear_draft()
            
            return {
                'success': True,
                'message': f'{"Summary" if draft_type == "summary" else "Email"} sent to {", ".join(recipients)}'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error sending: {str(e)}'}