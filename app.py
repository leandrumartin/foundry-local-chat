import threading
from dataclasses import dataclass, field

import gradio as gr

from chat_history import ChatHistory
from foundry import FoundryManager

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
    if request.session_hash in runtime_store:
        del runtime_store[request.session_hash]

def get_runtime(request: gr.Request):
    """Get the runtime context for the current session."""
    if request.session_hash not in runtime_store:
        initialize_runtime(request)
    return runtime_store[request.session_hash]

def load_model(model_name: str, retain: bool = False):
    """Load a model into memory. If retain is False, unloads all other models except the one being loaded."""
    manager.load_model(model_name, retain)

    loaded_models_list = gr.Textbox(
        label="Loaded Models",
        value=", ".join(manager.loaded_model_names),
        interactive=False,
    )

    return loaded_models_list

def get_model_response(history, session: SessionContext, request: gr.Request):
    """Get a response from the currently loaded model based on transformed user input and conversation history.
    """
    runtime = get_runtime(request)
    runtime.stop_event.clear()

    history.append({"role": "user", "content": session.pending_user_input})
    yield history

    history.append({"role": "assistant", "content": ""})

    for chunk in manager.get_model_response(history):
        if runtime.stop_event.is_set():
            break
        history[-1]["content"] += chunk
        yield history

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

def load_new_conversation(request: gr.Request):
    """Load a new conversation in the UI."""
    runtime = get_runtime(request)
    return runtime.history_manager.load_new_conversation()

def load_previous_conversation(index: int, request: gr.Request):
    """Load a previous conversation from the history in the UI."""
    runtime = get_runtime(request)
    return runtime.history_manager.load_previous_conversation(index)

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

        loaded_models_list = load_model(default_model)

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

            model_select.change(
                load_model,
                inputs=[model_select, retain_checkbox],
                outputs=[loaded_models_list]
            ).then(
                lambda: "",
                inputs=None,
                outputs=[chat_input],
                queue=False
            )

            submit_event = chat_input.submit(
                store_user_input_and_clear,
                inputs=[chat_input, session_state],
                outputs=[chat_input, session_state],
                queue=True,
            ).then(
                get_model_response,
                inputs=[chatbot, session_state],
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
                inputs = None,
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
                [chat_history_dataset],
                [chatbot],
                queue=True,
                show_progress="hidden",
            )

        full_interface.load(
            initialize_runtime,
            inputs=None,
            outputs=None,
            queue=True,
        ).then(
            update_conversation_history,
            inputs=None,
            outputs=[chat_history_dataset],
            queue=False,
        ).then(
            load_new_conversation,
            inputs=None,
            outputs=[chatbot],
            queue=False,
        )

        full_interface.unload(
            cleanup_runtime,
        )

    full_interface.launch(pwa=True)

if __name__ == "__main__":
    main()