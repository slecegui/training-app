import { ChangeEvent, useEffect, useState, useCallback } from 'react'
import { Goal, GoalRoute, Activity, WeeklyPlanRead, WeeklyPlanHistoryRead, ComplianceSummaryRead, ComplianceComponentRead, PlannedSessionResultRead } from '../types'
import { request, useLocation, errorText, jsonHeaders, duration, distance } from '../utils'
import { Input } from '../components/Common'
import { GoalForm } from '../components/GoalForm'
import { Icon as SharedIcon, IconName } from '../components/Icon'

interface ObjectiveDetailPageProps {
  goalId: string
  setMessage: (value: string) => void
}

type RouteDraftStatus = 'pending' | 'uploading' | 'success' | 'error'
interface RouteDraft {
  id: string
  file: File
  stageLabel: string
  displayOrder: number
  status: RouteDraftStatus
  error?: string
}

type GoalIconName = Extract<IconName, 'target' | 'edit' | 'trash' | 'route' | 'calendar' | 'activity' | 'upload' | 'plus' | 'check'>

function GoalIcon({ name }: { name: GoalIconName }) {
  return <SharedIcon name={name} className="goal-icon" />
}

export function ObjectiveDetailPage({ goalId, setMessage }: ObjectiveDetailPageProps) {
  const [, navigate] = useLocation()
  const [goal, setGoal] = useState<Goal | null>(null)
  const [loading, setLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)

  // Sub-sections states
  const [activities, setActivities] = useState<Activity[]>([])
  const [routes, setRoutes] = useState<GoalRoute[]>([])
  const [routePanelOpen, setRoutePanelOpen] = useState(false)
  const [routeDrafts, setRouteDrafts] = useState<RouteDraft[]>([])
  const [routeUploading, setRouteUploading] = useState(false)
  const [editingRouteId, setEditingRouteId] = useState<number | null>(null)
  const [routeLabelDraft, setRouteLabelDraft] = useState('')
  const [routeOrderDraft, setRouteOrderDraft] = useState('0')
  const [refreshKey, setRefreshKey] = useState(0)

  // Plan & sessions states
  const [activePlan, setActivePlan] = useState<WeeklyPlanRead | null>(null)
  const [history, setHistory] = useState<WeeklyPlanHistoryRead[]>([])
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)
  const [viewedPlan, setViewedPlan] = useState<WeeklyPlanRead | null>(null)
  const [regenReason, setRegenReason] = useState('')
  const [refDate, setRefDate] = useState('')

  // Linking session results states
  const [editingSessionId, setEditingSessionId] = useState<number | null>(null)
  const [eligibleActivities, setEligibleActivities] = useState<Activity[]>([])
  const [status, setStatus] = useState<'completed' | 'omitted' | 'partial' | 'replaced'>('completed')
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null)
  const [linkReason, setLinkReason] = useState('')
  const [corrReason, setCorrReason] = useState('')
  const [linkNotes, setLinkNotes] = useState('')

  // Compliance states
  const [compliance, setCompliance] = useState<ComplianceSummaryRead | null>(null)
  const [goalCompliance, setGoalCompliance] = useState<ComplianceSummaryRead | null>(null)
  const [complianceHistory, setComplianceHistory] = useState<ComplianceSummaryRead[]>([])
  const [calculatingCompliance, setSubmittingCompliance] = useState(false)

  const memoizedNavigate = useCallback((path: string) => navigate(path), [navigate])
  const memoizedSetMessage = useCallback((msg: string) => setMessage(msg), [setMessage])

  // Fetch full goal details
  useEffect(() => {
    void request(`/goals/${goalId}`)
      .then(async (res) => {
        if (res.ok) {
          setGoal(await res.json())
        } else {
          memoizedSetMessage(await errorText(res))
          memoizedNavigate('/objectives')
        }
      })
      .finally(() => setLoading(false))
  }, [goalId, isEditing, refreshKey, memoizedNavigate, memoizedSetMessage])

  // Fetch associated activities and active plan details
  useEffect(() => {
    if (!goal) return

    // 1. Fetch routes and activities of this goal
    void request(`/goals/${goal.id}/routes`).then(async (res) => {
      if (res.ok) setRoutes(await res.json())
    })

    void request(`/goals/${goal.id}/activities`).then(async (res) => {
      if (res.ok) {
        const data = await res.json()
        setActivities(data)
      }
    })

    // 2. Fetch active plan of the goal
    void request(`/plans/active?goal_id=${goal.id}`)
      .then(async (res) => {
        if (res.ok) {
          const plan: WeeklyPlanRead = await res.json()
          setActivePlan(plan)
          setViewedPlan(plan)
          setSelectedPlanId(plan.id)
          // Fetch plan history
          void request(`/plans/history?goal_id=${goal.id}&start_date=${plan.start_date}`).then(async (hRes) => {
            if (hRes.ok) {
              setHistory(await hRes.json())
            }
          })
        } else {
          setActivePlan(null)
          setViewedPlan(null)
          setSelectedPlanId(null)
          setHistory([])
        }
      })
  }, [goal, refreshKey])

  // Fetch compliance
  useEffect(() => {
    if (!viewedPlan || !goal) return

    void request(`/plans/${viewedPlan.id}/compliance`)
      .then(async (res) => {
        if (res.ok) {
          setCompliance(await res.json())
        } else {
          setCompliance(null)
        }
      })

    void request(`/plans/${viewedPlan.id}/compliance/history`)
      .then(async (res) => {
        if (res.ok) {
          setComplianceHistory(await res.json())
        } else {
          setComplianceHistory([])
        }
      })

    void request(`/goals/${goal.id}/compliance?from_date=${viewedPlan.start_date}&to_date=${viewedPlan.end_date}`)
      .then(async (res) => {
        if (res.ok) {
          setGoalCompliance(await res.json())
        } else {
          setGoalCompliance(null)
        }
      })
  }, [viewedPlan, goal, refreshKey])

  // Handle plan selection from history dropdown
  const handleSelectPlan = async (planId: number) => {
    const res = await request(`/plans/${planId}`)
    if (res.ok) {
      const plan: WeeklyPlanRead = await res.json()
      setViewedPlan(plan)
      setSelectedPlanId(plan.id)
    } else {
      setMessage('No se pudo cargar la versión del plan especificada.')
    }
  }

  // Handle Goal activation
  const handleActivate = async () => {
    if (!goal) return
    const res = await request(`/goals/${goal.id}`, {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify({ ...goal, is_active: true })
    })
    if (res.ok) {
      setMessage('Objetivo activado correctamente.')
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
  }

  // Handle Goal deletion
  const handleDelete = async () => {
    if (!goal) return
    if (!confirm(`¿Estás seguro de que deseas eliminar permanentemente el objetivo "${goal.title}"?`)) {
      return
    }
    const res = await request(`/goals/${goal.id}`, { method: 'DELETE' })
    if (res.ok) {
      setMessage('Objetivo eliminado correctamente.')
      navigate('/objectives')
    } else {
      setMessage(await errorText(res))
    }
  }

  // Handle manual activity disassociation
  const handleDisassociateActivity = async (actId: number) => {
    if (!confirm('¿Deseas desasociar esta actividad del objetivo?')) return
    const res = await request(`/activities/${actId}/goal`, {
      method: 'PATCH',
      headers: jsonHeaders,
      body: JSON.stringify({ goal_id: null })
    })
    if (res.ok) {
      setMessage('Actividad desasociada del objetivo.')
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
  }

  // Handle direct file import for this goal
  const handleUploadActivity = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!goal) return
    const file = event.target.files?.[0]
    if (!file) return

    const form = new FormData()
    form.append('file', file)

    // Call import with goal_id in query!
    const res = await request(`/activities/import?goal_id=${goal.id}`, {
      method: 'POST',
      body: form
    })

    if (res.ok) {
      setMessage('Actividad importada y asociada al objetivo correctamente.')
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
    event.target.value = ''
  }

  const selectRouteFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []).filter((file) => file.name.toLowerCase().endsWith('.gpx'))
    setRouteDrafts(files.map((file, index) => ({
      id: `${file.name}-${file.lastModified}-${index}`,
      file,
      stageLabel: '',
      displayOrder: routes.length + index,
      status: 'pending'
    })))
    event.target.value = ''
  }

  const updateRouteDraft = (id: string, field: 'stageLabel' | 'displayOrder', value: string) => {
    setRouteDrafts((drafts) => drafts.map((draft) => draft.id === id ? {
      ...draft,
      [field]: field === 'displayOrder' ? Number(value) : value
    } : draft))
  }

  const uploadRouteDrafts = async () => {
    if (!goal || routeDrafts.length === 0) return
    setRouteUploading(true)
    for (const draft of routeDrafts) {
      if (draft.status === 'success') continue
      setRouteDrafts((drafts) => drafts.map((item) => item.id === draft.id ? { ...item, status: 'uploading', error: undefined } : item))
      const form = new FormData()
      form.append('file', draft.file)
      if (draft.stageLabel.trim()) form.append('stage_label', draft.stageLabel.trim())
      form.append('display_order', String(Math.max(0, draft.displayOrder)))
      try {
        const response = await request(`/goals/${goal.id}/routes`, { method: 'POST', body: form })
        if (!response.ok) throw new Error(await errorText(response))
        const route: GoalRoute = await response.json()
        setRoutes((current) => [...current, route].sort((a, b) => a.display_order - b.display_order || a.id - b.id))
        setRouteDrafts((drafts) => drafts.map((item) => item.id === draft.id ? { ...item, status: 'success' } : item))
      } catch (error) {
        setRouteDrafts((drafts) => drafts.map((item) => item.id === draft.id ? {
          ...item,
          status: 'error',
          error: error instanceof Error ? error.message : 'No se pudo subir el archivo.'
        } : item))
      }
    }
    setRouteUploading(false)
  }

  const startRouteEdit = (route: GoalRoute) => {
    setEditingRouteId(route.id)
    setRouteLabelDraft(route.stage_label ?? '')
    setRouteOrderDraft(String(route.display_order))
  }

  const saveRouteEdit = async (routeId: number) => {
    if (!goal) return
    const response = await request(`/goals/${goal.id}/routes/${routeId}`, {
      method: 'PATCH',
      headers: jsonHeaders,
      body: JSON.stringify({ stage_label: routeLabelDraft.trim() || null, display_order: Math.max(0, Number(routeOrderDraft) || 0) })
    })
    if (!response.ok) return setMessage(await errorText(response))
    const updated: GoalRoute = await response.json()
    setRoutes((current) => [...current.filter((route) => route.id !== routeId), updated].sort((a, b) => a.display_order - b.display_order || a.id - b.id))
    setEditingRouteId(null)
    setMessage('Metadatos de la ruta actualizados.')
  }

  const deleteRoute = async (route: GoalRoute) => {
    if (!goal || !confirm(`¿Eliminar la ruta “${route.original_filename}”${route.stage_label ? ` (${route.stage_label})` : ''}?`)) return
    const response = await request(`/goals/${goal.id}/routes/${route.id}`, { method: 'DELETE' })
    if (!response.ok) return setMessage(await errorText(response))
    setRoutes((current) => current.filter((item) => item.id !== route.id))
    setMessage('Ruta GPX eliminada.')
  }

  // Handle weekly plan generation / regeneration
  const handleGeneratePlan = async (force: boolean) => {
    if (!goal) return
    if (force && !confirm('¿Estás seguro de que deseas regenerar el plan semanal? Esto marcará la versión actual como inactiva.')) {
      return
    }
    const payload = {
      force_regenerate: force,
      generation_reason: regenReason || null,
      reference_date: refDate || null
    }
    const res = await request('/plans/generate', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    })
    if (res.ok) {
      const plan: WeeklyPlanRead = await res.json()
      setActivePlan(plan)
      setViewedPlan(plan)
      setSelectedPlanId(plan.id)
      setRegenReason('')
      setRefDate('')
      setMessage(force ? 'Plan semanal regenerado.' : 'Plan semanal generado.')
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
  }

  // Results linking logic
  const startLinking = async (sessionId: number, currentResult?: PlannedSessionResultRead) => {
    setEditingSessionId(sessionId)
    setStatus((currentResult?.status as 'completed' | 'omitted' | 'partial' | 'replaced') || 'completed')
    setLinkReason(currentResult?.reason || '')
    setCorrReason('')
    setLinkNotes(currentResult?.notes || '')

    const res = await request(`/planned-sessions/${sessionId}/eligible-activities`)
    if (res.ok) {
      const acts = await res.json()
      setEligibleActivities(acts)
      if (currentResult?.activity_id) {
        setSelectedActivityId(currentResult.activity_id)
      } else {
        setSelectedActivityId(acts[0]?.id || null)
      }
    } else {
      setEligibleActivities([])
    }
  }

  const saveResult = async (sessionId: number, hasExistingResult: boolean) => {
    if (status !== 'omitted' && !selectedActivityId) {
      setMessage('Debes seleccionar una actividad.')
      return
    }
    if (status !== 'completed' && !linkReason.trim()) {
      setMessage('Debes especificar un motivo o explicación.')
      return
    }
    if (hasExistingResult && !corrReason.trim()) {
      setMessage('Debes especificar un motivo de corrección.')
      return
    }

    const payload = {
      status,
      activity_id: status === 'omitted' ? null : Number(selectedActivityId),
      reason: status === 'completed' ? null : linkReason,
      correction_reason: hasExistingResult ? corrReason : null,
      notes: linkNotes || null
    }

    const res = await request(`/planned-sessions/${sessionId}/result`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    })

    if (res.ok) {
      setMessage('Resultado guardado correctamente.')
      setEditingSessionId(null)
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
  }

  // Recalculate Compliance
  const recalculateCompliance = async () => {
    if (!viewedPlan || !goal) return
    setSubmittingCompliance(true)
    const res = await request(`/plans/${viewedPlan.id}/compliance/calculate`, { method: 'POST' })
    if (res.ok) {
      setMessage('Cumplimiento recalculado.')
      await request(`/goals/${goal.id}/compliance/calculate`, {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify({ from_date: viewedPlan.start_date, to_date: viewedPlan.end_date })
      })
      setRefreshKey((k) => k + 1)
    } else {
      setMessage(await errorText(res))
    }
    setSubmittingCompliance(false)
  }

  // Render a fixed 7-day plan table (Mon-Sun)
  const renderWeeklyTable = () => {
    if (!viewedPlan) return null

    const daysOfWeek = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    const start = new Date(viewedPlan.start_date + 'T00:00:00')

    const tableRows = []
    let totalPlannedMins = 0

    for (let i = 0; i < 7; i++) {
      const currentDate = new Date(start)
      currentDate.setDate(start.getDate() + i)
      const dateStr = currentDate.toISOString().split('T')[0]
      const dayLabel = daysOfWeek[i]

      // Find matching session for this date
      const s = viewedPlan.sessions.find(x => x.date === dateStr)
      const activeRes = s?.results?.find(r => r.is_current)

      if (s) {
        totalPlannedMins += s.planned_duration
      }

      tableRows.push(
        <tr key={i} style={{ borderBottom: '1px solid #d8ddd5' }}>
          <td style={{ padding: '12px', fontWeight: 'bold' }}>
            {dayLabel} <span style={{ fontWeight: 'normal', color: '#888', fontSize: '0.8rem' }}>({currentDate.toLocaleDateString('es-ES')})</span>
          </td>
          <td style={{ padding: '12px' }}>
            {s ? (
              <div>
                <strong>{s.title}</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#666' }}>{s.description}</p>
                {s.rationale && (
                  <p style={{ margin: '4px 0 0 0', fontSize: '0.75rem', color: '#888', fontStyle: 'italic' }}>Decisión: {s.rationale}</p>
                )}
              </div>
            ) : (
              <span style={{ color: '#888', fontStyle: 'italic' }}>Descanso</span>
            )}
          </td>
          <td style={{ padding: '12px', textAlign: 'center' }}>
            {s ? `${s.planned_duration} min` : '—'}
          </td>
          <td style={{ padding: '12px', textAlign: 'center', color: '#888', fontStyle: 'italic' }}>
            {s ? 'No disponible' : '—'}
          </td>
          <td style={{ padding: '12px', textAlign: 'right' }}>
            {s ? (
              editingSessionId === s.id ? (
                <div style={{ background: 'rgba(0,0,0,0.02)', padding: '10px', borderRadius: '4px', textAlign: 'left', minWidth: '220px' }}>
                  <select value={status} onChange={(e) => setStatus(e.target.value as 'completed' | 'omitted' | 'partial' | 'replaced')} style={{ display: 'block', marginBottom: '8px', fontSize: '0.85rem' }}>
                    <option value="completed">Completado</option>
                    <option value="omitted">Omitido</option>
                    <option value="partial">Parcial</option>
                    <option value="replaced">Sustituido</option>
                  </select>
                  {status !== 'omitted' && (
                    <select value={selectedActivityId || ''} onChange={(e) => setSelectedActivityId(Number(e.target.value))} style={{ display: 'block', marginBottom: '8px', fontSize: '0.85rem' }}>
                      {eligibleActivities.length === 0 ? (
                        <option value="">Sin actividades disponibles</option>
                      ) : (
                        eligibleActivities.map(a => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))
                      )}
                    </select>
                  )}
                  {status !== 'completed' && (
                    <input placeholder="Motivo (Obligatorio)" value={linkReason} onChange={e => setLinkReason(e.target.value)} style={{ padding: '6px', fontSize: '0.85rem', marginBottom: '8px', display: 'block', width: '100%' }} />
                  )}
                  {activeRes && (
                    <input placeholder="Motivo de corrección" value={corrReason} onChange={e => setCorrReason(e.target.value)} style={{ padding: '6px', fontSize: '0.85rem', marginBottom: '8px', display: 'block', width: '100%' }} />
                  )}
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button className="primary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => void saveResult(s.id, !!activeRes)}>OK</button>
                    <button className="secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => setEditingSessionId(null)}>Cancel</button>
                  </div>
                </div>
              ) : activeRes ? (
                <div>
                  <span className="badge" style={{ background: activeRes.status === 'completed' ? '#2e7d32' : '#ef6c00', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontSize: '0.75rem' }}>
                    {activeRes.status}
                  </span>
                  <button className="link-button" style={{ marginLeft: '8px', fontSize: '0.8rem' }} onClick={() => void startLinking(s.id, activeRes)}>
                    Corregir
                  </button>
                </div>
              ) : (
                <button className="primary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => void startLinking(s.id)}>
                  Vincular
                </button>
              )
            ) : '—'}
          </td>
        </tr>
      )
    }

    return (
      <div className="panel weekly-plan-table" style={{ marginTop: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h4><GoalIcon name="calendar" /> Vista de plan semanal ({viewedPlan.start_date} al {viewedPlan.end_date})</h4>
          {history.length > 1 && (
            <label style={{ fontSize: '0.8rem' }}>
              Versión:
              <select value={selectedPlanId || ''} onChange={e => void handleSelectPlan(Number(e.target.value))} style={{ marginLeft: '0.5rem', padding: '4px', fontSize: '0.8rem' }}>
                {history.map(h => (
                  <option key={h.id} value={h.id}>v{h.version} {h.is_active ? '(Vigente)' : '(Histórica)'}</option>
                ))}
              </select>
            </label>
          )}
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: '#f5f5ee', borderBottom: '1px solid #cbd2c8' }}>
              <th style={{ padding: '12px' }}>Día</th>
              <th style={{ padding: '12px' }}>Detalles de la sesión</th>
              <th style={{ padding: '12px', textAlign: 'center' }}>Duración</th>
              <th style={{ padding: '12px', textAlign: 'center' }}>Fichero rodillo</th>
              <th style={{ padding: '12px', textAlign: 'right' }}>Resultado</th>
            </tr>
          </thead>
          <tbody>
            {tableRows}
          </tbody>
          <tfoot>
            <tr style={{ background: '#e5e9e0', fontWeight: 'bold' }}>
              <td colSpan={2} style={{ padding: '12px' }}>Total Planificado de la Semana:</td>
              <td style={{ padding: '12px', textAlign: 'center' }}>{totalPlannedMins} min</td>
              <td colSpan={2}></td>
            </tr>
          </tfoot>
        </table>
      </div>
    )
  }

  if (loading) {
    return <section className="panel"><h2>Cargando espacio de trabajo de tu objetivo…</h2></section>
  }

  if (!goal) {
    return <section className="panel"><h2>Objetivo no encontrado</h2></section>
  }

  return (
    <>
      <header className="goal-detail-header">
        <div className="goal-detail-heading">
          <span className={`goal-status ${goal.is_active ? 'is-active' : ''}`}>
            <span className="status-dot" aria-hidden="true" />
            {goal.is_active ? 'Objetivo activo' : 'Objetivo inactivo'}
          </span>
          <h1>{goal.title}</h1>
          <p className="subtitle">
            Periodo de preparación: <strong>{goal.start_date ? new Date(goal.start_date + 'T00:00:00').toLocaleDateString('es-ES') : '—'}</strong> al <strong>{new Date(goal.target_date + 'T00:00:00').toLocaleDateString('es-ES')}</strong>
          </p>
        </div>
        <div className="goal-detail-actions">
          {!goal.is_active && (
            <button className="secondary" type="button" onClick={() => void handleActivate()}>
              <GoalIcon name="check" /> Activar objetivo
            </button>
          )}
          <button className="secondary" type="button" onClick={() => setIsEditing(!isEditing)}>
            <GoalIcon name="edit" /> {isEditing ? 'Ver objetivo' : 'Editar datos'}
          </button>
          <button className="secondary danger-button" type="button" onClick={() => void handleDelete()}>
            <GoalIcon name="trash" /> Eliminar
          </button>
        </div>
      </header>

      {isEditing ? (
        <section className="panel">
          <h2>Editar datos del objetivo</h2>
          <GoalForm goal={goal} onSuccess={() => setIsEditing(false)} onCancel={() => setIsEditing(false)} setMessage={setMessage} />
        </section>
      ) : (
        <div className="goal-detail-sections">
          {/* 1. Header / Resumen de métrica */}
          <section className="panel goal-metric-panel">
            <p className="eyebrow">Métrica de éxito establecida</p>
            <div className="goal-metric-content">
              <strong><GoalIcon name="target" />{goal.success_metric}</strong>
              {goal.details && <p style={{ margin: 0, fontStyle: 'italic', color: '#666' }}>"{goal.details}"</p>}
            </div>
          </section>
          <section className="panel goal-routes-panel">
            <div className="section-heading goal-section-heading">
              <div>
                <p className="eyebrow"><GoalIcon name="route" /> Rutas del objetivo</p>
                <h2>Recorridos por etapa</h2>
                <p className="subtitle">Añade una ruta por etapa o día. La distancia y el desnivel se calculan desde el GPX.</p>
              </div>
              <button className="primary" type="button" onClick={() => setRoutePanelOpen(!routePanelOpen)}>
                <GoalIcon name="plus" /> Añadir ruta GPX
              </button>
            </div>

            {routePanelOpen && (
              <div className="route-upload-panel">
                <label className="route-file-picker">
                  <span>Seleccionar uno o varios archivos GPX</span>
                  <input type="file" accept=".gpx,application/gpx+xml" multiple onChange={selectRouteFiles} />
                </label>
                {routeDrafts.length > 0 && (
                  <div className="route-draft-list">
                    {routeDrafts.map((draft) => (
                      <div className="route-draft" key={draft.id}>
                        <div className="route-draft-file"><strong>{draft.file.name}</strong><small>{(draft.file.size / 1024).toFixed(1)} KB</small></div>
                        <label>Etapa o día<input value={draft.stageLabel} onChange={(event) => updateRouteDraft(draft.id, 'stageLabel', event.target.value)} maxLength={120} disabled={draft.status === 'uploading' || draft.status === 'success'} /></label>
                        <label>Orden<input type="number" min="0" value={draft.displayOrder} onChange={(event) => updateRouteDraft(draft.id, 'displayOrder', event.target.value)} disabled={draft.status === 'uploading' || draft.status === 'success'} /></label>
                        <span className={`route-upload-status is-${draft.status}`} role={draft.status === 'error' ? 'alert' : undefined}>
                          {draft.status === 'pending' ? 'Pendiente' : draft.status === 'uploading' ? 'Subiendo…' : draft.status === 'success' ? 'Subida' : draft.error}
                        </span>
                      </div>
                    ))}
                    <button className="primary route-upload-submit" type="button" onClick={() => void uploadRouteDrafts()} disabled={routeUploading || routeDrafts.every((draft) => draft.status === 'success')}>
                      <GoalIcon name="upload" /> {routeUploading ? 'Subiendo rutas…' : 'Subir rutas seleccionadas'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {routes.length === 0 ? (
              <div className="compact-empty-state">
                <GoalIcon name="route" />
                <div><strong>Aún no hay rutas asociadas</strong><p>Adjunta uno o varios GPX para organizar las etapas de este objetivo.</p></div>
              </div>
            ) : (
              <div className="route-list" aria-label="Rutas del objetivo">
                {routes.slice().sort((a, b) => a.display_order - b.display_order || a.id - b.id).map((route) => (
                  <article className="route-row" key={route.id}>
                    {editingRouteId === route.id ? (
                      <div className="route-edit-grid">
                        <label>Etapa o día<input value={routeLabelDraft} onChange={(event) => setRouteLabelDraft(event.target.value)} maxLength={120} /></label>
                        <label>Orden<input type="number" min="0" value={routeOrderDraft} onChange={(event) => setRouteOrderDraft(event.target.value)} /></label>
                        <div className="route-row-actions"><button className="primary" type="button" onClick={() => void saveRouteEdit(route.id)}>Guardar</button><button className="secondary" type="button" onClick={() => setEditingRouteId(null)}>Cancelar</button></div>
                      </div>
                    ) : (
                      <>
                        <div className="route-order" aria-label={`Orden ${route.display_order + 1}`}>{route.display_order + 1}</div>
                        <div className="route-row-main"><strong>{route.stage_label || `Ruta ${route.display_order + 1}`}</strong><span>{route.original_filename}</span></div>
                        <div className="route-row-metrics"><span>{route.distance_meters != null ? `${(route.distance_meters / 1000).toFixed(1)} km` : '—'}</span><span>{route.elevation_gain_meters != null ? `${Math.round(route.elevation_gain_meters)} m+` : '—'}</span><small>{new Date(route.uploaded_at).toLocaleDateString('es-ES')}</small></div>
                        <div className="route-row-actions"><button className="link-button" type="button" onClick={() => startRouteEdit(route)}>Editar</button><button className="link-button danger-link" type="button" onClick={() => void deleteRoute(route)}>Eliminar</button></div>
                      </>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* 2. Planificación Semanal */}
          <section className="panel goal-work-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3><GoalIcon name="calendar" /> Planificación semanal</h3>
              {!activePlan && goal.is_active && (
                <button className="primary" onClick={() => void handleGeneratePlan(false)}>
                  <GoalIcon name="plus" /> Generar plan semanal
                </button>
              )}
              {activePlan && (
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <Input type="date" label="Fecha ref (Opc)" value={refDate} onChange={e => setRefDate(e.target.value)} />
                  <button className="secondary" style={{ background: '#fae1dc', color: '#c62828', height: '42px', marginTop: '1.5rem' }} onClick={() => void handleGeneratePlan(true)}>
                    Regenerar Plan
                  </button>
                </div>
              )}
            </div>
            {!activePlan ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>
                {!goal.is_active ? 'Este objetivo no está activo. Actívalo para generar o ver tu planificación semanal.' : 'Aún no has generado planificación semanal para este objetivo.'}
              </div>
            ) : (
              renderWeeklyTable()
            )}
          </section>

          {/* 3. Actividades del objetivo */}
          <section className="panel goal-work-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h3><GoalIcon name="activity" /> Actividades del objetivo</h3>
                <p className="subtitle" style={{ margin: 0 }}>Listado de entrenamientos deportivos realizados e importados dentro del periodo del objetivo.</p>
              </div>
              <label className="import">
                <GoalIcon name="upload" /> Importar FIT/TCX/GPX para objetivo
                <input type="file" accept=".fit,.tcx,.gpx" onChange={handleUploadActivity} />
              </label>
            </div>

            {activities.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>
                No hay actividades asociadas a este objetivo todavía. Importa un archivo arriba para asociarlo.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: '#f5f5ee', borderBottom: '1px solid #cbd2c8' }}>
                    <th style={{ padding: '12px' }}>Fecha</th>
                    <th style={{ padding: '12px' }}>Nombre</th>
                    <th style={{ padding: '12px', textAlign: 'center' }}>Duración</th>
                    <th style={{ padding: '12px', textAlign: 'center' }}>Distancia</th>
                    <th style={{ padding: '12px', textAlign: 'center' }}>Desnivel</th>
                    <th style={{ padding: '12px', textAlign: 'right' }}>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {activities.map((act) => (
                    <tr key={act.id} style={{ borderBottom: '1px solid #d8ddd5' }}>
                      <td style={{ padding: '12px' }}>{act.started_at ? new Date(act.started_at).toLocaleDateString('es-ES') : '—'}</td>
                      <td style={{ padding: '12px', fontWeight: 'bold' }}>{act.name}</td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>{duration(act.duration_seconds)}</td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>{distance(act.distance_meters)}</td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>{act.elevation_gain_meters ? `${Math.round(act.elevation_gain_meters)} m` : '—'}</td>
                      <td style={{ padding: '12px', textAlign: 'right' }}>
                        <button className="secondary" style={{ color: '#c62828', padding: '4px 8px', fontSize: '0.8rem' }} onClick={() => void handleDisassociateActivity(act.id)}>
                          Desasociar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* 4. Cumplimiento */}
          {compliance && (
            <section className="panel" style={{ background: 'var(--bg-card)', padding: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div>
                  <span className="badge" style={{ background: '#7e57c2', color: '#fff' }}>Regla: {compliance.ruleset_version} (rev {compliance.revision})</span>
                  <h3 style={{ margin: '0.5rem 0 0 0', display: 'flex', alignItems: 'center', gap: '8px' }}><GoalIcon name="activity" /> Cumplimiento semanal</h3>
                </div>
                <button className="primary" style={{ background: '#7e57c2', fontSize: '0.85rem' }} type="button" disabled={calculatingCompliance} onClick={() => void recalculateCompliance()}>
                  {calculatingCompliance ? 'Calculando...' : 'Recalcular'}
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem', alignItems: 'center' }}>
                <div style={{ textAlign: 'center', background: 'rgba(0,0,0,0.2)', padding: '1.5rem', borderRadius: '8px' }}>
                  {compliance.status === 'complete' ? (
                    <div>
                      <strong style={{ display: 'block', fontSize: '2.5rem', color: 'var(--primary)' }}>{Number(compliance.percentage).toFixed(2)}%</strong>
                      <span style={{ fontSize: '0.85rem', color: '#888' }}>Definitivo</span>
                    </div>
                  ) : compliance.status === 'incomplete' ? (
                    <div>
                      <strong style={{ display: 'block', fontSize: '1.5rem', color: '#ef6c00' }}>INCOMPLETO</strong>
                      <span style={{ fontSize: '0.85rem', color: '#bbb' }}>Faltan resultados por registrar</span>
                    </div>
                  ) : (
                    <div>
                      <strong style={{ display: 'block', fontSize: '1.5rem', color: '#c62828' }}>N/A</strong>
                      <span style={{ fontSize: '0.85rem', color: '#bbb' }}>Denominador cero</span>
                    </div>
                  )}
                </div>

                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                        <th style={{ textAlign: 'left', padding: '0.5rem 0' }}>Sesión</th>
                        <th style={{ textAlign: 'center', padding: '0.5rem 0' }}>Peso (min)</th>
                        <th style={{ textAlign: 'center', padding: '0.5rem 0' }}>Crédito</th>
                        <th style={{ textAlign: 'right', padding: '0.5rem 0' }}>Contribución</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compliance.components?.map((comp: ComplianceComponentRead) => {
                        const s = viewedPlan?.sessions.find(x => x.id === comp.planned_session_id);
                        return (
                          <tr key={comp.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '0.5rem 0' }}>
                              <strong style={{ display: 'block' }}>{s?.title || 'Sesión'}</strong>
                              {comp.exclusion_or_error_reason && (
                                <span style={{ fontSize: '0.75rem', color: '#ef6c00' }}>{comp.exclusion_or_error_reason}</span>
                              )}
                            </td>
                            <td style={{ textAlign: 'center', padding: '0.5rem 0' }}>{Number(comp.weight)}</td>
                            <td style={{ textAlign: 'center', padding: '0.5rem 0' }}>{comp.credit != null ? Number(comp.credit).toFixed(4) : '—'}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{comp.weighted_credit != null ? Number(comp.weighted_credit).toFixed(2) : '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.75rem', fontSize: '0.85rem', color: '#888' }}>
                    <span>Numerador total: {Number(compliance.numerator).toFixed(2)} min</span>
                    <span>Denominador total: {Number(compliance.denominator).toFixed(2)} min</span>
                  </div>
                </div>
              </div>

              {complianceHistory.length > 1 && (
                <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.75rem', fontSize: '0.85rem', color: '#888' }}>
                  <b>Historial de revisiones de cálculo:</b>
                  <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.25rem', maxHeight: '100px', overflowY: 'auto' }}>
                    {complianceHistory.map((h) => (
                      <li key={h.id}>
                        rev {h.revision} ({h.status === 'complete' ? `${Number(h.percentage).toFixed(2)}%` : h.status}) · {new Date(h.computed_at).toLocaleString('es-ES')} {h.is_current ? '(Vigente)' : '(Sustituido)'}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {goalCompliance && (
                <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>Acumulado acumulado del objetivo:</strong>
                    <span style={{ fontSize: '0.85rem', color: '#aaa', marginLeft: '0.5rem' }}>rango {new Date(goalCompliance.from_date + 'T00:00:00').toLocaleDateString('es-ES')} al {new Date(goalCompliance.to_date + 'T00:00:00').toLocaleDateString('es-ES')}</span>
                  </div>
                  <span className="badge" style={{ background: goalCompliance.status === 'complete' ? 'var(--primary)' : '#ef6c00', fontSize: '0.9rem', padding: '0.35rem 0.65rem' }}>
                    {goalCompliance.status === 'complete' ? `${Number(goalCompliance.percentage).toFixed(2)}%` : 'INCOMPLETO'}
                  </span>
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </>
  )
}
