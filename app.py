import json
import threading
from dataclasses import dataclass, field

import gradio as gr

import tool_registry
from chat_history import ChatHistory
from foundry import FoundryManager
from user_tools import load_tools

load_tools()
available_tools: list = tool_registry.get_tool_schemas()

try:
    with open("models.txt", "r") as f:
        models = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print("models.txt not found. Please create the file and add model names, one per line.")
    print("Defaulting to smallest model: 'qwen2.5-0.5b.'")
    models = ["qwen2.5-0.5b"]

default_model = models[0]
manager: FoundryManager = FoundryManager()

@dataclass
class SessionContext:
    """A dataclass to hold serializable session context for the Gradio interface."""
    retain_loaded_models: bool = False
    pending_user_input: str = ""
    rebuild_history: bool = True  # Flag to indicate whether to rebuild the conversation history in the manager
    new_request: bool = True  # Flag to indicate whether this is a new model request


@dataclass
class RuntimeContext:
    """A dataclass to hold non-serializable runtime context for the Gradio interface."""
    history_manager: ChatHistory = field(default_factory=ChatHistory)
    stop_event: threading.Event = field(default_factory=threading.Event)


runtime_store = {}

def initialize_runtime(request: gr.Request):
    """Initialize the runtime context for the current session."""
    runtime_store[request.session_hash] = RuntimeContext()

def cleanup_runtime(request: gr.Request):
    """Clean up the runtime context for the current session."""
    assert request.session_hash is not None
    if request.session_hash in runtime_store:
        del runtime_store[request.session_hash]
    manager.unload_session(request.session_hash)

def get_runtime(request: gr.Request):
    """Get the runtime context for the current session."""
    if request.session_hash not in runtime_store:
        initialize_runtime(request)
    return runtime_store[request.session_hash]

def load_model(model_name: str, session: SessionContext, request: gr.Request, retain: bool = False):
    """Load a model into memory. If retain is False, unloads all other models except the one being loaded."""
    assert request.session_hash is not None
    session.rebuild_history = False
    manager.load_model(model_name, request.session_hash, retain)

    loaded_models_list = gr.Textbox(
        label="Loaded Models",
        value=", ".join(manager.loaded_model_names),
        interactive=False,
    )

    return loaded_models_list

def get_model_response(history: list[gr.MessageDict | gr.ChatMessage], session: SessionContext, enabled_tools: list[str], request: gr.Request, tool_results: list[dict] | None = None):
    """Get a response from the currently loaded model based on transformed user input and any conversation history that needs to be restored.
    """
    runtime = get_runtime(request)
    runtime.stop_event.clear()

    assert request.session_hash is not None

    # Restore session settings if this function is being called for the first time in a new request. The manager may
    #  override the user's tool_choice setting, so this restores the setting for each new request.
    if session.new_request:
        manager.restore_settings(request.session_hash)
        session.new_request = False

    user_input_object = None
    if session.pending_user_input != "":
        user_input_object = {"role": "user", "content": session.pending_user_input}
        history.append(user_input_object)
        session.pending_user_input = ""
        yield history

    history.append({"role": "assistant", "content": ""})
    print("Model response: ", end="", flush=True)

    if session.rebuild_history:
        history_to_pass = history
        session.rebuild_history = False
    else:
        if user_input_object is not None:
            history_to_pass = [user_input_object]
        else:
            history_to_pass = []

    tool_calls = []
    last_message_was_tool_call = False
    for chunk in manager.get_model_response(history_to_pass, request.session_hash, tool_results=tool_results):
        if runtime.stop_event.is_set():
            break
        if chunk["type"] == "text":
            # Check whether the last message in history is regular assistant text or a tool call. If it's a tool call, we need to create a new message for the regular assistant text.
            if last_message_was_tool_call:
                history.append({"role": "assistant", "content": chunk["content"]})
            else:
                history[-1]["content"] += chunk["content"]
            print(chunk["content"], end="", flush=True)
            last_message_was_tool_call = False
        elif chunk["type"] == "tool_call_list":
            tool_calls = chunk["content"]
            history.append(gr.ChatMessage(
                role="assistant",
                content="\n".join(
                    f"Called tool {function_name} with arguments {arguments_json}"
                    for _, function_name, arguments_json in tool_calls
                ),
                metadata={"title": "Tool calls"}
            ))
            print(f"\nTool calls: {tool_calls}", end="", flush=True)
            last_message_was_tool_call = True
        yield history

    # If the model made tool calls, call the tools, create message items to pass to model and add to history, and get a new response from the model
    new_tool_results = []
    if len(tool_calls) > 0:
        tool_functions = tool_registry.get_tool_functions()
        for call_id, function_name, arguments_json in tool_calls:
            if runtime.stop_event.is_set():
                break
            try:
                arguments = json.loads(arguments_json)
                if arguments is None:
                    arguments = {}
                if function_name in [json.loads(t)["name"] for t in enabled_tools] and function_name in tool_functions:
                    print(f"\nCalling tool: {function_name} with arguments: {arguments}")
                    try:
                        new_tool_result_content = json.dumps(tool_functions[function_name](**arguments))
                        print(f"Tool output: {new_tool_result_content}")
                        result = {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": new_tool_result_content,
                        }
                        new_tool_results.append(result)
                    except Exception as e:
                        print(f"Error calling tool '{function_name}': {e}")
                        result = {
                            "role": "assistant",
                            "tool_call_id": call_id,
                            "content": f"Error calling tool '{function_name}': {e}"
                        }
                        new_tool_results.append(result)
                else:
                    print(f"Tool '{function_name}' not found.")
                    result = {
                        "role": "assistant",
                        "tool_call_id": call_id,
                        "content": f"Tool '{function_name}' not found."
                    }
                    new_tool_results.append(result)
            except json.JSONDecodeError as e:
                print(f"Error decoding arguments for tool '{function_name}': {e}")
                result = {
                    "role": "assistant",
                    "tool_call_id": call_id,
                    "content": f"Error decoding arguments for tool '{function_name}': {e}"
                }
                new_tool_results.append(result)
            history.append(result)

        # Get a new response from the model after the tool calls
        if not runtime.stop_event.is_set():
            yield from get_model_response(history, session, enabled_tools, request, tool_results=new_tool_results)  # AUTO overrides REQUIRED so it's not stuck in an infinite loop of tool calls

