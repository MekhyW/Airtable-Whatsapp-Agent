"""
Application state management module.
Separated from main.py to avoid circular imports.
"""

from typing import Dict, Any


# Global application state
app_state: Dict[str, Any] = {
    "agent": None,
    "mcp_manager": None,
    "settings": None
}


def get_app_state() -> Dict[str, Any]:
    """Get application state."""
    return app_state


def set_app_state(key: str, value: Any) -> None:
    """Set a value in the application state."""
    app_state[key] = value


def clear_app_state() -> None:
    """Clear all application state."""
    global app_state
    app_state = {
        "agent": None,
        "mcp_manager": None,
        "settings": None
    }