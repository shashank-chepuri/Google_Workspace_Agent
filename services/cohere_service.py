# services/cohere_service.py
import os
import cohere
from dotenv import load_dotenv

load_dotenv()

def init_cohere():
    """Initialize Cohere client."""
    cohere_api_key = os.getenv("COHERE_API_KEY")
    if not cohere_api_key:
        raise ValueError("❌ COHERE_API_KEY not found in .env file")
    
    return cohere.Client(cohere_api_key)

def summarize_text(co_client, text):
    """Summarize text using Cohere's Chat API."""
    if not text or not text.strip():
        return "⚠️ No content to summarize."
    
    snippet = text.strip()
    if len(snippet) > 50000:
        snippet = snippet[:50000]
    
    try:
        prompt = f"""Please provide a concise summary of the following text in a short paragraph:
{snippet}"""
        
        response = co_client.chat(
            model="command-r-plus-08-2024",
            message=prompt,
            temperature=0.3
        )
        
        return response.text.strip() if response and response.text else "⚠️ No summary generated."
    except Exception as e:
        return f"⚠️ Summarization failed: {e}"