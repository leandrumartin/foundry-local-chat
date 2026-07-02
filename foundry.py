from collections.abc import Generator

from foundry_local_sdk import Configuration, FoundryLocalManager
from foundry_local_sdk.imodel import IModel
from foundry_local_sdk.openai import ChatClient

class FoundryManager:
    def __init__(self):
        self._current_model_name: str|None = None
        self._model: IModel|None = None
        self._client: ChatClient|None = None
        self._manager: FoundryLocalManager = self._get_initialized_manager()
        self._loaded_models: list[str] = []

    def _get_initialized_manager(self) -> FoundryLocalManager:
        # Initialize the Foundry Local SDK
        config: Configuration = Configuration(app_name="foundry_local_chat")
        FoundryLocalManager.initialize(config)
        manager: FoundryLocalManager = FoundryLocalManager.instance

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

    def get_loaded_model(self, model_name: str) -> (IModel):
        # Select and load a model from the catalog
        model: IModel|None = self._manager.catalog.get_model(model_name)

        if model is None:
            raise ValueError(f"Model '{model_name}' not found in the catalog.")

        model.download(
            lambda progress: print(
                f"\rDownloading model: {progress:.2f}%", end="", flush=True
            )
        )
        print()
        model.load()
        print(f"Model '{model_name}' loaded and ready.")

        return model

    def load_model(self, model_name: str, retain: bool = False) -> None:
        if not retain:
            self.unload_all_models(exceptions=[model_name])

        self._current_model_name = model_name
        if model_name not in self._loaded_models:
            self._loaded_models.append(model_name)
        self._model = self.get_loaded_model(model_name)
        self._client = self._model.get_chat_client()

    def get_model_response(self, user_input: str, history: list[dict]) -> Generator[str]:
        if self._client is None:
            raise ValueError("No model is currently loaded. Please load a model first.")

        history.append({"role": "user", "content": user_input})
        print("User: ", user_input)

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

    def unload_model(self, model_name: str) -> None:
        if model_name in self._loaded_models:
            model = self._manager.catalog.get_model(model_name)
            if model is not None:
                model.unload()
            self._loaded_models.remove(model_name)
            print(f"Model '{model_name}' unloaded.")

    def unload_all_models(self, exceptions: list[str] = []) -> None:
        for model_name in self._loaded_models:
            if exceptions and model_name in exceptions:
                continue
            self.unload_model(model_name)
        self._loaded_models.clear()

    def get_loaded_models(self) -> list[str]:
        return self._loaded_models