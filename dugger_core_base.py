# DuggerCore Base Library
# Shared components for ecosystem-wide error handling and caching

import functools
import time
from typing import Any


class DuggerToolError(Exception):
    """Custom exception for tool-related errors."""
    
    def __init__(self, tool_name: str, command: list[str], message: str) -> None:
        self.tool_name = tool_name
        self.command = command
        self.message = message
        super().__init__(f"{tool_name}: {message}")


def ttl_cache(ttl_seconds: int = 30):
    """Simple TTL cache decorator for tool status."""
    def decorator(func):
        cache = {}
        timestamps = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # Check if cache entry exists and is still valid
            if key in cache and current_time - timestamps[key] < ttl_seconds:
                return cache[key]
            
            # Compute and cache result
            result = func(*args, **kwargs)
            cache[key] = result
            timestamps[key] = current_time
            return result
        
        return wrapper
    return decorator


# Version info for compatibility checking
__version__ = "1.0.0"
__all__ = ["DuggerToolError", "ttl_cache"]
