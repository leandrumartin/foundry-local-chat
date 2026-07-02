import gradio as gr
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

def load_model(model_name, retain):
    manager.load_model(model_name, retain)

    loaded_models_list = gr.Textbox(
        label="Loaded Models",
        value=", ".join(manager.loaded_model_names),
        interactive=False,
    )

    input_textbox = gr.MultimodalTextbox(
        interactive=True,
        submit_btn=True,
        stop_btn=True,
        placeholder="Ask anything...",
    )

    return loaded_models_list, input_textbox

def get_model_response(user_input: dict[str, list] | str, history):
    if isinstance(user_input, str):
        transformed_input = user_input
    else:
        transformed_input = user_input.get("text", "")

    transformed_input = {
        "role": "user",
        "content": transformed_input
    }

    history.append(transformed_input)

    yield from manager.get_model_response(history)

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

        loaded_models_list, chat_input = load_model(default_model, retain_loaded_models)
        model_select.change(load_model, inputs=[model_select, retain_checkbox], outputs=[loaded_models_list, chat_input])

        chatbot = gr.Chatbot(
            reasoning_tags=[("<think>", "</think>")],
        )

        gr.ChatInterface(
            chatbot=chatbot,
            textbox=chat_input,
            save_history=True,
            fn=get_model_response,
        )

    full_interface.launch()

if __name__ == "__main__":
    main()