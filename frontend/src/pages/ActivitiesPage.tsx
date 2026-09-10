import { ChangeEvent, useEffect, useState } from 'react'
import { Activity, Goal } from '../types'
import { request, duration, distance, errorText, jsonHeaders } from '../utils'
import { Metric } from '../components/Common'

interface ActivitiesPageProps {
  setMessage: (value: string) => void
}

export function ActivitiesPage({ setMessage }: ActivitiesPageProps) {
  const [activities, setActivities] = useState<Activity[]>([])
  const [goals, setGoals] = useState<Goal[]>([])
  const [selected, setSelected] = useState<Activity | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<number | null>(null)

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
                    <small>{item.started_at ? new Date(item.started_at).toLocaleDateString('es-ES') : 'Sin fecha'} · {item.sport}</small>
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
