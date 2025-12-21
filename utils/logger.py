import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Any
from enum import Enum

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class PipelineLogger:
    """Centralized logger for pipeline activities with real-time streaming support"""

    def __init__(self):
        self.logs = []
        self.sessions = {}  # session_id -> logs
        self.lock = threading.Lock()
        self.max_logs_per_session = 1000
        self.max_global_logs = 5000

    def log(self, session_id: str, level: LogLevel, message: str,
            stage: str = None, metadata: Dict = None):
        """Add a log entry"""
        timestamp = datetime.now().isoformat()

        log_entry = {
            'timestamp': timestamp,
            'level': level.value,
            'message': message,
            'stage': stage,
            'metadata': metadata or {}
        }

        with self.lock:
            # Add to session logs
            if session_id not in self.sessions:
                self.sessions[session_id] = []

            self.sessions[session_id].append(log_entry)

            # Limit session logs
            if len(self.sessions[session_id]) > self.max_logs_per_session:
                self.sessions[session_id] = self.sessions[session_id][-self.max_logs_per_session:]

            # Add to global logs
            self.logs.append(log_entry)

            # Limit global logs
            if len(self.logs) > self.max_global_logs:
                self.logs = self.logs[-self.max_global_logs:]

    def debug(self, session_id: str, message: str, stage: str = None, **kwargs):
        self.log(session_id, LogLevel.DEBUG, message, stage, kwargs)

    def info(self, session_id: str, message: str, stage: str = None, **kwargs):
        self.log(session_id, LogLevel.INFO, message, stage, kwargs)

    def success(self, session_id: str, message: str, stage: str = None, **kwargs):
        self.log(session_id, LogLevel.SUCCESS, message, stage, kwargs)

    def warning(self, session_id: str, message: str, stage: str = None, **kwargs):
        self.log(session_id, LogLevel.WARNING, message, stage, kwargs)

    def error(self, session_id: str, message: str, stage: str = None, **kwargs):
        self.log(session_id, LogLevel.ERROR, message, stage, kwargs)

    def get_session_logs(self, session_id: str) -> List[Dict]:
        """Get all logs for a specific session"""
        with self.lock:
            return self.sessions.get(session_id, [])

    def get_recent_logs(self, session_id: str, since: float = None) -> List[Dict]:
        """Get logs since a specific timestamp"""
        logs = self.get_session_logs(session_id)
        if since is None:
            return logs

        return [log for log in logs if
                datetime.fromisoformat(log['timestamp']).timestamp() > since]

    def clear_session(self, session_id: str):
        """Clear logs for a session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

    def clear_old_sessions(self, max_age_hours: int = 24):
        """Clear sessions older than max_age_hours"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        with self.lock:
            to_remove = []
            for session_id, logs in self.sessions.items():
                if not logs:
                    continue
                last_log_time = datetime.fromisoformat(logs[-1]['timestamp']).timestamp()
                if last_log_time < cutoff_time:
                    to_remove.append(session_id)

            for session_id in to_remove:
                del self.sessions[session_id]


# Global logger instance
pipeline_logger = PipelineLogger()