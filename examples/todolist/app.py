import sys, os, subprocess as sp

try:
    import hybridoma
except (ImportError, ModuleNotFoundError):
    hybridoma_path = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, "hybridoma")
    sp.run([sys.executable, "-m", "pip", "install", "-e", hybridoma_path, "--trusted-host", "pypi.org", "--trusted-host", "files.pythonhosted.org", "--break-system-packages"])

from hybridoma import App, ViewModel, Model
from sqlalchemy import select, Column, Integer, String, Boolean

app = App(__name__, db_path='sqlite+aiosqlite:///todos.db')

@app.model
class Todo(Model):
    __tablename__ = 'todos'
    id = Column(Integer, primary_key=True)
    text = Column(String(120), nullable=False)
    done = Column(Boolean, default=False)

@app.before_serving
async def setup_database():
    await app.db.create_all()

@app.view_model(template="todo_list.html")
class TodoList(ViewModel):
    todos: list[Todo] = []
    new_todo_text: str = ""

    @app.db.transaction
    async def mount(self, session):
        """Called when the component is first loaded. Fetches initial state."""
        self.todos = Todo.query.all()

    @app.db.transaction
    async def add_todo(self, session, payload: dict):
        """Adds a new todo to the database and updates the UI."""
        self.new_todo_text = payload.get('new_todo_text', '').strip()
        if not self.new_todo_text:
            return # No empty todos allowed

        todo = Todo(text=self.new_todo_text)
        session.add(todo)

        self.todos.append(todo) # Update our local state
        self.new_todo_text = "" # Clear the input box

    @app.db.transaction
    async def toggle_todo(self, session, todo_id: int):
        """Flips the 'done' status of a todo."""
        todo = Todo.query.get(todo_id)
        if todo:
            todo.done = not todo.done

    @app.db.transaction
    async def delete_todo(self, session, todo_id: int):
        """Deletes a todo."""
        todo = Todo.query.get(todo_id)
        if todo:
            session.delete(todo)
            self.todos = [t for t in self.todos if t.id != todo_id]

@app.route('/')
async def index():
    return await app.render("index.html")

if __name__ == "__main__":
    app.run(debug=True)