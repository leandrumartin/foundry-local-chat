# Foundry Local Chat

Simple Gradio-based chat UI for Microsoft Foundry Local models. The app lets you pick a local model, load it through the Foundry Local SDK, and chat with it in a browser.

## Requirements

- Python installed
- A file called `models.txt` listing one or more model names, each on one line. The first option in the list will be the default one loaded when the app starts up. You can select models at <https://www.foundrylocal.ai/models>.

## Install

1. Optionally create and activate a virtual environment.
    - On Windows:

        ```powershell
        python -m venv .venv
        .venv\Scripts\activeate
        ```

    - On macOS and Linux:

        ```bash
        python -m venv .venv
        source .venv/bin/activate
        ```

2. Install dependencies.
    - On Windows:

        ```powershell
        pip install -r requirements_windows.txt
        ```

        This installs the Windowss-specific version of the Foundry Local SDK, which integrates with the Windows ML platform.
    - On macOS and Linux:

        ```bash
        pip install -r requirements.txt
        ```

## Run

Start the app with:

```bash
python app.py
```

Gradio will start a local web server and provide a URL you can use to open the chat UI in your browser.

## Linting

Ruff is the preferred linter for the repository. See the documentation at <https://docs.astral.sh/ruff/> for support.

## Notes

- The first time you run the app, Foundry Local may need to download execution providers and model files.
- If `models.txt` is missing, the app falls back to `qwen2.5-0.5b` (the smallest and lightest model in the catalog, good for testing).

## Planned Features

- Better management for loading and unloading models
- Support for attached files (Foundry Local does not support image recognition models, but support is planned for attaching text-based files and audio files for use with transcription models)
- Filter and select models by fields such as number of parameters, tool support, reasoning support, and context length
- MCP tool support
- Incorporate embedding models to index and select relevant files for a query
