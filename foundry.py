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
        self.loaded_model_names: list[str] = []

    def _get_initialized_manager(self) -> FoundryLocalManager:
        """Initialize the FoundryLocalManager with the application configuration. Load all execution providers, print
        the progress, and return the initialized manager.
        """

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
        """Get a model from the catalog, downloads it if necessary, and loads it into memory. Return the loaded model
        instance.
        
        Raises:
            ValueError: If the model is not found in the catalog.
        """

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
        """Load a model into memory. If retain is False, unloads all other models except the one being loaded.  """

        if not retain:
            self.unload_all_models(exceptions=[model_name])

        self._current_model_name = model_name
        if model_name not in self.loaded_model_names:
            self.loaded_model_names.append(model_name)
        self._model = self.get_loaded_model(model_name)
        self._client = self._model.get_chat_client()

    def get_model_response(self, history: list[dict]) -> Generator[str]:
        """Get a response from the currently loaded model based on user input and conversation history.
        
        Raises:
            ValueError: If no model is currently loaded.
        """

        if self._client is None:
            raise ValueError("No model is currently loaded. Please load a model first.")
        
        history = self._cleaned_history(history)

        # Stream the response token by token
        full_response = ""
        for chunk in self._client.complete_streaming_chat(history):
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
            yield full_response

    def unload_model(self, model_name: str) -> None:
        """Unload a model from memory. If the model is not loaded, does nothing."""

        if model_name in self.loaded_model_names:
            model = self._manager.catalog.get_model(model_name)
            if model is not None:
                model.unload()
            self.loaded_model_names.remove(model_name)
            print(f"Model '{model_name}' unloaded.")

    def unload_all_models(self, exceptions: list[str] = []) -> None:
        """Unload all models from memory, except those specified in the exceptions list."""

        for model_name in self.loaded_model_names:
            if exceptions and model_name in exceptions:
                continue
            self.unload_model(model_name)
        self.loaded_model_names.clear()

    def _cleaned_history(self, history: list[dict]) -> list[dict[str, str]]:
        """Clean the conversation history by replacing the 'content' fields containing dictionaries with their 'text'
        values. This ensures that the history is in the correct format for the model to process."""

        cleaned_history = []
        for entry in history:
            if isinstance(entry.get("content"), str):
                cleaned_entry = entry
            else:
                # Other possible format is list[dict], i.e. [{"type": "text", "text": "some text"}]
                text_content = entry["content"][0].get("text", "")
                cleaned_entry = {
                    "role": entry.get("role", ""),
                    "content": text_content
                }
            cleaned_history.append(cleaned_entry)

        return cleaned_history