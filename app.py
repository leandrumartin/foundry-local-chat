import gradio as gr
from foundry import FoundryManager

models = ["qwen2.5-0.5b", "qwen2.5-coder-0.5b", "qwen2.5-1.5b", "qwen2.5-coder-1.5b", "qwen2.5-7b", "qwen2.5-coder-7b"]

def main():
    with gr.Blocks() as full_interface:
        chat_input = gr.Textbox(
            interactive=False,
        )

        model_select = gr.Dropdown(
            label="Select Model",
            choices=models,
            interactive=True,
        )

        manager = FoundryManager()

        def load_model(model_name):
            manager.load_model(model_name)
            return gr.Textbox(
                interactive=True,
                submit_btn=True,
            )

        model_select.change(load_model, inputs=model_select, outputs=chat_input)

        gr.ChatInterface(
            textbox=chat_input,
            save_history=True,
            fn=manager.get_model_response,
        )

    full_interface.launch()

if __name__ == "__main__":
    main()