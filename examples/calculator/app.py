from hybridoma import App, expose

app = App(__name__)

@expose
def add(a, b):
    # raise ArithmeticError("Example")
    return a + b

@app.route("/")
async def index():
    return await app.render("index.html")

if __name__ == "__main__":
    app.run(debug=True)