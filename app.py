import gradio as gr
import random
import time
from foundry import FoundryManager
import os

models = ["qwen2.5-0.5b", "qwen2.5-coder-0.5b", "qwen2.5-1.5b", "qwen2.5-7b", "qwen2.5-7b-instruct-qnn-npu:3"]
messages = []

def slow_echo(message, history):
    for i in range(len(message)):
        time.sleep(0.3)
        yield "You typed: " + message[: i+1]

def main():
    print(os.getcwd())

    with gr.Blocks() as full_interface:
        model_select = gr.Dropdown(
            label="Select Model",
            choices=models,
            interactive=True,
        )

        manager = FoundryManager()

        def set_manager(model_name):
            nonlocal manager
            manager.load_model(model_name)

        model_select.change(fn=lambda model_name: set_manager(model_name), inputs=model_select, outputs=None)

        gr.ChatInterface(
            save_history=True,
            fn=manager.get_model_response,
            # flagging_dir="."
        )

    full_interface.launch()

if __name__ == "__main__":
    main()