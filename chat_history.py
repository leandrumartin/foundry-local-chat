import gradio as gr

class ChatHistory:
    def __init__(self):
        self.conversations = []
        self._current_conversation_index = -1

    def _add_conversation(self, conversation):
        self.conversations.append(conversation)
        self._current_conversation_index = len(self.conversations) - 1

    def _get_conversation(self, index):
        if 0 <= index < len(self.conversations):
            return self.conversations[index]
        elif len(self.conversations) == 0:
            new_conversation = []
            self._add_conversation(new_conversation)
            return new_conversation
        else:
            raise IndexError("Conversation index out of range.")

    def _get_all_conversations(self):
        return self.conversations
    
    def _get_conversation_title(self, index):
        conversation = self._get_conversation(index)
        if conversation:
            return f"{conversation[0]['content'][:40]}..."
        else:
            return f"New conversation"
        
    def _update_conversation(self, index, history):
        if 0 <= index < len(self.conversations):
            self.conversations[index] = history
        elif len(self.conversations) == 0:
            self._add_conversation(history)
        else:
            raise IndexError("Conversation index out of range.")
    
    def load_new_conversation(self):
        new_conversation = []
        self._add_conversation(new_conversation)
        return new_conversation, gr.Dataset(
            samples=[
                [self._get_conversation_title(conversation_index)]
                for conversation_index, conversation
                in enumerate(self.conversations)
            ]
        )

    def load_previous_conversation(self, index):
        conversation = self._get_conversation(index)
        self._current_conversation_index = index
        return conversation
    
    def update_current_conversation(self, history):
        self._update_conversation(self._current_conversation_index, history)