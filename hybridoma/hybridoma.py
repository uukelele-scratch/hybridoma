import quart_flask_patch
import asyncio
import quart as q
from functools import wraps, lru_cache
from markupsafe import Markup
import os, re
import json, inspect
import minify_html
import pydantic as p    
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from contextlib import asynccontextmanager

def static_file(name):
    with open(os.path.join(os.path.dirname(__file__), 'static', name)) as file:
        return file.read()

HYBRIDOMA_JS  = static_file('hybridoma.js.txt')
HYBRIDOMA_CSS = static_file('pico.classless.min.css')
MORPHDOM_JS   = static_file('morphdom.min.js.txt')
LUCIDE_JS     = static_file('lucide.min.js.txt')

class HyHelpers:
    def __init__(self, app: "App"):
        self.app: "App" = app

    async def component(self, *args, **kwargs):
        return await self.app._render_component_for_template(*args, **kwargs)
    
    def js(self):
        return self.app._render_js()
    
    def css(self):
        return self.app._render_css()
    
    @lru_cache()
    def icon(self, icon_name: str, height=None, width=None):
        height = height or 24
        if height and not width: width = height
        return Markup(f'<i data-lucide="{icon_name}" style="width:{width}px; height:{height}px;"></i>')

class HyDB(SQLAlchemy):
    def __init__(self, *args, **kwargs):
        kwargs['session_options'] = {
            'scopefunc': lambda: asyncio.current_task() if asyncio.get_running_loop() else None
        }
        super().__init__(*args, **kwargs)

    def transaction(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await self._app.ensure_async(func)(*args, **kwargs)
                await self._app.ensure_async(self.session.commit)()
                return result
            except Exception as e:
                await self._app.ensure_async(self.session.rollback)()
                raise e
        return wrapper

db = HyDB()

class App(q.Quart):
    def __init__(self, import_name, db_path=None, **kwargs):
        super().__init__(import_name, **kwargs)
        self._view_models = {}
        self._models = []

        if db_path:
            self._init_db(db_path)

        self._register_hy_routes()

        self._hy = HyHelpers(self)

        @self.context_processor
        def helpers():
            return dict(
                hy=self._hy,
            )
        
        self._original_ensure_async = self.ensure_async

        def smart_ensure_async(func):
            if inspect.iscoroutinefunction(func):
                return func
            else:
                return self._original_ensure_async(func)

        self.ensure_async = smart_ensure_async

    def _init_db(self, db_path):
        self.config['SQLALCHEMY_DATABASE_URI'] = db_path
        db.init_app(self)
        db._app = self

        # async with self.app_context():
            # og_query = db.Model.query
            # db.Model.query = property(lambda m_inst: AsyncObjectProxy(self, og_query))
            # db.session = AsyncObjectProxy(self, db.session)

    def model(self, cls):
        self._models.append(cls)
        return cls

    def view_model(self, template):
        def decorator(cls):
            self._view_models[cls.__name__] = {"class": cls, "template": template}
            @wraps(cls)
            def wrapper(*args, **kwargs):
                return cls(*args, **kwargs)
            return wrapper
        return decorator

    async def render(self, template, **ctx):
        html = await q.render_template(template, **ctx)
        script = str(self._hy.js())
        
        html, subs_made = re.subn(
            r'(?i)</\s*body\s*>',
            f'{script}\\g<0>',
            html,
            count=1,
        )

        if subs_made == 0:
            html += script

        if not self.debug:
            html = minify_html.minify(html, minify_css=True, minify_js=True)

        return Markup(html)

    async def _render_component_for_template(self, view_model, _instance=None, _hy_id=None):
        vm_class = None
        vm_name = None

        if isinstance(view_model, str):
            vm_name = view_model
            if vm_name not in self._view_models:
                raise NameError(f"ViewModel '{vm_name}' is not registered with @app.view_model")
            vm_class = self._view_models[vm_name]['class']
        else:
            vm_class = view_model
            vm_name = vm_class.__name__

        vm_info = self._view_models[vm_name]
        template_path = vm_info['template']

        if _instance:
            vm_instance: ViewModel = _instance
        else:
            vm_instance: ViewModel = vm_class()
            if hasattr(vm_instance, 'mount'):
                await self.ensure_async(vm_instance.mount)()

        if not _hy_id:
            _hy_id = f"hy-{vm_name.lower()}-{os.urandom(4).hex()}"

        ctx = vm_instance.get_state()

        ctx['hy_id'] = _hy_id

        html = await q.render_template(template_path, **ctx)
        wrapper = f'<div id="{ctx["hy_id"]}" hy-vm="{vm_name}">{html}</div>'
        return Markup(wrapper)

    def _register_hy_routes(self):
        @self.route('/_hy/hy.js')
        def serve_js():
            return HYBRIDOMA_JS.replace("$DEBUG", '1' if self.debug else '0', 1), 200, {'Content-Type': 'application/javascript'}

        @self.route('/_hy/morphdom.js')
        def serve_morphdom():
            return MORPHDOM_JS, 200, {'Content-Type': 'application/javascript'}
        
        @self.route('/_hy/lucide.js')
        def serve_lucide():
            return LUCIDE_JS, 200, {'Content-Type': 'application/javascript'}

        @self.route('/_hy/hy.css')
        def serve_css():
            return HYBRIDOMA_CSS, 200, {'Content-Type': 'text/css'}

        @self.websocket('/_hy/ws')
        async def websocket():
            ws = q.websocket
            vm_instances = {}
            print("[ws] client connected.")
            try:
                init_data = await ws.receive_json() 
                if init_data.get('type') == 'init':
                    components = init_data.get('components', [])
                    for comp_info in components:
                        vm_name = comp_info.get('vm_name')
                        hy_id = comp_info.get('hy_id')

                        if vm_name in self._view_models:
                            vm_class = self._view_models[vm_name]['class']
                            vm_instance = vm_class()
                            if hasattr(vm_instance, 'mount'):
                                await self.ensure_async(vm_instance.mount)()

                            vm_instances[hy_id] = vm_instance
                            print(f"[ws] Initialized VM '{vm_name}' for component '{hy_id}'.")           
            
                while True:
                    data = await ws.receive_json()

                    print(f"[ws] Received: {data}")

                    hy_id = data.get('hy_id')
                    vm_instance = vm_instances.get(hy_id)

                    if not vm_instance:
                        print(f"[ws] Received action for unknown component ID: {hy_id}")
                        continue

                    action_name: str = data.get('name')
                    args = data.get('args', [])

                    action_method = getattr(vm_instance, action_name, None)
                    if callable(action_method):
                        await self.ensure_async(action_method)(*args)
                        vm_name = vm_instance.__class__.__name__
                        html = await self._render_component_for_template(
                            vm_name,
                            _instance = vm_instance,
                            _hy_id = hy_id,
                        )
                        await ws.send_json({ 'type': 'update', 'html': str(html), 'id': hy_id })
                    else:
                        msg = f"[ws] [!] Could not find action {action_name} on {vm_class} ({action_method})."
                        if action_name.endswith("()"): msg += f" Perhaps you meant: {action_name.removesuffix('()')}"
                        print(msg)
            except asyncio.CancelledError:
                print("[ws] client disconnected.")

    def _render_js(self):
        return Markup(
            '<script src="/_hy/lucide.js"></script>'
            '<script src="/_hy/morphdom.js"></script>'
            '<script src="/_hy/hy.js" type="module" defer></script>'
        )

    def _render_css(self):
        return Markup('<link rel="stylesheet" href="/_hy/hy.css">')
    
    def run(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        shutdown_event = asyncio.Event()

        def _signal_handler(*_, **__):
            shutdown_event.set()

            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
        
        import signal
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)

        kwargs['shutdown_trigger'] = shutdown_event.wait
        server_task = asyncio.ensure_future(
            self.run_task(*args, **kwargs)
        )

        try:
            loop.run_until_complete(server_task)
        except asyncio.CancelledError:
            pass
        finally:
            loop.remove_signal_handler(signal.SIGINT)
            loop.remove_signal_handler(signal.SIGTERM)


class Model(p.BaseModel): ...

class ViewModel():
    def get_state(self): return {k: v for k, v in self.__dict__.items() if not k.startswith('_') and not callable(v)}
    def mount(self): ...