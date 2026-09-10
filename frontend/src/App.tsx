import { FormEvent, useEffect, useState } from 'react'
import { User } from './types'
import { request, jsonHeaders, errorText, useLocation } from './utils'
import { Input } from './components/Common'
import { Sidebar } from './components/Sidebar'
import { ObjectivesPage } from './pages/ObjectivesPage'
import { ObjectiveDetailPage } from './pages/ObjectiveDetailPage'
import { ActivitiesPage } from './pages/ActivitiesPage'
import { ProfilePage } from './pages/ProfilePage'
import { GoalForm } from './components/GoalForm'
import { HomePage } from './pages/HomePage'
import './styles.css'

export function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [message, setMessage] = useState('')
  const [path, navigate] = useLocation()
  const logout = async () => {
    const response = await request('/auth/logout', { method: 'POST' })
    if (!response.ok) return setMessage(await errorText(response))
    setUser(null); setMessage(''); navigate('/')
  }

  // Fetch session on startup
  useEffect(() => {
    void request('/auth/session')
      .then(async (response) => {
        if (response.ok) {
          setUser(await response.json())
        }
      })
      .finally(() => setChecking(false))
  }, [])

  // Redirect to objectives page on login/startup if at root
  useEffect(() => {
    if (user && (path === '/' || path === '/index.html')) {
      navigate('/home')
    }
  }, [user, path, navigate])

  if (checking) {
    return <main className="auth-shell">Comprobando sesión…</main>
  }

  if (!user) {
    return <Auth onAuthenticated={setUser} message={message} setMessage={setMessage} />
  }

  // Handle routing matching
  const renderContent = () => {
    if (path === '/home') return <HomePage user={user} />
    if (path === '/objectives') {
      return <ObjectivesPage setMessage={setMessage} />
    }
    if (path === '/objectives/new') {
      return (
        <section className="panel">
          <h2>🎯 Crear Nuevo Objetivo Estructurado</h2>
          <p className="subtitle" style={{ marginBottom: '1.5rem' }}>Configura los datos del reto y el método de éxito esperado.</p>
          <GoalForm
            onSuccess={() => navigate('/objectives')}
            onCancel={() => navigate('/objectives')}
            setMessage={setMessage}
          />
        </section>
      )
    }
    if (path.startsWith('/objectives/')) {
      const parts = path.split('/')
      const goalId = parts[2]
      if (goalId) {
        return <ObjectiveDetailPage goalId={goalId} setMessage={setMessage} />
      }
    }
    if (path === '/activities') {
      return <ActivitiesPage setMessage={setMessage} />
    }
    if (path === '/profile') {
      return <ProfilePage setMessage={setMessage} />
    }

    // Default Fallback
    return <ObjectivesPage setMessage={setMessage} />
  }

  return (
    <div className="main-layout">
      {/* 1. Sidebar Left */}
      <Sidebar userName={user.name} />

      {/* 2. Central Content Area */}
      <main className="app-container">
        <header className="topbar"><div className="topbar-context">Planificador ciclista</div><div className="topbar-user"><span className="avatar small">{user.name.slice(0, 1).toUpperCase()}</span><button className="secondary" type="button" onClick={() => void logout()}>Cerrar sesión</button></div></header>
        {message && (
          <div className="message" style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{message}</span>
            <button
              type="button"
              style={{ border: 'none', background: 'none', fontWeight: 'bold', cursor: 'pointer', fontSize: '1rem', color: '#17251e' }}
              onClick={() => setMessage('')}
            >
              ✕
            </button>
          </div>
        )}
        {renderContent()}
      </main>
    </div>
  )
}

function Auth({ onAuthenticated, message, setMessage }: { onAuthenticated: (user: User) => void; message: string; setMessage: (value: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    const response = await request(`/auth/${mode}`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(data)
    })
    if (!response.ok) {
      return setMessage(await errorText(response))
    }
    onAuthenticated(await response.json())
    setMessage('')
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">TRAINING ONLINE</p>
        <h1>Entrena con dirección.</h1>
        <p className="subtitle">Tu perfil, objetivos y actividades en un espacio privado centrado en metas.</p>
        <form onSubmit={submit}>
          {mode === 'register' && <Input name="name" label="Nombre" minLength={2} required />}
          <Input name="email" label="Email" type="email" required />
          <Input name="password" label="Contraseña" type="password" minLength={10} required />
          <button className="primary" type="submit">
            {mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}
          </button>
        </form>
        {message && <p className="message error" style={{ marginTop: '1rem' }}>{message}</p>}
        <button
          className="link-button"
          type="button"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage('') }}
        >
          {mode === 'login' ? 'Crear una cuenta' : 'Ya tengo una cuenta'}
        </button>
      </section>
    </main>
  )
}
