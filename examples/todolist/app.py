import sys, os, subprocess as sp

try:
    import hybridoma
except (ImportError, ModuleNotFoundError):
    hybridoma_path = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, "hybridoma")
    sp.run([sys.executable, "-m", "pip", "install", "-e", hybridoma_path, "--trusted-host", "pypi.org", "--trusted-host", "files.pythonhosted.org", "--break-system-packages"])

from hybridoma import App, ViewModel, db, view_model

app = App(__name__, db_path='sqlite:///todos.db')

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(120), nullable=False)
    done = db.Column(db.Boolean, default=False)

@app.before_serving
async def setup_database():
    async with app.app_context():
        app.ensure_async(db.create_all)

@view_model(template="todo_list.html")
class TodoList(ViewModel):
    todos: list[Todo] = []

    @db.transaction
    async def mount(self):
        """Called when the component is first loaded. Fetches initial state."""
        self.todos = Todo.query.all()

    @db.transaction
    async def add_todo(self, payload: dict):
        """Adds a new todo to the database and updates the UI."""
        text = payload.get('new_todo_text', '').strip()
        if not text:
            return # No empty todos allowed

        todo = Todo(text=text)
        db.session.add(todo)

        self.todos.append(todo)

    @db.transaction
    async def toggle_todo(self, todo_id: int):
        """Flips the 'done' status of a todo."""
        todo = Todo.query.get(todo_id)
        if todo:
            todo.done = not todo.done

    @db.transaction
    async def delete_todo(self, todo_id: int):
        """Deletes a todo."""
        todo = Todo.query.get(todo_id)
        if todo:
            db.session.delete(todo)
            self.todos = [t for t in self.todos if t.id != todo_id]

@app.route('/')
async def index():
    return await app.render("index.html")

if __name__ == "__main__":
    app.run(debug=True)