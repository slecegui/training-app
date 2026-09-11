export type IconName =
  | 'home'
  | 'target'
  | 'activity'
  | 'profile'
  | 'edit'
  | 'trash'
  | 'route'
  | 'calendar'
  | 'upload'
  | 'plus'
  | 'check'
  | 'menu'
  | 'chevron-left'

const paths: Record<IconName, string> = {
  home: 'M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z',
  target: 'M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2zm1 5h-2v4H7v2h4v4h2v-4h4v-2h-4V7z',
  activity: 'M20 2H4C3 2 2 2.9 2 4v3.01c0 .72.43 1.34 1 1.69V20c0 1.1 1.1 2 2 2h14c.9 0 2-.9 2-2V8.7c.57-.35 1-.97 1-1.69V4c0-1.1-.9-2-2-2m-5 12H9v-2h6zm5-7H4V4h16z',
  profile: 'M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10m0 2c-4.42 0-8 2.24-8 5v3h16v-3c0-2.76-3.58-5-8-5z',
  edit: 'M4 17.25V20h2.75L16.81 9.94l-2.75-2.75L4 17.25zM19.71 7.04a1 1 0 0 0 0-1.41l-1.34-1.34a1 1 0 0 0-1.41 0l-1.08 1.08 2.75 2.75 1.08-1.08z',
  trash: 'M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM8 9h8v10H8V9zm7.5-5-1-1h-5l-1 1H5v2h14V4z',
  route: 'M7 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm10 8a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM8.3 10.4l7.4 3.2.8-1.8-7.4-3.2-.8 1.8z',
  calendar: 'M7 2h2v2h6V2h2v2h3v18H4V4h3V2zm-1 8v10h12V10H6zm2 3h2v2H8v-2zm4 0h2v2h-2v-2z',
  upload: 'M11 16h2V8l3 3 1.4-1.4L12 4.2 6.6 9.6 8 11l3-3v8zM5 18h14v2H5v-2z',
  plus: 'M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z',
  check: 'm9 16.2-3.5-3.5L4 14.2l5 5 11-11-1.4-1.4z',
  menu: 'M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z',
  'chevron-left': 'm15.5 5-7 7 7 7 1.4-1.4-5.6-5.6 5.6-5.6L15.5 5z',
}

interface IconProps {
  name: IconName
  className?: string
}

export function Icon({ name, className = 'app-icon' }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  )
}
