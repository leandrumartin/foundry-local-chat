from collections.abc import Generator

from foundry_local_sdk import (
    ChatSession,
    Configuration,
    FoundryLocalManager,
    MessageItem,
    MessageRole,
    Request,
    TextItem,
)
from foundry_local_sdk.imodel import IModel

role_map = {
    "none": MessageRole.NONE,
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "tool": MessageRole.TOOL,
    "developer": MessageRole.DEVELOPER,
}


class FoundryManager:
    def __init__(self):
        self._current_model_name: str|None = None
        self._active_models: dict[str, IModel] = {}
        self._active_model_names: dict[str, str] = {}
        self._sessions: dict[str, ChatSession] = {}
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

    def load_model(self, model_name: str, session_hash: str, retain: bool = False) -> None:
        """Load a model into memory. If retain is False, unloads all other models except the one being loaded.  """

        if not retain:
            self.unload_all_models(exceptions=[model_name])

        self._current_model_name = model_name
        if model_name not in self.loaded_model_names:
            self.loaded_model_names.append(model_name)
        self._active_models[session_hash] = self.get_loaded_model(model_name)
        self._active_model_names[session_hash] = model_name
        self._sessions[session_hash] = ChatSession(self._active_models[session_hash])

    def get_model_response(self, history: list[dict], session_hash: str) -> Generator[str]:
        """Get a response from the currently loaded model based on user input and conversation history.
        
        Raises:
            ValueError: If no model is currently loaded.
        """

        if self._sessions[session_hash] is None:
            raise ValueError("No model is currently loaded. Please load a model first.")
        
        history = self._cleaned_history(history)

        # Stream the response token by token
        self._sessions[session_hash].set_streaming(True)
        with Request() as request:
            for message in history:
                request.add_item(
                    MessageItem(
                        role=role_map.get(message["role"], MessageRole.NONE),
                        content=message["content"]
                    )
                )

            for item in self._sessions[session_hash].process_streaming_request(request):
                if isinstance(item, TextItem):
                    yield item.text

    def unload_model(self, model_name: str) -> None:
        """Unload a model from memory. If the model is not loaded, does nothing."""

        if model_name in self.loaded_model_names:
            model = self._manager.catalog.get_model(model_name)
            if model is not None:
                model.unload()
            self.loaded_model_names.remove(model_name)
            print(f"Model '{model_name}' unloaded.")

    def unload_all_models(self, exceptions: list[str]|None = None) -> None:
        """Unload all models from memory, except those being used by active sessions and those specified in the exceptions list."""

        unloaded_model_names = []
        for model_name in self.loaded_model_names:
            if exceptions and (model_name in exceptions or model_name in self._active_model_names.values()):
                continue
            self.unload_model(model_name)
            unloaded_model_names.append(model_name)
        for model_name in unloaded_model_names:
            if model_name in self.loaded_model_names:
                self.loaded_model_names.remove(model_name)

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

    def load_new_session(self, session_hash: str) -> None:
        """Create a new chat session for the currently loaded model. Raises an error if no model is loaded."""
        if session_hash not in self._active_models:
            raise ValueError("No model is currently loaded. Please load a model first.")
        self._sessions[session_hash] = ChatSession(self._active_models[session_hash])

    def unload_session(self, session_hash: str) -> None:
        """Unload the chat session for the given session hash. Does not unload the model itself."""
        if session_hash in self._sessions:
            del self._sessions[session_hash]
            del self._active_models[session_hash]
            del self._active_model_names[session_hash]