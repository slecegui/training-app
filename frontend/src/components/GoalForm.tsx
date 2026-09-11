import { FormEvent, useState } from 'react'
import { Goal } from '../types'
import { Input } from './Common'
import { request, jsonHeaders, errorText } from '../utils'

interface GoalFormProps {
  goal?: Goal | null // If present, we are in Edit mode; otherwise in Create mode
  onSuccess: (savedGoal: Goal) => void
  onCancel: () => void
  setMessage: (value: string) => void
}

export function GoalForm({ goal, onSuccess, onCancel, setMessage }: GoalFormProps) {
  const [title, setTitle] = useState(goal?.title || '')
  const [goalType, setGoalType] = useState(goal?.goal_type || 'sportive')
  const [sport, setSport] = useState(goal?.sport || 'road_cycling')
  const [startDate, setStartDate] = useState(goal?.start_date || new Date().toISOString().split('T')[0])
  const [targetDate, setTargetDate] = useState(goal?.target_date || '')
  const [priority, setPriority] = useState(goal?.priority || 'medium')
  const [distKm, setDistKm] = useState(goal?.target_distance_meters ? (goal.target_distance_meters / 1000).toString() : '')
  const [elevM, setElevM] = useState(goal?.target_elevation_meters ? goal.target_elevation_meters.toString() : '')
  const [successMetricType, setSuccessMetricType] = useState(goal?.success_metric_type || 'completar')
  const [successMetricValue, setSuccessMetricValue] = useState(goal?.success_metric_value?.toString() || '')
  const [details, setDetails] = useState(goal?.details || '')
  const [isActive, setIsActive] = useState(goal?.is_active || false)
  const [submitting, setSubmitting] = useState(false)

  const getMetricLabelAndUnit = (mType: string) => {
    switch (mType) {
      case 'completar':
        return { label: 'Sin campos adicionales', unit: '', type: 'none' }
      case 'tiempo_maximo':
        return { label: 'Tiempo Máximo Objetivo (horas, ej: 4.5)', unit: 'horas', type: 'number', step: '0.01' }
      case 'velocidad_media':
        return { label: 'Velocidad Media Objetivo', unit: 'km/h', type: 'number', step: '0.1' }
      case 'posicion_objetivo':
        return { label: 'Posición de Clasificación', unit: 'puesto', type: 'number', step: '1' }
      case 'potencia_media':
        return { label: 'Potencia Media Objetivo', unit: 'W', type: 'number', step: '1' }
      case 'distancia_total':
        return { label: 'Distancia de Resistencia', unit: 'km', type: 'number', step: '0.1' }
      case 'duracion_total':
        return { label: 'Duración Total Objetivo', unit: 'minutos', type: 'number', step: '1' }
      case 'ftp_objetivo':
        return { label: 'Vatios de FTP Objetivo', unit: 'W', type: 'number', step: '1' }
      case 'ftp_incremento':
        return { label: 'Incremento Porcentual de FTP', unit: '%', type: 'number', step: '0.1' }
      case 'sesiones_semanales':
        return { label: 'Número de Sesiones Semanales', unit: 'sesiones/sem', type: 'number', step: '1' }
      case 'minutos_semanales':
        return { label: 'Duración Semanal Objetivo', unit: 'minutos/sem', type: 'number', step: '10' }
      case 'semanas_consecutivas':
        return { label: 'Semanas Consecutivas', unit: 'semanas', type: 'number', step: '1' }
      default:
        return { label: '', unit: '', type: 'none' }
    }
  }

  const getUnitForMetric = (mType: string): string | null => {
    switch (mType) {
      case 'completar': return null
      case 'tiempo_maximo': return 'horas'
      case 'velocidad_media': return 'km/h'
      case 'posicion_objetivo': return 'puesto'
      case 'potencia_media': return 'W'
      case 'distancia_total': return 'km'
      case 'duracion_total': return 'minutos'
      case 'ftp_objetivo': return 'W'
      case 'ftp_incremento': return '%'
      case 'sesiones_semanales': return 'sesiones/sem'
      case 'minutos_semanales': return 'minutos/sem'
      case 'semanas_consecutivas': return 'semanas'
      default: return null
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!title.trim() || !targetDate) {
      setMessage('El nombre y la fecha de finalización son obligatorios.')
      return
    }

    if (startDate && targetDate && startDate > targetDate) {
      setMessage('La fecha de inicio no puede ser posterior a la de finalización.')
      return
    }

    setSubmitting(true)
    const payload = {
      title: title.trim(),
      goal_type: goalType,
      sport,
      start_date: startDate || null,
      target_date: targetDate,
      priority,
      target_distance_meters: distKm ? parseFloat(distKm) * 1000 : null,
      target_elevation_meters: elevM ? parseFloat(elevM) : null,
      success_metric_type: successMetricType,
      success_metric_value: successMetricValue ? parseFloat(successMetricValue) : null,
      success_metric_unit: getUnitForMetric(successMetricType),
      details: details.trim() || null,
      is_active: isActive
    }

    const url = goal ? `/goals/${goal.id}` : '/goals'
    const method = goal ? 'PUT' : 'POST'

    const res = await request(url, {
      method,
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    })

    if (res.ok) {
      const savedGoal: Goal = await res.json()
      onSuccess(savedGoal)
      setMessage(goal ? 'Objetivo actualizado correctamente.' : 'Objetivo creado correctamente.')
    } else {
      setMessage(await errorText(res))
    }
    setSubmitting(false)
  }

  const metricConfig = getMetricLabelAndUnit(successMetricType)

  return (
    <form className="form-grid" onSubmit={handleSubmit}>
      <div className="wide" style={{ borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>
        <h3>Sección 1: Detalles del objetivo</h3>
      </div>
      <Input
        label="Nombre del objetivo (Ej. Quebrantahuesos 2027)"
        placeholder="Escribe el nombre del reto o evento..."
        value={title}
        maxLength={120}
        required
        onChange={(e) => setTitle(e.target.value)}
      />
      <div style={{ display: 'block', fontSize: '0.75rem', color: '#888', marginTop: '-0.5rem', gridColumn: '1' }}>
        Caracteres: {title.trim().length} / 120
      </div>

      <label>
        Tipo de objetivo
        <select value={goalType} onChange={(e) => {
          const newType = e.target.value
          setGoalType(newType)
          const allowed = getMetricsForType(newType)
          if (!allowed.includes(successMetricType)) {
            setSuccessMetricType(allowed[0])
            setSuccessMetricValue('')
          }
        }}>
          <option value="sportive">Gran Fondo / Cicloturista</option>
          <option value="race">Carrera competitiva</option>
          <option value="climb">Subida / Puerto específico</option>
          <option value="endurance">Reto de resistencia / distancia</option>
          <option value="ftp_improvement">Mejora de FTP</option>
          <option value="health">Salud y constancia general</option>
        </select>
      </label>

      <label>
        Modalidad ciclista
        <select value={sport} onChange={(e) => setSport(e.target.value)}>
          <option value="cycling_general">Ciclismo general</option>
          <option value="road_cycling">Carretera</option>
          <option value="mountain_biking">MTB / Montaña</option>
          <option value="gravel">Gravel</option>
          <option value="indoor_cycling">Rodillo / Entrenamiento indoor</option>
          <option value="cyclocross">Ciclocross</option>
          <option value="track_cycling">Pista</option>
        </select>
      </label>

      <label>
        Prioridad del objetivo
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="low">Baja (objetivo secundario / entrenamiento)</option>
          <option value="medium">Media (objetivo relevante)</option>
          <option value="high">Alta (objetivo principal que condicionará el plan)</option>
        </select>
      </label>

      <div className="wide" style={{ borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: '0.5rem', marginTop: '1rem', marginBottom: '0.5rem' }}>
        <h3>Sección 2: Resultado esperado y métricas</h3>
      </div>

      <label>
        Métrica de éxito
        <select value={successMetricType} onChange={(e) => setSuccessMetricType(e.target.value)}>
          {getMetricsForType(goalType).map((m) => (
            <option key={m} value={m}>
              {m === 'completar' ? 'Completar el reto' : (
                m === 'tiempo_maximo' ? 'Finalizar en un tiempo límite' : (
                  m === 'velocidad_media' ? 'Velocidad media objetivo' : (
                    m === 'posicion_objetivo' ? 'Posición objetivo de clasificación' : (
                      m === 'potencia_media' ? 'Potencia media objetivo (W)' : (
                        m === 'distancia_total' ? 'Distancia total a recorrer (km)' : (
                          m === 'duracion_total' ? 'Duración total de entrenamiento (min)' : (
                            m === 'ftp_objetivo' ? 'FTP objetivo a alcanzar (W)' : (
                              m === 'ftp_incremento' ? 'Incremento porcentual de FTP (%)' : (
                                m === 'sesiones_semanales' ? 'Número mínimo de sesiones semanales' : (
                                  m === 'minutos_semanales' ? 'Minutos acumulados semanales' : 'Semanas consecutivas cumpliendo'
                                )
                              )
                            )
                          )
                        )
                      )
                    )
                  )
                )
              )}
            </option>
          ))}
        </select>
      </label>

      {metricConfig.type !== 'none' && (
        <label>
          {metricConfig.label} ({metricConfig.unit})
          <input
            type={metricConfig.type}
            step={metricConfig.step}
            min="0.1"
            value={successMetricValue}
            required
            onChange={(e) => setSuccessMetricValue(e.target.value)}
          />
        </label>
      )}

      <div className="wide" style={{ borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: '0.5rem', marginTop: '1rem', marginBottom: '0.5rem' }}>
        <h3>Sección 3: Recorrido y fechas</h3>
      </div>

      <Input
        type="date"
        label="Fecha de inicio de la preparación"
        value={startDate}
        required
        onChange={(e) => setStartDate(e.target.value)}
      />

      <Input
        type="date"
        label="Fecha final / fecha del objetivo"
        value={targetDate}
        required
        onChange={(e) => setTargetDate(e.target.value)}
      />

      {(['sportive', 'race', 'climb', 'endurance'].includes(goalType)) && (
        <>
          <div style={{ display: 'grid', gap: '8px' }}>
            <Input
              type="number"
              step="0.1"
              min="0.1"
              label="Distancia del recorrido (km, Opcional)"
              value={distKm}
              onChange={(e) => setDistKm(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '0.25rem', marginTop: '2px' }}>
              {[50, 100, 160, 200].map((preset) => (
                <button key={preset} type="button" className="secondary" style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '4px' }} onClick={() => setDistKm(preset.toString())}>
                  {preset}k
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gap: '8px' }}>
            <Input
              type="number"
              step="10"
              min="1"
              label="Desnivel del recorrido (m, Opcional)"
              value={elevM}
              onChange={(e) => setElevM(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '0.25rem', marginTop: '2px' }}>
              {[500, 1000, 2000, 3000].map((preset) => (
                <button key={preset} type="button" className="secondary" style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '4px' }} onClick={() => setElevM(preset.toString())}>
                  +{preset}m
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      <label className="wide checkbox" style={{ marginTop: '1rem' }}>
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
        />
        Marcar este objetivo como ACTIVO (Activar este objetivo desactivará automáticamente cualquier otro activo)
      </label>

      <label className="wide">
        Detalles y anotaciones adicionales (Opcional, máx 1000 caracteres)
        <textarea
          value={details}
          maxLength={1000}
          placeholder="Escribe cualquier información del puerto, altimetrías, logística o limitaciones..."
          onChange={(e) => setDetails(e.target.value)}
        />
      </label>
      <div style={{ fontSize: '0.75rem', color: '#888', marginTop: '-0.5rem', gridColumn: '1 / -1' }}>
        Caracteres: {details.length} / 1000
      </div>

      <div className="actions wide" style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
        <button className="primary" type="submit" disabled={submitting}>
          {submitting ? 'Guardando...' : (goal ? 'Guardar Cambios' : 'Crear Objetivo')}
        </button>
        <button className="secondary" type="button" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </form>
  )
}

export function getMetricsForType(type: string): string[] {
  switch (type) {
    case 'sportive':
    case 'race':
      return ['completar', 'tiempo_maximo', 'velocidad_media', 'posicion_objetivo']
    case 'climb':
      return ['completar', 'tiempo_maximo', 'potencia_media']
    case 'endurance':
      return ['completar', 'distancia_total', 'duracion_total']
    case 'ftp_improvement':
      return ['ftp_objetivo', 'ftp_incremento']
    case 'health':
      return ['sesiones_semanales', 'minutos_semanales', 'semanas_consecutivas']
    default:
      return ['completar']
  }
}
