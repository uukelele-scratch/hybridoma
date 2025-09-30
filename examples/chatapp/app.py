from hybridoma import App, ViewModel, Model

app = App(__name__)

@app.model
class Message(Model):
    content: str

@app.view_model(template="chat_window.html")
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