def stop_generation(request: gr.Request):
    """Stop the model generation process."""
    runtime = get_runtime(request)
    runtime.stop_event.set()

def store_user_input_and_clear(user_input: dict[str, list] | str, session: SessionContext, request: gr.Request):
    """Store the user input for later use. In the case of multimodal input, only the text portion is stored.
    Returns an empty string to clear the input field in the UI."""
    if isinstance(user_input, str):
        session.pending_user_input = user_input
    else:
        session.pending_user_input = str(user_input.get("text", ""))
    return "", session

def update_conversation_history(request: gr.Request):
    """Update the conversation history in the UI."""
    runtime = get_runtime(request)
    return runtime.history_manager.update_conversation_history()

def update_current_conversation(history, request: gr.Request):
    """Update the current conversation in the UI."""
    runtime = get_runtime(request)
    runtime.history_manager.update_current_conversation(history)

def load_new_conversation(session: SessionContext, request: gr.Request):
    """Load a new conversation in the UI."""
    assert request.session_hash is not None
    runtime = get_runtime(request)
    manager.load_new_session(request.session_hash)
    session.rebuild_history = False
    return runtime.history_manager.load_new_conversation()

def load_previous_conversation(index: int, session: SessionContext, request: gr.Request):
    """Load a previous conversation from the history in the UI."""
    assert request.session_hash is not None
    runtime = get_runtime(request)
    manager.load_new_session(request.session_hash)
    session.rebuild_history = True
    return runtime.history_manager.load_previous_conversation(index)

def toggle_tool_usage(tool_schema: dict, use_tool: bool):
    """Toggle the usage of a tool in the model's response generation."""
    if use_tool:
        if tool_schema not in available_tools:
            available_tools.append(tool_schema)
    else:
        available_tools.remove(tool_schema)

def toggle_tool_support(request: gr.Request):
    """Enable or disable the options for choosing tools based on whether the current model supports tool calling."""
    assert request.session_hash is not None

    active_model = manager.get_active_model(request.session_hash)
    if active_model is None:
        return gr.CheckboxGroup(interactive=False, value=None), gr.Radio(interactive=False)
    
    return (
        gr.CheckboxGroup(
            interactive = active_model.supports_tool_calling,
            value = [] if active_model.supports_tool_calling else None
        ),
        gr.Radio(
            interactive = active_model.supports_tool_calling
        )
    )

def update_tool_choice(tool_choice: str, request: gr.Request):
    """Update the tool choice setting for the current session."""
    assert request.session_hash is not None
    manager.update_tool_choice(request.session_hash, tool_choice)

def update_available_tools(available_tools: list[str], request: gr.Request):
    """Update the available tools for the current session."""
    assert request.session_hash is not None
    manager.update_available_tools(request.session_hash, [json.loads(tool) for tool in available_tools])

def enable_new_request_flag(session: SessionContext):
    """Set the new_request flag in the session context to True."""
    session.new_request = True

