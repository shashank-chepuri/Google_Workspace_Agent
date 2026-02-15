# config/mongodb.py
from flask_pymongo import PyMongo
import os
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    """MongoDB connection manager"""
    
    def __init__(self, app=None):
        self.mongo = PyMongo()
        self.uri = os.getenv('MONGO_URI')
        self.db_name = os.getenv('MONGO_DB_NAME', 'workspace_agent')
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize MongoDB with Flask app"""
        app.config['MONGO_URI'] = self.uri
        self.mongo.init_app(app)
        
        # Test connection
        try:
            # The ismaster command is cheap and doesn't require auth
            self.mongo.cx.admin.command('ismaster')
            print("✅ MongoDB connected successfully!")
        except Exception as e:
            print(f"❌ MongoDB connection error: {e}")
    
    @property
    def db(self):
        """Get database instance"""
        return self.mongo.cx[self.db_name]
    
    @property
    def friends(self):
        """Get friends collection"""
        return self.db.friends
    
    def ping(self):
        """Check if MongoDB is connected"""
        try:
            self.mongo.cx.admin.command('ping')
            return True
        except:
            return False

# Create global instance
mongodb = MongoDB()