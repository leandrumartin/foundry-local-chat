import gradio as gr
from foundry import FoundryManager

models = ["qwen2.5-0.5b", "qwen2.5-coder-0.5b", "qwen2.5-1.5b", "qwen2.5-coder-1.5b", "qwen2.5-7b", "qwen2.5-coder-7b"]
default_model = models[0]
retain_loaded_models = False

def main():
    with gr.Blocks() as full_interface:
        model_select = gr.Dropdown(
            label="Select Model",
            choices=models,
            interactive=True,
            value=default_model,
        )

        manager = FoundryManager()

        def load_model(model_name, retain):
            manager.load_model(model_name, retain)

            loaded_models_list = gr.Textbox(
                label="Loaded Models",
                value=", ".join(manager.get_loaded_models()),
                interactive=False,
            )

            input_textbox = gr.Textbox(
                interactive=True,
                submit_btn=True,
                stop_btn=True,
                placeholder="Ask anything...",
            )

            return loaded_models_list, input_textbox

        retain_checkbox = gr.Checkbox(
            label="Retain Loaded Models",
            value=retain_loaded_models,
            interactive=True,
        )

        loaded_models_list, chat_input = load_model(default_model, retain_loaded_models)
        model_select.change(load_model, inputs=[model_select, retain_checkbox], outputs=[loaded_models_list, chat_input])

        gr.ChatInterface(
            textbox=chat_input,
            save_history=True,
            fn=manager.get_model_response,
        )

    full_interface.launch()

if __name__ == "__main__":
    main()