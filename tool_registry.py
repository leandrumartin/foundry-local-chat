from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class Tool:
    """A dataclass to represent a tool with its metadata and function."""
    name: str
    description: str
    parameters: dict
    function: Callable[..., Any]

_tools: dict[str, Tool] = {}

def register_tool(
    *,
    name: str,
    description: str,
    parameters: dict,
):
    """Decorator to register a function as a tool with its metadata.
    
    Args:
        name (str): The name of the tool.
        description (str): A brief description of the tool.
        parameters (dict): A dictionary describing the parameters of the tool.
    """
    def decorator(func):
        function_name: str = name or func.__name__
        _tools[function_name] = Tool(
            name = function_name,
            description = description or func.__doc__ or "",
            parameters = parameters or func.__annotations__,
            function = func
        )
        return func
    return decorator

def get_tool_schemas() -> list[dict]:
    """Return a list of tool schemas for all registered tools."""
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "strict": True,
        }
        for tool in _tools.values()
    ]

def get_tool_functions() -> dict[str, Callable[..., Any]]:
    """Return a dictionary mapping tool names to their corresponding functions."""
    return {
        name: tool.function
        for name, tool in _tools.items()
    }