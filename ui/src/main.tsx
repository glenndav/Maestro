import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Mobile browsers require persistent notifications from a service worker;
// `new Notification()` is desktop-only on several engines, including iOS
// WebKit. This worker deliberately does not cache application assets, so a
// Maestro update can never strand users on an old UI bundle.
if ('serviceWorker' in navigator) {
  void navigator.serviceWorker.register('/maestro-sw.js', { scope: '/' }).catch(error => {
    console.warn('[Notifications] Service worker registration failed:', error)
  })
}

// A tab opened before an update (or before another Maestro install took over
// this port) still names the previous build's lazily loaded screens, which
// are gone from disk. Reload once to pick up the current build instead of
// failing to a black screen; a second failure within a minute is a real
// error and is left to surface.
const STALE_BUILD_RELOAD_KEY = 'maestro:stale-build-reload'
window.addEventListener('vite:preloadError', event => {
  let lastReload = 0
  try {
    lastReload = Number(sessionStorage.getItem(STALE_BUILD_RELOAD_KEY)) || 0
  } catch {
    return
  }
  if (Date.now() - lastReload < 60_000) return
  try {
    sessionStorage.setItem(STALE_BUILD_RELOAD_KEY, String(Date.now()))
  } catch {
    return
  }
  event.preventDefault()
  window.location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
