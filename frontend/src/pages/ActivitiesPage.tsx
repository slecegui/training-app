import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Activity, Goal } from '../types'
import { request, duration, distance, errorText, jsonHeaders } from '../utils'
import { Metric } from '../components/Common'

interface ActivitiesPageProps {
  setMessage: (value: string) => void
}

interface GarminStatus {
  available: boolean
  connected: boolean
  last_sync_at: string | null
  last_error: string | null
  experimental: boolean
}

export function ActivitiesPage({ setMessage }: ActivitiesPageProps) {
  const [activities, setActivities] = useState<Activity[]>([])
  const [goals, setGoals] = useState<Goal[]>([])
  const [selected, setSelected] = useState<Activity | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [garmin, setGarmin] = useState<GarminStatus | null>(null)
  const [garminEmail, setGarminEmail] = useState('')
  const [garminPassword, setGarminPassword] = useState('')
  const [garminCode, setGarminCode] = useState('')
  const [needsMfa, setNeedsMfa] = useState(false)
  const [garminBusy, setGarminBusy] = useState(false)
  const autoSyncAttempted = useRef(false)

  const loadGarminStatus = useCallback(async () => {
    try {
      const response = await request('/integrations/garmin/status')
      if (response.ok) setGarmin(await response.json())
    } catch { setGarmin(null) }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadGarminStatus() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadGarminStatus])

  const syncGarmin = useCallback(async (automatic = false) => {
    setGarminBusy(true)
    try {
      const response = await request('/integrations/garmin/sync', { method: 'POST' })
      if (!response.ok) {
        setMessage(await errorText(response))
        return
      }
      const result: { imported: number; skipped: number; failed: number } = await response.json()
      if (result.imported || result.failed || !automatic) {
        setMessage(`Garmin: ${result.imported} nuevas, ${result.skipped} ya importadas, ${result.failed} con error.`)
      }
      setRefresh(value => value + 1)
      await loadGarminStatus()
    } catch {
      setMessage('No se pudo contactar con Garmin. Puedes seguir importando archivos manualmente.')
    } finally {
      setGarminBusy(false)
    }
  }, [loadGarminStatus, setMessage])

  useEffect(() => {
    if (!garmin?.available || !garmin.connected || autoSyncAttempted.current) return
    const lastSync = garmin.last_sync_at ? new Date(garmin.last_sync_at).getTime() : 0
    if (!lastSync || Date.now() - lastSync > 24 * 60 * 60 * 1000) {
      const timer = window.setTimeout(() => {
        autoSyncAttempted.current = true
        void syncGarmin(true)
      }, 0)
      return () => window.clearTimeout(timer)
    }
  }, [garmin, syncGarmin])

  const connectGarmin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setGarminBusy(true)
    try {
      const response = await request('/integrations/garmin/connect', {
        method: 'POST', headers: jsonHeaders,
        body: JSON.stringify({ email: garminEmail, password: garminPassword })
      })
      if (!response.ok) { setMessage(await errorText(response)); return }
      const result: { status: string } = await response.json()
      if (result.status === 'needs_mfa') {
        setNeedsMfa(true)
        setMessage('Garmin solicita un código de verificación. Introdúcelo en los próximos 5 minutos.')
      } else {
        setNeedsMfa(false)
        await loadGarminStatus()
        setMessage('Cuenta de Garmin conectada. Comenzará la primera sincronización.')
      }
    } catch { setMessage('No se pudo conectar con Garmin. Inténtalo más tarde.') }
    finally { setGarminPassword(''); setGarminBusy(false) }
  }

  const verifyGarmin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setGarminBusy(true)
    try {
      const response = await request('/integrations/garmin/mfa', {
        method: 'POST', headers: jsonHeaders, body: JSON.stringify({ code: garminCode })
      })
      if (!response.ok) { setMessage(await errorText(response)); return }
      setNeedsMfa(false)
      await loadGarminStatus()
      setMessage('Cuenta de Garmin conectada. Comenzará la primera sincronización.')
    } catch { setMessage('No se pudo verificar la conexión con Garmin.') }
    finally { setGarminCode(''); setGarminBusy(false) }
  }

  const disconnectGarmin = async () => {
    setGarminBusy(true)
    try {
      const response = await request('/integrations/garmin', { method: 'DELETE' })
      if (!response.ok) { setMessage(await errorText(response)); return }
      setNeedsMfa(false)
      autoSyncAttempted.current = false
      await loadGarminStatus()
      setMessage('Garmin desconectado. Las actividades ya importadas permanecen en tu historial.')
    } catch { setMessage('No se pudo desconectar Garmin. Inténtalo de nuevo.') }
    finally { setGarminBusy(false) }
  }

  // Fetch activities and goals
  useEffect(() => {
    Promise.all([
      request('/activities'),
      request('/goals')
    ]).then(async ([resActs, resGoals]) => {
      if (resActs.ok) {
        const data = await resActs.json()
        setActivities(data)
        setSelected((cur) => cur ?? data[0] ?? null)
      } else {
        setMessage(await errorText(resActs))
      }

      if (resGoals.ok) {
        setGoals(await resGoals.json())
      }
    }).finally(() => setLoading(false))
  }, [refresh, setMessage])

  // Handle general upload
  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)

    const response = await request('/activities/import', { method: 'POST', body: form })
    if (!response.ok) {
      setMessage(await errorText(response))
    } else {
      setSelected(await response.json())
      setMessage('Actividad importada correctamente en tu histórico general.')
      setRefresh((value) => value + 1)
    }
    event.target.value = ''
  }

  // Handle goal manual link update from activities view
  const handleLinkToGoal = async (activityId: number, goalIdVal: string) => {
    const goalId = goalIdVal ? Number(goalIdVal) : null
    const response = await request(`/activities/${activityId}/goal`, {
      method: 'PATCH',
      headers: jsonHeaders,
      body: JSON.stringify({ goal_id: goalId })
    })

    if (response.ok) {
      setSelected(await response.json())
      setMessage(goalId ? 'Actividad asignada al objetivo con éxito.' : 'Actividad desasociada del objetivo con éxito.')
      setRefresh((value) => value + 1)
    } else {
      setMessage(await errorText(response))
    }
  }
  const compatibleGoals = selected?.started_at
    ? goals.filter((goal) => {
        const activityDate = selected.started_at!.slice(0, 10)
        return Boolean(goal.start_date && activityDate >= goal.start_date && activityDate <= goal.target_date)
      })
    : []
  const remove = async (activity: Activity) => {
    const when = activity.started_at ? new Date(activity.started_at).toLocaleDateString('es-ES') : 'sin fecha'
    if (!confirm(`¿Eliminar “${activity.name}” (${when})? Esta acción no se puede deshacer.`)) return
    setDeletingId(activity.id)
    const response = await request(`/activities/${activity.id}`, { method: 'DELETE' })
    if (!response.ok) { setMessage(await errorText(response)); setDeletingId(null); return }
    setActivities(current => {
      const next = current.filter(item => item.id !== activity.id)
      setSelected(currentSelected => currentSelected?.id === activity.id ? next[0] ?? null : currentSelected)
      return next
    })
    setMessage('Actividad eliminada y archivo importado retirado.')
    setDeletingId(null)
  }

  if (loading) {
    return <section className="panel"><h2>Cargando histórico de actividades…</h2></section>
  }

  return (
    <>
      <section className="section-heading" style={{ marginBottom: '2rem' }}>
        <div>
          <p className="eyebrow">HISTÓRICO GENERAL</p>
          <h2>Todas tus Actividades</h2>
          <p className="subtitle">Historial de entrenamientos importados y archivados de forma privada para tu cuenta.</p>
        </div>
        <label className="import">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 19v2h14v-2H5z" /></svg>
          Importar FIT, TCX o GPX
          <input type="file" accept=".fit,.tcx,.gpx" onChange={upload} />
        </label>
      </section>

      <section className="panel" aria-label="Descarga experimental de Garmin">
        <p className="eyebrow">GARMIN CONNECT · EXPERIMENTAL</p>
        <h3>Descarga automática de actividades</h3>
        <p className="field-help">Conexión no oficial. Puede dejar de funcionar si Garmin cambia su servicio. Sincronizamos al abrir esta página si han pasado 24 horas; también puedes hacerlo cuando quieras. La importación FIT, TCX o GPX sigue disponible.</p>
        {garmin && !garmin.available && <p className="field-help">Esta función requiere que el administrador configure la clave de cifrado GARMIN_TOKEN_KEY.</p>}
        {garmin?.available && !garmin.connected && !needsMfa && (
          <form onSubmit={connectGarmin} className="form-grid" style={{ marginTop: '1rem' }}>
            <label>Correo de Garmin<input type="email" autoComplete="username" required value={garminEmail} onChange={e => setGarminEmail(e.target.value)} /></label>
            <label>Contraseña de Garmin<input type="password" autoComplete="current-password" required value={garminPassword} onChange={e => setGarminPassword(e.target.value)} /></label>
            <button className="secondary" type="submit" disabled={garminBusy}>{garminBusy ? 'Conectando…' : 'Conectar Garmin (experimental)'}</button>
            <p className="field-help">La contraseña se usa para iniciar sesión y no se guarda; se conserva una sesión cifrada para futuras descargas.</p>
          </form>
        )}
        {needsMfa && (
          <form onSubmit={verifyGarmin} className="form-grid" style={{ marginTop: '1rem' }}>
            <label>Código de verificación de Garmin<input autoComplete="one-time-code" required value={garminCode} onChange={e => setGarminCode(e.target.value)} /></label>
            <button className="secondary" type="submit" disabled={garminBusy}>{garminBusy ? 'Verificando…' : 'Verificar código'}</button>
          </form>
        )}
        {garmin?.connected && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap', marginTop: '1rem' }}>
            <span>Conectado · Última sincronización: {garmin.last_sync_at ? new Date(garmin.last_sync_at).toLocaleString('es-ES') : 'pendiente'}</span>
            <button className="secondary" type="button" disabled={garminBusy || !garmin.available} onClick={() => void syncGarmin()}>{garminBusy ? 'Sincronizando…' : 'Sincronizar ahora'}</button>
            <button className="secondary danger-action" type="button" disabled={garminBusy} onClick={() => void disconnectGarmin()}>Desconectar</button>
            {garmin.last_error && <p className="field-help" role="status">{garmin.last_error}</p>}
          </div>
        )}
      </section>

      <section className="summary">
        <article>
          <span>Total Actividades</span>
          <strong>{activities.length}</strong>
        </article>
        <article>
          <span>Distancia Acumulada</span>
          <strong>{(activities.reduce((sum, item) => sum + (item.distance_meters ?? 0), 0) / 1000).toFixed(1)} km</strong>
        </article>
        <article>
          <span>Tiempo Activo Acumulado</span>
          <strong>{duration(activities.reduce((sum, item) => sum + (item.duration_seconds ?? 0), 0))}</strong>
        </article>
      </section>

      <section className="content">
        <div className="list">
          {activities.map((item) => {
            const currentGoal = goals.find(g => g.id === item.goal_id)

            return (
              <div key={item.id} className={`activity activity-row ${selected?.id === item.id ? 'active' : ''}`}>
                <button style={{ flex: 1, textAlign: 'left', border: 'none', background: 'none', display: 'flex', gap: '12px', alignItems: 'center', cursor: 'pointer' }} type="button" onClick={() => setSelected(item)}>
                  <span className="avatar small sport">{item.sport.slice(0, 1)}</span>
                  <span>
                    <b>{item.name}</b>
                    <small>{item.started_at ? new Date(item.started_at).toLocaleDateString('es-ES') : 'Sin fecha'} · {item.sport}{item.source_provider === 'garmin' ? ' · Garmin' : ''}</small>
                    {currentGoal && (
                      <span className="badge activity-goal-badge">
                        🎯 {currentGoal.title}
                      </span>
                    )}
                  </span>
                </button>

                <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <b>{distance(item.distance_meters)}</b>
                  <small>{duration(item.duration_seconds)}</small>
                  <button className="secondary danger-action" type="button" disabled={deletingId === item.id} onClick={() => void remove(item)}>{deletingId === item.id ? 'Eliminando…' : 'Eliminar'}</button>
                </div>
              </div>
            )
          })}
          {!activities.length && <p>Aún no has importado actividades en tu cuenta.</p>}
        </div>

        <aside>
          {selected ? (
            <>
              <p className="eyebrow">MÉTRICAS Y DETALLE</p>
              <h2>{selected.name}</h2>
              <div className="metrics" style={{ margin: '1rem 0' }}>
                <Metric label="Distancia" value={distance(selected.distance_meters)} />
                <Metric label="Duración" value={duration(selected.duration_seconds)} />
                <Metric label="Desnivel" value={selected.elevation_gain_meters ? `${Math.round(selected.elevation_gain_meters)} m` : '—'} />
                <Metric label="FC media" value={selected.average_heart_rate ? `${selected.average_heart_rate} ppm` : '—'} />
                <Metric label="Potencia" value={selected.average_power ? `${selected.average_power} W` : '—'} />
                <Metric label="Cadencia" value={selected.average_cadence ? `${selected.average_cadence} rpm` : '—'} />
              </div>

              {/* Manual Goal Association */}
              <div className="goal-association">
                <label>
                  Asociar a un objetivo compatible por fechas
                  <select
                    value={selected.goal_id || ''}
                    onChange={(e) => void handleLinkToGoal(selected.id, e.target.value)}
                  >
                    <option value="">Ningún objetivo (Actividad general)</option>
                    {compatibleGoals.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.title} ({translateSportInOption(g.sport)})
                      </option>
                    ))}
                  </select>
                </label>
                {selected.started_at && compatibleGoals.length === 0 && <p className="field-help">No hay objetivos cuyo periodo incluya esta fecha.</p>}
                {!selected.started_at && <p className="field-help">Esta actividad no tiene fecha de inicio y no puede asociarse a un objetivo.</p>}
              </div>
              <button className="secondary danger-action" type="button" disabled={deletingId === selected.id} onClick={() => void remove(selected)} style={{ marginTop: '1rem' }}>{deletingId === selected.id ? 'Eliminando actividad…' : 'Eliminar actividad'}</button>
            </>
          ) : (
            <p>Selecciona una actividad de la lista de la izquierda para ver su detalle.</p>
          )}
        </aside>
      </section>
    </>
  )
}

function translateSportInOption(s: string) {
  const sports: Record<string, string> = {
    cycling_general: 'Ciclismo general',
    road_cycling: 'Carretera',
    mountain_biking: 'MTB',
    gravel: 'Gravel',
    indoor_cycling: 'Rodillo / indoor',
    cyclocross: 'Ciclocross',
    track_cycling: 'Pista'
  }
  return sports[s] || s
}
