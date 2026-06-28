from foundry_local_sdk import Configuration, FoundryLocalManager

class FoundryManager:
    def __init__(self):
        self._model = None
        self._client = None
        self._manager = self._initialize_manager()
        self._history = [
            {
                "role": "system",
                "content": "You are a helpful, friendly assistant. Keep your responses "
                           "concise and conversational. If you don't know something, say so.",
            }
        ]

    def _initialize_manager(self):
        # Initialize the Foundry Local SDK
        config = Configuration(app_name="foundry_local_samples")
        FoundryLocalManager.initialize(config)
        manager = FoundryLocalManager.instance

        # Download and register all execution providers.
        current_ep = ""

        def ep_progress(ep_name: str, percent: float):
            nonlocal current_ep
            if ep_name != current_ep:
                if current_ep:
                    print()
                current_ep = ep_name
            print(f"\r  {ep_name:<30}  {percent:5.1f}%", end="", flush=True)

        manager.download_and_register_eps(progress_callback=ep_progress)
        if current_ep:
            print()

        return manager

    def get_loaded_model(self, model_name):
        # Select and load a model from the catalog
        model = self._manager.catalog.get_model(model_name)
        model.download(
            lambda progress: print(
                f"\rDownloading model: {progress:.2f}%", end="", flush=True
            )
        )
        print()
        model.load()
        print("Model loaded and ready.")

        return model

    def load_model(self, model_name):
        if self._model is not None:
            self._model.unload()
            print("Model unloaded.")

        self._model = self.get_loaded_model(model_name)
        self._client = self._model.get_chat_client()

    def get_model_response(self, user_input, history):
        history.append({"role": "user", "content": user_input})

        # Stream the response token by token
        print("Assistant: ", end="", flush=True)
        full_response = ""
        for chunk in self._client.complete_streaming_chat(history):
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                full_response += content
            yield full_response
        print("\n")
