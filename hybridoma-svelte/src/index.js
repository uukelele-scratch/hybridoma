import { encode, decode } from "@msgpack/msgpack";

class PortalBase extends EventTarget {
    constructor(options = {}) {
        super();
        this.url = this._getDefaultURL(options.url);
        this.ws = null;
        this.callId = 0;
        this.pendingCalls = new Map();
        this._emitter = new Map();

        this.connect();
    }

    _getDefaultURL(url) {
        if (url && /^(ws|wss|http|https):\/\//.test(url)) {
            return url;
        }

        if (url) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;

            const clean = url.startsWith('/') ? url : '/' + url;

            return `${protocol}//${host}${clean}`;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/_hy/ws`;
    }

    connect() {
        this.ws = new WebSocket(this.url);
        this.ws.binaryType = "arrayBuffer";

        this.ws.onopen = () => {
            // console.log ?
            this.ws.send(encode({ type: 'init', components: [] }));
            this.dispatchEvent(new CustomEvent('connected'));
        }

        this.ws.onmessage = event => {
            const data = decode(event.data);

            if (data.id && ('result' in data || 'error' in data)) {
                if (this.pendingCalls.has(data.id)) {
                    const { resolve, reject } = this.pendingCalls.get(data.id);
                    if (data.error) reject(new Error(data.error));
                    else resolve(data.result);
                    this.pendingCalls.delete(data.id);
                }
            } else if (data.type === 'event') {
                const { args = [], kwargs = {} } = data.payload || {};
                this.dispatchEvent(new CustomEvent(data.name, { detail: { args, kwargs} }))
                this._emit(data.name, args, kwargs);
            }
        }

        this.ws.onclose = () => {
            setTimeout(() => this.connect(), 3000);
        }
    };

    on(name, cb) {
        if (!this._emitter.has(name)) this._emitter.set(name, new Set());
        this._emitter.get(name).add(cb);
    }

    off(name, cb) {
        if (!this._emitter.has(name)) return;
        const s = this._emitter.get(name);
        s.delete(cb);
        if (!s.size) this._emitter.delete(name);
    }

    once(name, cb) {
        const wrapper = (...args) => { this.off(name, wrapper); cb(...args); };
        this.on(name,  wrapper);
    }

    _emit(name, args=[], kwargs={}) {
        if (this._emitter.has(name)) {
            for (const cb of Array.from(this._emitter.get(name))) {
                try { cb(...args, kwargs); } catch(e) { console.error(e); }
            }
        }
    }
}

export function createPortal(options = {}) {
    const instance = new PortalBase(options);
    const proxy = new Proxy(instance, {
        get(target, prop) {
            if (prop in target) return target[prop];

            return async(...args) => {
                return new Promise((resolve, reject) => {
                    const id = ++target.callId;
                    target.pendingCalls.set(id, { resolve, reject });
                    target.ws.send(encode({ type: 'rpc', id, name: prop, args }));
                });
            };
        }
    });

    return proxy;
}

// export const portal = createPortal();
// decided not to add this as it would cause confusion