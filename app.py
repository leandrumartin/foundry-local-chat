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
retain_loaded_models = False

manager = FoundryManager()
history_manager = ChatHistory()

transformed_user_input = ""

def load_model(model_name, retain):
    manager.load_model(model_name, retain)

    loaded_models_list = gr.Textbox(
        label="Loaded Models",
        value=", ".join(manager.loaded_model_names),
        interactive=False,
    )

    return loaded_models_list

def get_model_response(history):
    """Get a response from the currently loaded model based on transformed user input and conversation history.
    """
    history.append({"role": "user", "content": transformed_user_input})
    history.append({"role": "assistant", "content": ""})

    for chunk in manager.get_model_response(history):
        history[-1]["content"] += chunk
        yield history

def store_user_input_and_clear(user_input: dict[str, list] | str):
    """Store the user input for later use. In the case of multimodal input, only the text portion is stored.
    Returns an empty string to clear the input field in the UI."""
    if isinstance(user_input, str):
        transformed_input = user_input
    else:
        transformed_input = user_input.get("text", "")

    global transformed_user_input
    transformed_user_input = transformed_input
    return ""

def main():
    with gr.Blocks() as full_interface:
        model_select = gr.Dropdown(
            label="Select Model",
            choices=models,
            interactive=True,
            value=default_model,
        )

        retain_checkbox = gr.Checkbox(
            label="Retain Loaded Models",
            value=retain_loaded_models,
            interactive=True,
        )

        loaded_models_list = load_model(default_model, retain_loaded_models)

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
                outputs=[loaded_models_list, chat_input]
            )
            
            model_select.change(lambda: "", inputs=None, outputs=[chat_input], queue=False)

            chat_input.submit(
                store_user_input_and_clear,
                inputs=[chat_input],
                outputs=[chat_input],
                queue=False,
            ).then(
                get_model_response,
                inputs=[chatbot],
                outputs=[chatbot],
                queue=True,
            ).then(
                history_manager.update_current_conversation,
                inputs=[chatbot],
                outputs=None,
                queue=False,
            ).then(
                history_manager.update_conversation_history,
                inputs = None,
                outputs = [chat_history_dataset],
                queue=False,
            )

            new_chat_button.click(
                lambda: [],
                inputs = None,
                outputs = [chatbot],
                queue=False,
            ).then(
                history_manager.load_new_conversation,
                inputs = None,
                outputs = [chatbot],
                queue=False,
            ).then(
                history_manager.update_conversation_history,
                inputs = None,
                outputs = [chat_history_dataset],
                queue=False,
            )

            # gr.on(
            #     triggers=[saved_conversations.change],
            #     fn=load_chat_history,
            #     inputs=[saved_conversations],
            #     outputs=[chat_history_dataset],
            #     queue=False,
            # )

            chat_history_dataset.click(
                lambda: "",
                inputs=None,
                outputs=[chat_input],
                queue=False,
            ).then(
                lambda: [],
                inputs = None,
                outputs = [chatbot],
                queue=False,
            ).then(
                history_manager.load_previous_conversation,
                [chat_history_dataset],
                [chatbot],
                queue=False,
                show_progress="hidden",
            )

    full_interface.launch()

if __name__ == "__main__":
    main()