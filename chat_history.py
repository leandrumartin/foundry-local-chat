import gradio as gr

class ChatHistory:
    def __init__(self):
        self.conversations = []

    def _add_conversation(self, conversation):
        self.conversations.append(conversation)

    def _get_conversation(self, index):
        if 0 <= index < len(self.conversations):
            return self.conversations[index]
        else:
            raise IndexError("Conversation index out of range.")

    def _get_all_conversations(self):
        return self.conversations
    
    def load_new_conversation(self):
        new_conversation = []
        self._add_conversation(new_conversation)
        return new_conversation, gr.Dataset(
            samples=[[] for conv in self.conversations]
        )

    def load_previous_conversation(self, index):
        conversation = self._get_conversation(index)
        return conversation