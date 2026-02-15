# models/history_model.py
from datetime import datetime
from bson import ObjectId
from bson.json_util import dumps
import json
import re

class HistoryModel:
    """MongoDB model for command history"""
    
    def __init__(self, db):
        self.collection = db.history
    
    def to_json(self, data):
        """Convert MongoDB ObjectId to string for JSON serialization."""
        return json.loads(dumps(data))
    
    def log(self, user_id, user_name, command, response, action, success=True, error_msg=None):
        """Log a command to history."""
        try:
            history_entry = {
                'user_id': user_id,
                'user_name': user_name,
                'timestamp': datetime.utcnow(),
                'command': command,
                'response': response[:500] if response else '',
                'action': action,
                'success': success,
                'error': error_msg
            }
            
            result = self.collection.insert_one(history_entry)
            history_entry['_id'] = result.inserted_id
            return self.to_json(history_entry)
        except Exception as e:
            print(f"⚠️ Error logging to history: {e}")
            return None
    
    def get_user_history(self, user_id, limit=50, skip=0):
        """Get user's command history with pagination."""
        try:
            cursor = self.collection.find(
                {'user_id': user_id}
            ).sort('timestamp', -1).skip(skip).limit(limit)
            return self.to_json(list(cursor))
        except Exception as e:
            print(f"⚠️ Error getting history: {e}")
            return []
    
    def search_history(self, user_id, query, limit=50):
        """Search user's command history."""
        try:
            regex_pattern = re.compile(query, re.IGNORECASE)
            cursor = self.collection.find({
                'user_id': user_id,
                '$or': [
                    {'command': regex_pattern},
                    {'response': regex_pattern}
                ]
            }).sort('timestamp', -1).limit(limit)
            return self.to_json(list(cursor))
        except Exception as e:
            print(f"⚠️ Error searching history: {e}")
            return []
    
    def get_stats(self, user_id):
        """Get statistics for user."""
        try:
            total = self.collection.count_documents({'user_id': user_id})
            
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today = self.collection.count_documents({
                'user_id': user_id,
                'timestamp': {'$gte': today_start}
            })
            
            total_with_outcome = self.collection.count_documents({
                'user_id': user_id,
                'success': {'$exists': True}
            })
            
            successful = self.collection.count_documents({
                'user_id': user_id,
                'success': True
            })
            
            success_rate = round((successful / total_with_outcome * 100), 1) if total_with_outcome > 0 else 0
            
            # Get most used commands
            pipeline = [
                {'$match': {'user_id': user_id, 'action': {'$ne': 'unknown'}}},
                {'$group': {'_id': '$action', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}},
                {'$limit': 5}
            ]
            
            top_commands = list(self.collection.aggregate(pipeline))
            
            return {
                'total_commands': total,
                'today_commands': today,
                'success_rate': success_rate,
                'top_commands': self.to_json(top_commands)
            }
        except Exception as e:
            print(f"⚠️ Error getting stats: {e}")
            return {
                'total_commands': 0,
                'today_commands': 0,
                'success_rate': 0,
                'top_commands': []
            }
    
    def clear_history(self, user_id):
        """Clear all history for a user."""
        try:
            result = self.collection.delete_many({'user_id': user_id})
            return result.deleted_count
        except Exception as e:
            print(f"⚠️ Error clearing history: {e}")
            return 0
    
    def delete_old_entries(self, days=30):
        """Delete history entries older than specified days."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            result = self.collection.delete_many({'timestamp': {'$lt': cutoff}})
            return result.deleted_count
        except Exception as e:
            print(f"⚠️ Error deleting old entries: {e}")
            return 0