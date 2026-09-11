import { useState } from 'react'
import { useLocation } from '../utils'
import { Icon as SharedIcon } from './Icon'
interface SidebarProps { userName: string }
type IconName = 'home' | 'target' | 'activity' | 'profile'
function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, string> = { home: 'M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z', target: 'M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2zm1 5h-2v4H7v2h4v4h2v-4h4v-2h-4V7z', activity: 'M20 2H4C3 2 2 2.9 2 4v3.01c0 .72.43 1.34 1 1.69V20c0 1.1 1.1 2 2 2h14c.9 0 2-.9 2-2V8.7c.57-.35 1-.97 1-1.69V4c0-1.1-1-2-2-2m-5 12H9v-2h6zm5-7H4V4h16z', profile: 'M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10m0 2c-4.42 0-8 2.24-8 5v3h16v-3c0-2.76-3.58-5-8-5z' }
  return <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d={paths[name]} /></svg>
}
export function Sidebar({ userName }: SidebarProps) {
  const [path, navigate] = useLocation(); const [collapsed, setCollapsed] = useState(false); const [mobileOpen, setMobileOpen] = useState(false)
  const links: readonly [string, string, IconName][] = [['/home', 'Inicio', 'home'], ['/objectives', 'Objetivos', 'target'], ['/activities', 'Actividades', 'activity'], ['/profile', 'Perfil', 'profile']]
  const active = (target: string) => target === '/objectives' ? path.startsWith('/objectives') : path === target
  const go = (target: string) => { navigate(target); setMobileOpen(false) }
  return <><button className="mobile-menu-toggle" aria-label="Abrir navegación" aria-expanded={mobileOpen} onClick={() => setMobileOpen(!mobileOpen)}><SharedIcon name="menu" /></button><aside className={`sidebar ${collapsed ? 'is-collapsed' : ''} ${mobileOpen ? 'is-open' : ''}`}><div className="sidebar-brand"><span className="brand-mark">T</span><strong>Training Online</strong><button className="collapse-toggle" aria-label="Contraer navegación" onClick={() => setCollapsed(!collapsed)}><SharedIcon name="chevron-left" /></button></div><div className="user-card"><span className="avatar">{userName.trim().slice(0, 1).toUpperCase() || 'U'}</span><span className="user-copy"><strong>{userName}</strong><small>Plan ciclista personal</small></span></div><nav aria-label="Navegación principal">{links.map(([target, label, icon]) => <button key={target} className={active(target) ? 'active' : ''} aria-current={active(target) ? 'page' : undefined} onClick={() => go(target)}><span className="nav-icon"><Icon name={icon} /></span><span>{label}</span></button>)}</nav></aside>{mobileOpen && <button className="sidebar-backdrop" aria-label="Cerrar navegación" onClick={() => setMobileOpen(false)} />}</>
}
