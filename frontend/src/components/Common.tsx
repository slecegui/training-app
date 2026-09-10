import React from 'react'

export function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, ...inputProps } = props
  return (
    <label style={{ display: 'grid', gap: '7px', fontSize: '.86rem', fontWeight: 700 }}>
      {label}
      <input {...inputProps} style={{ width: '100%', border: '1px solid #cbd2c8', borderRadius: '9px', padding: '11px 12px', background: '#fbfcf8', color: '#17251e' }} />
    </label>
  )
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
