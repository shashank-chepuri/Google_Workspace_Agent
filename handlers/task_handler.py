# handlers/task_handler.py
import json
from datetime import datetime
from utils.helpers import load_json_file, save_json_file, generate_id, parse_date

TASKS_FILE = 'data/tasks.json'

class TaskHandler:
    def __init__(self):
        self.tasks = load_json_file(TASKS_FILE, [])
    
    def handle(self, action, parsed, command):
        """Route task actions to appropriate methods."""
        if action == 'list_tasks':
            return self.list_tasks()
        elif action == 'add_task':
            return self.add_task(parsed)
        elif action == 'complete_task':
            return self.complete_task(parsed)
        elif action == 'delete_task':
            return self.delete_task(parsed)
        else:
            return {'success': False, 'message': 'Unknown task action'}
    
    def list_tasks(self):
        """List all tasks."""
        if not self.tasks:
            return {
                'success': True,
                'action': 'list_tasks',
                'data': {'pending': [], 'completed': []},
                'message': 'No tasks found'
            }
        
        # Separate pending and completed tasks
        pending = [t for t in self.tasks if not t.get('completed')]
        completed = [t for t in self.tasks if t.get('completed')]
        
        # Sort pending tasks by due date (tasks without due date go to the end)
        def get_due_date(task):
            due = task.get('due')
            # Return a tuple: (has_due_date, due_date)
            # Tasks with due dates come first, sorted by date
            # Tasks without due dates come last
            if due:
                return (0, due)  # Has due date
            return (1, '9999-12-31')  # No due date
        
        pending.sort(key=get_due_date)
        
        # Sort completed tasks by completion date (newest first)
        def get_completed_date(task):
            return task.get('completed_at', task.get('created', '1970-01-01'))
        
        completed.sort(key=get_completed_date, reverse=True)
        
        return {
            'success': True,
            'action': 'list_tasks',
            'data': {
                'pending': pending,
                'completed': completed
            },
            'message': f'Found {len(pending)} pending and {len(completed)} completed tasks'
        }
    
    def add_task(self, parsed):
        """Add a new task."""
        text = parsed.get('text', '')
        due = parsed.get('due')
        
        if not text:
            return {'success': False, 'message': 'Task description is required'}
        
        # Parse due date if provided
        due_date = None
        if due:
            parsed_date = parse_date(due)
            if parsed_date:
                due_date = parsed_date.isoformat()
        
        task = {
            'id': generate_id(),
            'text': text,
            'created': datetime.now().isoformat(),
            'completed': False,
            'due': due_date
        }
        
        self.tasks.append(task)
        save_json_file(TASKS_FILE, self.tasks)
        
        due_text = f" due {due_date}" if due_date else ""
        return {
            'success': True,
            'action': 'add_task',
            'data': task,
            'message': f'✅ Task added: {text}{due_text}'
        }
    
    def complete_task(self, parsed):
        """Mark a task as complete."""
        task_id = parsed.get('task_id')
        
        for task in self.tasks:
            if task['id'] == task_id:
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                save_json_file(TASKS_FILE, self.tasks)
                return {
                    'success': True,
                    'action': 'complete_task',
                    'data': task,
                    'message': f'✅ Task completed: {task["text"]}'
                }
        
        return {'success': False, 'message': f'Task {task_id} not found'}
    
    def delete_task(self, parsed):
        """Delete a task."""
        task_id = parsed.get('task_id')
        
        for i, task in enumerate(self.tasks):
            if task['id'] == task_id:
                deleted = self.tasks.pop(i)
                save_json_file(TASKS_FILE, self.tasks)
                return {
                    'success': True,
                    'action': 'delete_task',
                    'message': f'✅ Task deleted: {deleted["text"]}'
                }
        
        return {'success': False, 'message': f'Task {task_id} not found'}
    
    def get_all_tasks(self):
        """API endpoint to get all tasks."""
        return {'success': True, 'data': self.tasks}
    
    def create_task_api(self, data):
        """API endpoint to create a task."""
        task = {
            'id': generate_id(),
            'text': data.get('text'),
            'created': datetime.now().isoformat(),
            'completed': False,
            'due': data.get('due')
        }
        self.tasks.append(task)
        save_json_file(TASKS_FILE, self.tasks)
        return {'success': True, 'data': task}
    
    def update_task_api(self, data):
        """API endpoint to update a task."""
        task_id = data.get('id')
        for task in self.tasks:
            if task['id'] == task_id:
                task.update(data)
                save_json_file(TASKS_FILE, self.tasks)
                return {'success': True, 'data': task}
        return {'success': False, 'message': 'Task not found'}