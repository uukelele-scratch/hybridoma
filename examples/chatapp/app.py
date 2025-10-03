from hybridoma import App, ViewModel, view_model
from pydantic import BaseModel

app = App(__name__)

class Message(BaseModel):
    content: str

@view_model(template="chat_window.html")
class ChatWindow(ViewModel):
    messages: list[Message] = []

    def __init__(self):
        self.messages = []

    async def add_message(self, payload: dict):
        message_text = payload["text"]
        self.messages.append(Message(content=message_text))

@app.route("/")
async def index():
    return await app.render("index.html")

if __name__ == "__main__":
    app.run(debug=True)