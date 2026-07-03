import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { bootstrapToken } from './api/client'

const rootElement = document.getElementById('root')!
rootElement.innerHTML = '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;font:14px system-ui;color:#6b7280;background:#f9fafb">Starter TimeLapse Pro...</div>'

bootstrapToken()
  .catch(err => {
    console.error('Token bootstrap failed', err)
  })
  .finally(() => {
    createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
    )
  })
