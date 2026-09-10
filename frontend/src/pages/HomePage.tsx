import { User } from '../types'
import { useLocation } from '../utils'

export function HomePage({ user }: { user: User }) {
  const [, navigate] = useLocation()
  const cards = [['Objetivos', 'Define tu reto y consulta su planificación.', '/objectives'], ['Actividades', 'Importa y revisa tus entrenamientos.', '/activities'], ['Planificación', 'Genera el siguiente plan desde tu objetivo activo.', '/objectives'], ['Perfil', 'Ajusta disponibilidad, zonas y preferencias.', '/profile']]
  return <div className="home-page"><section className="cycling-hero"><p className="eyebrow">TU ESPACIO DE ENTRENAMIENTO</p><h1>Hola, {user.name}</h1><p>Organiza tus objetivos y transforma cada salida en una planificación ciclista trazable.</p></section><section><div className="section-title"><div><p className="eyebrow">ACCESO RÁPIDO</p><h2>Continúa tu planificación</h2></div></div><div className="quick-grid">{cards.map(([title, copy, target]) => <button className="quick-card" key={title} onClick={() => navigate(target)}><span className="quick-icon" aria-hidden="true">↗</span><h3>{title}</h3><p>{copy}</p><span>Ir a {title}</span></button>)}</div></section></div>
}
