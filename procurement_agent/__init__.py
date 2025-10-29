"""
Procurement Agent System
A conversational agent for California state procurement data
"""
from .workflow import create_workflow
from .config import Config

__version__ = "1.0.0"
__all__ = ["create_workflow", "Config"]
