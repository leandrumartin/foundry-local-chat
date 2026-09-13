from tool_registry import add_tool
import datetime

function_info = {
    "name": "get_date",
    "description": "Get the current date",
    "parameters": {},
}

@add_tool(function_info)
def get_date():
    """Get current date."""
    return datetime.datetime.now().strftime("%Y-%m-%d")