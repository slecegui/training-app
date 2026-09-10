import { useEffect, useState } from 'react'

export const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
export const request = (path: string, init?: RequestInit) => fetch(`${api}${path}`, { credentials: 'include', ...init })
export const jsonHeaders = { 'Content-Type': 'application/json' }

export function useLocation() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])
  const navigate = (to: string) => {
    window.history.pushState(null, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }
  return [path, navigate] as const
}

export const duration = (seconds: number | null) => 
  seconds ? `${Math.floor(seconds / 3600)} h ${String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')} min` : '—'

export const distance = (meters: number | null) => 
  meters ? `${(meters / 1000).toFixed(1)} km` : '—'

export const pairs = (value: string) => 
  Object.fromEntries(
    value.split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => {
        const [key, raw] = item.split(':').map((part) => part.trim())
        return [key, Number(raw)]
      })
      .filter(([key, val]) => key && Number.isFinite(val))
  )

export const formatPairs = (value: Record<string, number>) => 
  Object.entries(value).map(([key, item]) => `${key}: ${item}`).join(', ')

export const errorText = async (response: Response) => {
  const body = await response.json().catch(() => null)
  return typeof body?.detail === 'string' ? body.detail : 'La operación no se pudo completar.'
}