def main():
    with gr.Blocks(title="Foundry Local Chat") as full_interface:
        session_state = gr.State(SessionContext())

        model_select = gr.Dropdown(
            label="Select Model",
            choices=models,
            interactive=True,
            value=default_model,
        )

        retain_checkbox = gr.Checkbox(
            label="Retain Loaded Models",
            value=session_state.value.retain_loaded_models,
            interactive=True,
        )

        loaded_models_list = gr.Textbox(
            label="Loaded Models",
            value="",
            interactive=False,
        )

        with gr.Row():
            with gr.Column(scale=1, min_width=100):
                new_chat_button = gr.Button(
                    "New chat",
                    variant="primary",
                    size="md",
                    # icon=utils.get_icon_path("plus.svg"),
                    # scale=0,
                )
                chat_history_dataset = gr.Dataset(
                    components=[gr.Textbox(visible=False)],
                    show_label=False,
                    layout="table",
                    type="index",
                )
            with gr.Column(scale=6):
                chatbot = gr.Chatbot(
                    reasoning_tags=[("<think>", "</think>")],
                    )

                chat_input = gr.MultimodalTextbox(
                    interactive=True,
                    submit_btn=True,
                    stop_btn=True,
                    placeholder="Ask anything...",
                )
            with gr.Column(scale=1, min_width=100):
                gr.Markdown("### Tools")

                enabled_tools = gr.CheckboxGroup(
                    label="Enabled Tools",
                    choices=[(tool_schema["name"], json.dumps(tool_schema)) for tool_schema in tool_registry.get_tool_schemas()],
                    interactive=True,
                )

                tool_choice = gr.Radio(
                    label="Tool Choice",
                    choices=["auto", "required", "none"],
                    value="auto",
                    interactive=True,
                )

            model_select.change(
                load_model,
                inputs=[model_select, session_state, retain_checkbox],
                outputs=[loaded_models_list]
            ).then(
                lambda: "",
                inputs=None,
                outputs=[chat_input],
                queue=False
            ).then(
                toggle_tool_support,
                inputs=None,
                outputs=[enabled_tools, tool_choice],
                queue=False
            )

            submit_event = chat_input.submit(
                store_user_input_and_clear,
                inputs=[chat_input, session_state],
                outputs=[chat_input, session_state],
                queue=True,
            ).then(
                enable_new_request_flag,
                inputs=[session_state],
                outputs=None,
                queue=True,
            ).then(
                get_model_response,
                inputs=[chatbot, session_state, enabled_tools],
                outputs=[chatbot],
                queue=True,
            ).then(
                update_current_conversation,
                inputs=[chatbot],
                outputs=None,
                queue=True,
            ).then(
                update_conversation_history,
                inputs = None,
                outputs = [chat_history_dataset],
                queue=True,
            )

            chat_input.stop(
                stop_generation,
                inputs=None,
                outputs=None,
                cancels=[submit_event],
                queue=False
            )

            new_chat_button.click(
                list,
                inputs = None,
                outputs = [chatbot],
                queue=True,
            ).then(
                load_new_conversation,
                inputs = [session_state],
                outputs = [chatbot],
                queue=True,
            ).then(
                update_conversation_history,
                inputs = None,
                outputs = [chat_history_dataset],
                queue=True,
            )

            chat_history_dataset.click(
                lambda: "",
                inputs=None,
                outputs=[chat_input],
                queue=True,
            ).then(
                list,
                inputs = None,
                outputs = [chatbot],
                queue=True,
            ).then(
                load_previous_conversation,
                [chat_history_dataset, session_state],
                [chatbot],
                queue=True,
                show_progress="hidden",
            )

            tool_choice.change(
                update_tool_choice,
                inputs=[tool_choice],
                outputs=None,
                queue=True,
            )

            enabled_tools.change(
                update_available_tools,
                inputs=[enabled_tools],
                outputs=None,
                queue=True,
            )

        full_interface.load(
            initialize_runtime,
            inputs=None,
            outputs=None,
            queue=True,
        ).then(
            load_model,
            inputs=[model_select, session_state, retain_checkbox],
            outputs=[loaded_models_list],
            queue=True,
        ).then(
            toggle_tool_support,
            inputs=None,
            outputs=[enabled_tools, tool_choice],
            queue=False
        ).then(
            update_conversation_history,
            inputs=None,
            outputs=[chat_history_dataset],
            queue=False,
        ).then(
            load_new_conversation,
            inputs=[session_state],
            outputs=[chatbot],
            queue=False,
        )

        full_interface.unload(
            cleanup_runtime,
        )

    full_interface.launch(pwa=True)

if __name__ == "__main__":
    main()