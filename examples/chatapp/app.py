from hybridoma import App, ViewModel

app = App(__name__)

@app.model
class Message:
    content: str

@app.view_model(template="chat_window.html")
class ChatWindow(ViewModel):
    messages: list[Message] = []

    def __init__(self):
        self.messages = []

    async def add_message(self, payload: dict):
        message_text = payload["text"]
        message = Message()
        message.content = message_text
        self.messages.append(message)
        print(f"New Message: {message_text}")
        print(self.messages)

@app.route("/")
async def index():
    return await app.render("index.html")

if __name__ == "__main__":
    app.run(debug=True)