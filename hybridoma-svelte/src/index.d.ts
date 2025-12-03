// index.d.ts

export interface PortalOptions {
    /**
     * The URL path to the backend WebSocket.
     * Defaults to `/_hy/ws` on the current host.
     * Example: "ws://localhost:8000/_hy/ws"
     */
    url?: string;
}

/**
 * A callback function for events.
 * It receives positional arguments spread out, with the last argument 
 * typically being the keyword arguments object.
 */
export type PortalCallback = (...args: any[]) => void;

/**
 * The Portal interface combines the built-in Event emitter methods
 * with the dynamic RPC proxy capability.
 */
export interface Portal extends EventTarget {
    /** The WebSocket URL being used. */
    url: string;

    /** Manually establish the WebSocket connection. */
    connect(): void;

    /**
     * Register a callback for a server-sent event.
     * @param event The name of the event emitted from Python.
     * @param callback The function to run when data is received.
     */
    on(event: string, callback: PortalCallback): void;

    /**
     * Remove a specific callback for an event.
     * @param event The name of the event.
     * @param callback The function to remove.
     */
    off(event: string, callback: PortalCallback): void;

    /**
     * Register a callback that runs only once.
     * @param event The name of the event.
     * @param callback The function to run.
     */
    once(event: string, callback: PortalCallback): void;

    /**
     * Dynamic RPC methods.
     * Any property not listed above is treated as an RPC call to the Python backend.
     * 
     * Usage: await portal.my_python_function(arg1, arg2)
     */
    [methodName: string]: ((...args: any[]) => Promise<any>) | any;
}

/**
 * Creates a Portal proxy to communicate with the Hybridoma backend.
 * @param options Configuration options.
 */
export function createPortal(options?: PortalOptions): Portal;