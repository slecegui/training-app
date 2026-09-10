import { FormEvent, useEffect, useState } from 'react'
import { request, formatPairs, pairs, jsonHeaders, errorText } from '../utils'
import { Input } from '../components/Common'

interface Profile {
  sports: string[]
  experience_level: string | null
  availability: Record<string, number>
  power_zones: Record<string, number>
  heart_rate_zones: Record<string, number>
  preferences: Record<string, string | number | boolean>
  injuries_or_constraints: string | null
}

const emptyProfile: Profile = {
  sports: [],
  experience_level: null,
  availability: {},
  power_zones: {},
  heart_rate_zones: {},
  preferences: {},
  injuries_or_constraints: null
}

interface ProfilePageProps {
  setMessage: (value: string) => void
}

export function ProfilePage({ setMessage }: ProfilePageProps) {
  const [profile, setProfile] = useState<Profile>(emptyProfile)
  const [availability, setAvailability] = useState('')
  const [power, setPower] = useState('')
  const [heartRate, setHeartRate] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Fetch profile on load
  useEffect(() => {
    void request('/profile').then(async (response) => {
      if (response.ok) {
        const data: Profile = await response.json()
        setProfile(data)
        setAvailability(formatPairs(data.availability))
        setPower(formatPairs(data.power_zones))
        setHeartRate(formatPairs(data.heart_rate_zones))
      } else {
        setMessage(await errorText(response))
      }
    })
  }, [setMessage])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)

    const response = await request('/profile', {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify({
        ...profile,
        availability: pairs(availability),
        power_zones: pairs(power),
        heart_rate_zones: pairs(heartRate)
      })
    })

    if (response.ok) {
      setMessage('Perfil deportivo guardado correctamente.')
    } else {
      setMessage(await errorText(response))
    }
    setSubmitting(false)
  }

  return (
    <>
      <header style={{ marginBottom: '2rem' }}>
        <div>
          <p className="eyebrow">CONFIGURACIÓN DE ATLETA</p>
          <h1>Tu Perfil Deportivo</h1>
          <p className="subtitle">Configura tus preferencias, zonas e intervalos de disponibilidad de entrenamiento.</p>
        </div>
      </header>

      <section className="panel" style={{ background: 'var(--bg-card)', padding: '2rem' }}>
        <h2>Perfil deportivo</h2>
        <p className="subtitle" style={{ marginBottom: '1.5rem' }}>
          Disponibilidad en minutos de lunes a domingo (mon..sun) y zonas de potencia o FC con formato estándar “z2: 180, z3: 220”.
        </p>

        <form className="form-grid" onSubmit={submit}>
          <Input
            label="Deportes practicados (separados por coma)"
            value={profile.sports.join(', ')}
            onChange={(event) => setProfile({
              ...profile,
              sports: event.target.value.split(',').map((item) => item.trim()).filter(Boolean)
            })}
          />

          <Input
            label="Nivel deportivo (Ej. Beginner, Intermediate, Advanced)"
            value={profile.experience_level ?? ''}
            onChange={(event) => setProfile({ ...profile, experience_level: event.target.value || null })}
          />

          <Input
            label="Disponibilidad semanal (mon: 60, wed: 90, sat: 180)"
            placeholder="mon: 60, tue: 45, wed: 90..."
            value={availability}
            onChange={(event) => setAvailability(event.target.value)}
          />

          <Input
            label="Zonas de potencia (en vatios)"
            placeholder="z1: 120, z2: 150, z4: 220..."
            value={power}
            onChange={(event) => setPower(event.target.value)}
          />

          <Input
            label="Zonas de frecuencia cardiaca (en ppm)"
            placeholder="z1: 110, z2: 130, z4: 160..."
            value={heartRate}
            onChange={(event) => setHeartRate(event.target.value)}
          />

          <label className="checkbox" style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={profile.preferences.has_power_meter === true}
              onChange={(event) => setProfile({
                ...profile,
                preferences: { ...profile.preferences, has_power_meter: event.target.checked }
              })}
            />
            Poseo potenciómetro en mi bicicleta principal (Métrica de potencia disponible)
          </label>

          <label className="checkbox" style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={profile.preferences.indoor === true}
              onChange={(event) => setProfile({
                ...profile,
                preferences: { ...profile.preferences, indoor: event.target.checked }
              })}
            />
            Acepto sesiones de rodillo / indoor trainer
          </label>

          <label className="wide">
            Limitaciones, dolores o lesiones activas (Opcional)
            <textarea
              value={profile.injuries_or_constraints ?? ''}
              onChange={(event) => setProfile({ ...profile, injuries_or_constraints: event.target.value || null })}
              style={{ minHeight: '100px', resize: 'vertical' }}
            />
          </label>

          <div style={{ marginTop: '1.5rem', gridColumn: '1 / -1' }}>
            <button className="primary" type="submit" disabled={submitting}>
              {submitting ? 'Guardando...' : 'Guardar Perfil Deportivo'}
            </button>
          </div>
        </form>
      </section>
    </>
  )
}
