"""Lab management - tracks running labs and learning state"""

import os
import json

# In-memory storage (in production: use database)
ACTIVE_LABS = {}


class LabSession:
    def __init__(self, lab_id, transcript, project_context, container_id, dockerfile, video_id=None):
        self.lab_id = lab_id
        self.transcript = transcript
        self.project_context = project_context
        self.container_id = container_id
        self.dockerfile = dockerfile
        self.video_id = video_id
        self.learning_plan = None
        self.conversation_history = []
        self.executed_commands = []

    def to_dict(self):
        return {
            'lab_id': self.lab_id,
            'container_id': self.container_id,
            'project_context': self.project_context,
            'learning_plan': self.learning_plan,
            'conversation_history': self.conversation_history,
            'executed_commands': self.executed_commands,
            'video_id': self.video_id,
        }


def create_lab(lab_id, transcript, project_context, container_id, dockerfile, video_id=None):
    """Create a new lab session"""
    ACTIVE_LABS[lab_id] = LabSession(lab_id, transcript, project_context, container_id, dockerfile, video_id)
    return ACTIVE_LABS[lab_id]


def get_lab(lab_id):
    """Get a lab session"""
    return ACTIVE_LABS.get(lab_id)


def update_lab_plan(lab_id, plan):
    """Update learning plan"""
    if lab_id in ACTIVE_LABS:
        ACTIVE_LABS[lab_id].learning_plan = plan


def add_conversation(lab_id, role, message):
    """Add to conversation history"""
    if lab_id in ACTIVE_LABS:
        ACTIVE_LABS[lab_id].conversation_history.append({
            'role': role,
            'message': message
        })


def add_executed_command(lab_id, command, output):
    """Track executed commands"""
    if lab_id in ACTIVE_LABS:
        ACTIVE_LABS[lab_id].executed_commands.append({
            'command': command,
            'output': output
        })
