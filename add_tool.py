def add_tool(model_class, function_info):
    def decorator(func):
        function_name = function_info.get("name", func.__name__)
        model_class.tools.append({
            "type": "function",
            "name": function_name,
            "description": function_info.get("description", func.__doc__),
            "parameters": function_info.get("parameters", func.__annotations__),
            "strict": True,
        })
        model_class.tool_functions[function_name] = func
        return func
    return decorator