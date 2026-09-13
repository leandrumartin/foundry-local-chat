import datetime

from tool_registry import register_tool


@register_tool(
    name = "get_date",
    description = "Get the current date",
    parameters = {},
)
def get_date():
    """Get current date."""
    return datetime.datetime.now().strftime("%Y-%m-%d")