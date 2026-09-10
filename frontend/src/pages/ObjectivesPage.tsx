import { useEffect, useState } from 'react'
import { Goal } from '../types'
import { request, useLocation, errorText } from '../utils'

interface ObjectivesPageProps {
  setMessage: (value: string) => void
}

export function ObjectivesPage({ setMessage }: ObjectivesPageProps) {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [, navigate] = useLocation()

  useEffect(() => {
    void request('/goals')
      .then(async (res) => {
        if (res.ok) {
          setGoals(await res.json())
        } else {
          setMessage(await errorText(res))
        }
      })
      .finally(() => setLoading(false))
  }, [setMessage])

  const translateType = (type: string) => {
    const types: Record<string, string> = {
      sportive: 'Gran Fondo',
      race: 'Carrera',
      climb: 'Subida',
      endurance: 'Resistencia',
      ftp_improvement: 'Mejora de FTP',
      health: 'Salud y Constancia'
    }
    return types[type] || type
  }

  const translateSport = (s: string) => {
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

  const getPriorityBadgeColor = (p: string) => {
    switch (p) {
      case 'high': return '#c62828'
      case 'medium': return '#ef6c00'
      default: return '#2e7d32'
    }
  }

  // Filter goals
  const filteredGoals = goals.filter((g) => {
    if (filterActive === 'active') return g.is_active
    if (filterActive === 'inactive') return !g.is_active
    return true
  })

  if (loading) {
    return <section className="panel"><h2>Cargando tus objetivos…</h2></section>
  }

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">OBJETIVOS DE TRABAJO</p>
          <h1>Tus Objetivos</h1>
          <p className="subtitle">Selecciona un objetivo para acceder a su plan de entrenamiento y actividades asociadas.</p>
        </div>
        <button className="primary" type="button" onClick={() => navigate('/objectives/new')}>
          ➕ Nuevo Objetivo
        </button>
      </header>

      {/* Filters bar */}
      <div className="panel" style={{ display: 'flex', gap: '1rem', alignItems: 'center', background: 'var(--bg-card)', padding: '1rem', marginBottom: '1.5rem' }}>
        <strong>Filtrar por estado:</strong>
        <nav style={{ display: 'flex', gap: '0.5rem', borderBottom: 'none', marginBottom: 0 }}>
          <button className={filterActive === 'all' ? 'active' : ''} style={{ padding: '6px 12px', borderBottom: 'none' }} onClick={() => setFilterActive('all')}>
            Todos
          </button>
          <button className={filterActive === 'active' ? 'active' : ''} style={{ padding: '6px 12px', borderBottom: 'none' }} onClick={() => setFilterActive('active')}>
            Activos
          </button>
          <button className={filterActive === 'inactive' ? 'active' : ''} style={{ padding: '6px 12px', borderBottom: 'none' }} onClick={() => setFilterActive('inactive')}>
            Inactivos
          </button>
        </nav>
      </div>

      <section className="panel goals-table-wrap">
        {filteredGoals.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>
            Aún no tienes objetivos en esta sección. ¡Crea uno nuevo para comenzar!
          </div>
        ) : (
          <table className="goals-table">
            <thead>
              <tr>
                <th style={{ padding: '12px 16px' }}>Nombre</th>
                <th style={{ padding: '12px 16px' }}>Tipo</th>
                <th style={{ padding: '12px 16px' }}>Modalidad</th>
                <th style={{ padding: '12px 16px' }}>Inicio de prep.</th>
                <th style={{ padding: '12px 16px' }}>Fecha límite</th>
                <th style={{ padding: '12px 16px', textAlign: 'center' }}>Prioridad</th>
                <th style={{ padding: '12px 16px', textAlign: 'center' }}>Estado</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {filteredGoals.map((g) => (
                <tr key={g.id} onClick={() => navigate(`/objectives/${g.id}`)}>
                  <td data-label="Nombre">{g.title}</td><td data-label="Tipo">{translateType(g.goal_type)}</td><td data-label="Modalidad">{translateSport(g.sport)}</td>
                  <td data-label="Inicio de preparación">{g.start_date ? new Date(g.start_date + 'T00:00:00').toLocaleDateString('es-ES') : '—'}</td>
                  <td data-label="Fecha límite">{g.target_date ? new Date(g.target_date + 'T00:00:00').toLocaleDateString('es-ES') : '—'}</td>
                  <td data-label="Prioridad" style={{ padding: '16px', textAlign: 'center' }}>
                    <span className="badge" style={{ color: '#fff', background: getPriorityBadgeColor(g.priority), padding: '2px 6px', borderRadius: '4px' }}>
                      {g.priority === 'high' ? 'Alta' : (g.priority === 'medium' ? 'Media' : 'Baja')}
                    </span>
                  </td>
                  <td data-label="Estado" style={{ padding: '16px', textAlign: 'center' }}>
                    <span className="badge" style={{ color: '#fff', background: g.is_active ? 'var(--primary)' : '#666', padding: '2px 6px', borderRadius: '4px' }}>
                      {g.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td data-label="Acción" style={{ padding: '16px', textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                    <button className="secondary" style={{ padding: '6px 12px', fontSize: '0.85rem' }} onClick={() => navigate(`/objectives/${g.id}`)}>
                      Ver espacio ➔
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
