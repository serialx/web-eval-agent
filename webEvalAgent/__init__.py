#!/usr/bin/env python3
"""WebEvalAgent Package - Configure logging before any imports."""

import os
import sys

# Set environment variables FIRST before any logging import
os.environ["BROWSER_USE_LOGGING_LEVEL"] = "CRITICAL"
os.environ["LANGCHAIN_VERBOSE"] = "false"
os.environ["LANGCHAIN_TRACING"] = "false"
os.environ["LOG_LEVEL"] = "CRITICAL"
os.environ["BROWSER_USE_LOG_LEVEL"] = "CRITICAL"
os.environ["PYTHONWARNINGS"] = "ignore"

import logging

# Silence all logging to stdout to prevent MCP communication issues
# This must happen before any other imports

# Create a null handler that discards all messages
null_handler = logging.NullHandler()

# Configure the root logger
root_logger = logging.getLogger()
root_logger.handlers = [null_handler]
root_logger.setLevel(logging.CRITICAL)

# Override logging.basicConfig to prevent reconfiguration
def no_op(*args, **kwargs):
    """No-op function to replace logging.basicConfig."""
    pass

logging.basicConfig = no_op

# Pre-configure all known problematic loggers
problematic_loggers = [
    "browser_use",
    "agent", 
    "browser",
    "playwright",
    "asyncio",
    "urllib3",
    "httpx",
    "httpcore",
    "werkzeug",
    "socketio",
    "engineio",
    "flask",
    "langchain",
    "anthropic",
    "openai",
    "",  # Empty string for the root logger
]

for logger_name in problematic_loggers:
    logger = logging.getLogger(logger_name)
    logger.handlers = [null_handler]
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False

# Also try to redirect stdout temporarily during imports
class SuppressOutput:
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr