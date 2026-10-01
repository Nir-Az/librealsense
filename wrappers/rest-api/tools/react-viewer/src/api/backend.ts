// Tauri v1 sets window.__TAURI__ only with withGlobalTauri; __TAURI_IPC__ is always injected.
export const isDesktopApp =
  typeof window !== 'undefined' && ('__TAURI__' in window || '__TAURI_IPC__' in window)

// The desktop app starts the backend on 127.0.0.1:8000 (src-tauri/src/main.rs).
// Its page origin is tauri.localhost, so the backend must be addressed explicitly.
export const DESKTOP_BACKEND_URL = 'http://127.0.0.1:8000'
