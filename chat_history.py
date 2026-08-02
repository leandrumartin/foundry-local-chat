import json
import sqlite3

import gradio as gr


class ChatHistory:
    """Manage chat conversations and provide helpers to navigate and display them.
    """

    def __init__(self):
        """Create an empty ChatHistory, initializing the conversations history if it doesn't yet exist.
        """
        self._execute_query(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
                conversation BLOB
            )
            """)
        self._conversation_count = self._execute_query("SELECT COUNT(id) FROM conversations")[0][0]
        self._current_conversation_index = self._conversation_count - 1 if self._conversation_count > 0 else 0

    def _add_conversation(self, conversation: list[dict]) -> None:
        """Add a new conversation and set it as the current one.

        Args:
            conversation: A conversation represented in the format used by Gradio's Chatbot component.
        """
        self._conversation_count += 1
        self._current_conversation_index = self._conversation_count - 1
        self._execute_query(
            """
            INSERT INTO conversations (title, conversation)
            VALUES (?, ?)
            """,
            (self._generate_conversation_title(conversation), json.dumps(conversation))
        )

    def _get_conversation(self, index: int) -> list[dict]:
        """Return the conversation at the given index, or create one if empty.

        Args:
            index: Index of the conversation to retrieve.

        Returns:
            The conversation list at the requested index.

        Raises:
            IndexError: If the index is out of range.
        """
        if 0 <= index < self._conversation_count:
            return json.loads(
                self._execute_query(
                    "SELECT conversation FROM conversations WHERE id = ?",
                    (index + 1,)
                )[0][0]
            )
        elif self._conversation_count == 0:
            new_conversation = []
            self._add_conversation(new_conversation)
            return new_conversation
        else:
            raise IndexError("Conversation index out of range.")

    def _get_all_conversations(self):
        """Return the internal list of all conversations.

        Returns:
            list: The list containing all stored conversations.
        """
        return self._execute_query("SELECT conversation FROM conversations")
    
    def _get_conversation_title(self, index: int) -> str:
        """Get the title of a conversation.

        Args:
            index: Index of the conversation to title.

        Returns:
            A short human-readable title for the conversation.
        """
        title = self._execute_query(
            "SELECT title FROM conversations WHERE id = ?",
            (index + 1,)
        )

        if title:
            return title[0][0]
        else:
            return "New conversation"
        
    def _update_conversation(self, index: int, history: list[dict]) -> None:
        """Replace or add a conversation at the given index.

        If the index refers to an existing conversation, that conversation is replaced with history. If there are no conversations yet, history is added as the first conversation.

        Args:
            index: Target index to update.
            history: The conversation history to store.

        Raises:
            IndexError: If index is out of range for existing conversations.
        """
        if 0 <= index < self._conversation_count:
            self._execute_query(
                """
                UPDATE conversations
                SET title = ?, conversation = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (self._generate_conversation_title(history), json.dumps(history), index + 1)
            )
        elif self._conversation_count == 0:
            self._add_conversation(history)
        else:
            raise IndexError("Conversation index out of range.")
        
    def _generate_conversation_title(self, conversation: list[dict]) -> str:
        """Generate a title for a conversation based on its first message.

        The title is derived from the first message's text (first 40 characters) and ends with an ellipsis if truncated. If the conversation is empty, returns a generic 'New conversation' title.

        Args:
            conversation: The conversation to generate a title for.
        """
        if conversation:
            title = conversation[0]['content'][0]['text'][:40]  # Get the first 40 characters of the first message
            if len(conversation[0]['content'][0]['text']) > 40:
                title += "..."
            return title
        else:
            return "New conversation"
        
    def _execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a SQL query and return the results.

        Args:
            query: The SQL query to execute.
            params: Optional parameters for the SQL query.
        """
        db = sqlite3.connect("chat_history.db")
        cursor = db.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        db.commit()
        db.close()
        return results

    def _correct_index(self, index: int) -> int:
        """Correct the index from the newest conversation being first (as displayed) to it being last (as handled by the database).

        Args:
            index: The index to correct.
        """
        return self._conversation_count - 1 - index if 0 <= index < self._conversation_count else index
    
    def load_new_conversation(self) -> list[dict]:
        """Create and load a new empty conversation.

        Returns:
            The newly created conversation (empty list).
        """
        new_conversation = []
        self._add_conversation(new_conversation)
        return new_conversation

    def load_previous_conversation(self, index: int) -> list[dict]:
        """Load an existing conversation by index, setting it as the current conversation.

        Args:
            index: The index of the conversation to load.

        Returns:
            The conversation at the requested index.
        """
        index = self._correct_index(index)
        conversation = self._get_conversation(index)
        self._current_conversation_index = index
        return conversation
    
    def update_current_conversation(self, history: list[dict]) -> None:
        """Update the currently active conversation with new history.

        Args:
            history: New conversation history to store for the current conversation index. Should be structured as a list of message dictionaries, in the format used by Gradio's Chatbot component.
        """
        self._update_conversation(self._current_conversation_index, history)

    def update_conversation_history(self) -> gr.Dataset:
        """Return a gradio.Dataset representing all conversation titles.

        Each dataset sample contains a single-item list with the conversation title, suitable for display in a Gradio DataFrame or similar UI.

        Returns:
            Dataset with one sample per stored conversation.
        """
        conversation_titles = self._execute_query("SELECT title FROM conversations")

        return gr.Dataset(
            samples=list(reversed(conversation_titles))
        )