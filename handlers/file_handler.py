# handlers/file_handler.py
import base64
import io
import traceback
import os
import cohere
from dotenv import load_dotenv
from googleapiclient.http import MediaIoBaseDownload

# Try importing PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class FileHandler:
    def __init__(self, google_services):
        self.drive = google_services.get('drive')
        self.sheets = google_services.get('sheets')
        self.docs = google_services.get('docs')
        self.slides = google_services.get('slides')
    
    def handle(self, action, parsed, command):
        """Route file actions to appropriate methods."""
        if action == 'list_files':
            return self.list_files()
        elif action == 'search_files':
            return self.search_files(parsed)
        elif action == 'show_images':
            return self.show_images()
        elif action == 'show_image':
            return self.show_image(parsed)
        elif action == 'view_folder':
            return self.view_folder(parsed)
        else:
            return {'success': False, 'message': 'Unknown file action'}
    
    # Helper functions
    def _escape_for_drive_q(self, s):
        """Escape single quotes for Google Drive query."""
        return s.replace("'", "\\'").strip()
    
    def _pick_best_match(self, hits, desired_name):
        """Pick the best matching file from search results."""
        if not hits:
            return None
        if desired_name:
            for f in hits:
                if f.get("name", "").lower() == desired_name.lower():
                    return f
        return hits[0] if hits else None
    
    def _deref_shortcut(self, file_dict):
        """Resolve a shortcut to its target file."""
        if not file_dict:
            return file_dict
        if file_dict.get("mimeType") == "application/vnd.google-apps.shortcut":
            target_id = (file_dict.get("shortcutDetails") or {}).get("targetId")
            if target_id:
                try:
                    return self.get_file_by_id(target_id)
                except Exception:
                    pass
        return file_dict
    
    def get_file_by_id(self, file_id):
        """Get file metadata by ID."""
        return self.drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,shortcutDetails(targetId,targetMimeType)"
        ).execute()
    
    def search_files_drive(self, keyword):
        """Search for files by keyword."""
        kw = self._escape_for_drive_q(keyword)
        results = self.drive.files().list(
            q=f"trashed = false and name contains '{kw}'",
            fields="files(id, name, mimeType, modifiedTime, shortcutDetails(targetId,targetMimeType))"
        ).execute()
        return results.get("files", [])
    
    def download_file(self, file_dict):
        """Download file content."""
        file_dict = self._deref_shortcut(file_dict)
        file_id = file_dict["id"]
        mime_type = file_dict["mimeType"]
        
        export_map = {
            "application/vnd.google-apps.document": "application/pdf",
            "application/vnd.google-apps.spreadsheet": "application/pdf",
            "application/vnd.google-apps.presentation": "application/pdf",
            "application/vnd.google-apps.drawing": "application/pdf",
        }
        
        if mime_type in export_map:
            request = self.drive.files().export_media(fileId=file_id, mimeType=export_map[mime_type])
        else:
            request = self.drive.files().get_media(fileId=file_id)
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read()
    
    def extract_file_content(self, file_dict):
        """Extract text content from various file types."""
        file_dict = self._deref_shortcut(file_dict)
        file_id = file_dict["id"]
        mime_type = file_dict["mimeType"]
        
        try:
            # Google Docs
            if mime_type == "application/vnd.google-apps.document":
                doc = self.docs.documents().get(documentId=file_id).execute()
                text = []
                for c in doc.get("body", {}).get("content", []):
                    if "paragraph" in c:
                        for e in c["paragraph"].get("elements", []):
                            tr = e.get("textRun", {})
                            if tr and "content" in tr:
                                text.append(tr["content"])
                return self._clean_text("".join(text))
            
            # Google Sheets
            if mime_type == "application/vnd.google-apps.spreadsheet":
                sheet = self.sheets.spreadsheets().values().get(
                    spreadsheetId=file_id, range="A1:J50"
                ).execute()
                values = sheet.get("values", [])
                return self._clean_text("\n".join([", ".join(row) for row in values]))
            
            # Google Slides
            if mime_type == "application/vnd.google-apps.presentation":
                pres = self.slides.presentations().get(presentationId=file_id).execute()
                text = []
                for slide in pres.get("slides", []):
                    for el in slide.get("pageElements", []):
                        shape = el.get("shape", {})
                        if "text" in shape:
                            for te in shape["text"].get("textElements", []):
                                if "textRun" in te and "content" in te["textRun"]:
                                    text.append(te["textRun"]["content"])
                return self._clean_text("".join(text))
            
            # For other file types, return None
            return None
            
        except Exception as e:
            print(f"⚠️ Error extracting content: {e}")
            return None
    
    def _clean_text(self, s):
        """Clean text by removing non-printable characters."""
        import re
        import string
        if not s:
            return s
        allowed = set(string.printable) | set("“”‘’—–•·\u200b\t\n\r")
        cleaned = ''.join(ch if (ch in allowed or ch.isprintable()) else ' ' for ch in s)
        cleaned = cleaned.replace('\u200b', '')
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()
    
    def is_image_file(self, mime_type, filename=None):
        """Check if file is an image based on mime type or extension."""
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
    
    def handle_summarize(self, parsed, command):
        """Handle file summarization."""
        file_name = parsed.get('file_name', '')
        try:
            hits = self.search_files_drive(file_name)
            if not hits:
                return {'success': False, 'message': 'File not found'}
            
            file_dict = self._pick_best_match(hits, file_name)
            file_dict = self._deref_shortcut(file_dict)
            
            content = self.extract_file_content(file_dict)
            
            if not content:
                return {'success': False, 'message': 'Could not extract content'}
            
            load_dotenv()
            cohere_api_key = os.getenv("COHERE_API_KEY")
            co = cohere.Client(cohere_api_key)
            
            # Summarize the content
            prompt = f"Please provide a concise summary of the following text:\n\n{content[:5000]}"
            response = co.chat(
                model="command-r-plus-08-2024",
                message=prompt,
                temperature=0.3
            )
            summary = response.text.strip() if response and response.text else "No summary generated."
            
            return {
                'success': True,
                'action': 'summarize_file',
                'data': {
                    'file_name': file_dict.get('name', 'Unknown'),
                    'summary': summary
                },
                'message': 'Summary generated'
            }
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'message': f'Error summarizing: {str(e)}'}
    
    def list_files(self):
        """List files from Google Drive."""
        try:
            results = self.drive.files().list(
                pageSize=20,
                q="trashed = false",
                fields="files(id, name, mimeType)"
            ).execute()
            files = results.get('files', [])
            return {
                'success': True,
                'action': 'list_files',
                'data': files,
                'message': f'Found {len(files)} files'
            }
        except Exception as e:
            return {'success': False, 'message': f'Error listing files: {str(e)}'}
    
    def search_files(self, parsed):
        """Search files by keyword."""
        # Handle both string and dict input
        if isinstance(parsed, str):
            keyword = parsed
        else:
            keyword = parsed.get('keyword', '') if parsed else ''
        
        if not keyword:
            return {'success': False, 'message': 'Search keyword is required'}
        
        try:
            files = self.search_files_drive(keyword)
            return {
                'success': True,
                'action': 'search_files',
                'data': files,
                'message': f'Found {len(files)} files matching "{keyword}"'
            }
        except Exception as e:
            return {'success': False, 'message': f'Error searching files: {str(e)}'}
    
    def show_images(self):
        """Show all images from Drive."""
        try:
            image_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", 
                          "image/bmp", "image/webp"]
            all_images = []
            
            for img_type in image_types:
                try:
                    results = self.drive.files().list(
                        q=f"trashed = false and mimeType = '{img_type}'",
                        fields="files(id, name, mimeType, modifiedTime)",
                        pageSize=50
                    ).execute()
                    all_images.extend(results.get('files', []))
                except Exception:
                    continue
            
            # Remove duplicates
            unique_images = {f['id']: f for f in all_images}.values()
            
            return {
                'success': True,
                'action': 'show_images',
                'data': list(unique_images)[:50],
                'message': f'Found {len(unique_images)} images'
            }
        except Exception as e:
            return {'success': False, 'message': f'Error finding images: {str(e)}'}
    
    def show_image(self, parsed):
        """Show a specific image."""
        file_name = parsed.get('file_name', '')
        try:
            hits = self.search_files_drive(file_name)
            if not hits:
                return {'success': False, 'message': f'Image "{file_name}" not found'}
            
            file_dict = self._pick_best_match(hits, file_name)
            
            if not self.is_image_file(file_dict.get('mimeType', ''), file_name):
                return {'success': False, 'message': f'File is not an image'}
            
            image_data = self.download_file(file_dict)
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            return {
                'success': True,
                'action': 'show_image',
                'data': {
                    'file_name': file_dict.get('name', file_name),
                    'image_data': image_base64,
                    'mime_type': file_dict.get('mimeType'),
                    'file_id': file_dict.get('id')
                },
                'message': f'Image loaded: {file_name}'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error loading image: {str(e)}'}
    
    def view_folder(self, parsed):
        """View contents of a folder."""
        folder_name = parsed.get('folder_name', '')
        try:
            folders = self.drive.files().list(
                q=f"trashed = false and mimeType = 'application/vnd.google-apps.folder' and name contains '{self._escape_for_drive_q(folder_name)}'",
                fields="files(id, name)"
            ).execute().get('files', [])
            
            if not folders:
                return {'success': False, 'message': f'Folder "{folder_name}" not found'}
            
            folder = folders[0]
            
            contents = self.drive.files().list(
                q=f"trashed = false and '{folder['id']}' in parents",
                fields="files(id, name, mimeType, modifiedTime)"
            ).execute().get('files', [])
            
            images = []
            other_files = []
            
            for f in contents:
                if self.is_image_file(f.get('mimeType', ''), f.get('name', '')):
                    images.append(f)
                else:
                    other_files.append(f)
            
            return {
                'success': True,
                'action': 'view_folder',
                'data': {
                    'folder_name': folder['name'],
                    'folder_id': folder['id'],
                    'images': images[:30],
                    'other_files': other_files[:20],
                    'total': len(contents)
                },
                'message': f'Found {len(images)} images and {len(other_files)} other files'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error viewing folder: {str(e)}'}