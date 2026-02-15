# email_operations.py
import re
import base64
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

def parse_recipients(text: str):
    """Extract email addresses from text."""
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    out = []
    seen = set()
    for e in emails:
        e = e.strip().strip(",;")
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out

def _make_attachment_part(filename: str, file_data: bytes):
    part = MIMEBase("application", "octet-stream")
    part.set_payload(file_data)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    return part

def send_email_with_attachments(gmail_service, recipients, subject, body_text, attachments=None):
    """Send email with optional attachments."""
    if not recipients:
        raise ValueError("No recipients provided.")
    
    if attachments:
        message = MIMEMultipart()
        message["to"] = ", ".join(recipients)
        message["subject"] = subject
        message.attach(MIMEText(body_text, "plain"))
        
        for filename, filedata in attachments:
            part = _make_attachment_part(filename, filedata)
            message.attach(part)
    else:
        message = MIMEText(body_text, "plain")
        message["to"] = ", ".join(recipients)
        message["subject"] = subject
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

def generate_email_draft(co_client, context: str):
    """Generate a professional email draft."""
    if not context or len(context.strip()) < 5:
        return None, "Please provide more details about what email you want to draft."
    
    prompt = f"""You are a professional email assistant. Generate a complete, ready-to-send email based on this request:

Request: {context}

Create a JSON response with:
1. "subject": A clear, concise subject line (max 10 words)
2. "body": The complete email body with:
   - Appropriate greeting
   - Clear main message
   - Professional closing
   - Signature placeholder: [Your Name]

The email should be professional, clear, and ready to send immediately.

Return ONLY valid JSON, no other text:"""
    
    try:
        # UPDATED: Changed from "command-r-plus" to "command-r-plus-08-2024"
        resp = co_client.chat(
            model="command-r-plus-08-2024", 
            message=prompt, 
            temperature=0.3
        )
        text = (resp.text or "").strip()
        
        # Clean markdown
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # Try to parse JSON
        try:
            data = json.loads(text)
            subject = data.get("subject", "").strip()
            body = data.get("body", "").strip()
            
            if not subject:
                first_line = body.split('\n')[0] if body else ""
                subject = first_line[:50] if first_line else "Email from Workspace Agent"
            
            return subject, body
            
        except json.JSONDecodeError:
            # Fallback: try to extract subject and body from text
            lines = text.split('\n')
            subject = ""
            body_parts = []
            
            for line in lines:
                if line.lower().startswith("subject:") or line.lower().startswith("subject:"):
                    subject = line.split(":", 1)[1].strip()
                elif line.strip() and not line.lower().startswith(("json", "```")):
                    body_parts.append(line.strip())
            
            if not subject and body_parts:
                subject = body_parts[0][:50]
            
            body = "\n".join(body_parts) if body_parts else text
            return subject, body
            
    except Exception as e:
        return None, f"⚠️ Drafting failed: {e}"
    
    return None, "⚠️ Could not generate email draft."

def refine_email_draft(co_client, instruction: str, current_subject: str, current_body: str):
    """Refine the current draft based on natural language instruction."""
    if not current_body:
        return current_subject, "⚠️ No draft exists to refine."
    
    prompt = f"""You are a professional email assistant. Refine this email draft according to the instruction.

Current Email:
Subject: {current_subject or '(No subject)'}
Body: {current_body}

Instruction: {instruction}

Return ONLY a JSON object with "subject" and "body" containing the refined email.
Keep the same general content but adjust the tone/length/style as requested."""
    
    try:
        # UPDATED: Changed from "command-r-plus" to "command-r-plus-08-2024"
        resp = co_client.chat(
            model="command-r-plus-08-2024", 
            message=prompt, 
            temperature=0.2
        )
        text = (resp.text or "").strip()
        
        # Clean markdown
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        
        try:
            data = json.loads(text)
            subject = data.get("subject", "").strip() or current_subject
            body = data.get("body", "").strip() or current_body
            return subject, body
        except json.JSONDecodeError:
            return current_subject, current_body + f"\n\n[Refinement attempt failed: using original]"
            
    except Exception as e:
        return current_subject, current_body + f"\n\n[Refinement failed: {e}]"

def interactive_draft_prompt():
    """Guide user through creating a detailed email draft."""
    print("\n📝 Let's create your email draft. Please provide:")
    
    purpose = input("Purpose of this email (e.g., sick leave, meeting request, etc.): ").strip()
    if not purpose:
        return None
    
    recipient_type = input("Who is this for? (manager, colleague, client, team, etc.): ").strip()
    details = input("Key details/dates/reason: ").strip()
    tone = input("Tone? (formal, casual, urgent, polite) [formal]: ").strip() or "formal"
    
    context = f"Email purpose: {purpose}\nRecipient: {recipient_type}\nDetails: {details}\nTone: {tone}"
    return context