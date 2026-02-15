# share.py
from pyexpose import Expose
import time
import socket
import requests

def get_local_ip():
    """Get your local IP address for display."""
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

def check_server_running():
    """Check if Flask server is running."""
    try:
        requests.get("http://localhost:5000", timeout=2)
        return True
    except:
        return False

print("=" * 60)
print("🚀 Workspace Agent - Share with Friend")
print("=" * 60)

# Check if Flask is running
if not check_server_running():
    print("❌ Flask server is not running on port 5000!")
    print("📌 Please start your app first with: python app.py")
    exit(1)

print("✅ Flask server detected on port 5000")

# Get local IP
local_ip = get_local_ip()
print(f"📍 Local network: http://{local_ip}:5000")

print("\n🔄 Creating public tunnel...")
print("⏳ Please wait...")

try:
    # Create tunnel on port 5000
    expose = Expose(port=5000)
    
    # Start the tunnel and get URL
    url = expose.start()
    
    print("\n" + "=" * 60)
    print("✅ TUNNEL CREATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\n🌐 SHARE THIS URL WITH YOUR FRIEND:")
    print(f"\n   \033[1m{url}\033[0m")  # Bold text for URL
    print("\n" + "=" * 60)
    print("📝 INSTRUCTIONS FOR YOUR FRIEND:")
    print("   1. Open the URL above in Chrome/Firefox")
    print("   2. Click 'Continue with Google'")
    print("   3. They'll need to authorize the app")
    print("   4. Start using Workspace Agent!")
    print("=" * 60)
    print("\n⚠️  Keep this terminal open to maintain the tunnel")
    print("   Press Ctrl+C to stop sharing\n")
    
    # Keep the tunnel running
    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n👋 Shutting down tunnel...")
    expose.stop()
    print("✅ Tunnel closed. Goodbye!")
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Troubleshooting:")
    print("   1. Make sure your Flask app is running (python app.py)")
    print("   2. Check if port 5000 is free")
    print("   3. Try installing: pip install --upgrade pyexpose")