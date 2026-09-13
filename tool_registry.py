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

def add_tool(function_info):
    """Decorator to register a function as a tool with its metadata."""
    def decorator(func):
        function_name: str = function_info.get("name", func.__name__)
        _tools[function_name] = Tool(
            name = function_name,
            description = function_info.get("description", func.__doc__),
            parameters = function_info.get("parameters", func.__annotations__),
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