import type { SVGProps } from 'react'

const baseProps: SVGProps<SVGSVGElement> = {
  viewBox: '0 0 24 24',
  width: 18,
  height: 18,
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export function CogIcon() {
  return (
    <svg {...baseProps}>
      <circle cx="12" cy="12" r="3" />
      <line x1="12" y1="4" x2="12" y2="7" />
      <line x1="12" y1="17" x2="12" y2="20" />
      <line x1="4" y1="12" x2="7" y2="12" />
      <line x1="17" y1="12" x2="20" y2="12" />
      <line x1="6" y1="6" x2="8" y2="8" />
      <line x1="18" y1="6" x2="16" y2="8" />
      <line x1="6" y1="18" x2="8" y2="16" />
      <line x1="18" y1="18" x2="16" y2="16" />
    </svg>
  )
}

export function SunIcon() {
  return (
    <svg {...baseProps}>
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

export function MoonIcon() {
  return (
    <svg {...baseProps}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

export function MenuIcon() {
  return (
    <svg {...baseProps}>
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

export function CloseIcon() {
  return (
    <svg {...baseProps}>
      <line x1="5" y1="5" x2="19" y2="19" />
      <line x1="19" y1="5" x2="5" y2="19" />
    </svg>
  )
}
