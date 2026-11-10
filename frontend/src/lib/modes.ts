import type { LegKind, Mode } from '../api/types'

export const MODE_ICON: Record<Mode, string> = {
  car: '🚗',
  taxi: '🚕',
  transit: '🚌',
  bike: '🚲',
  scooter: '🛴',
  walk: '🚶',
}

export const LEG_ICON: Record<LegKind, string> = {
  walk: '🚶',
  bus: '🚌',
  tram: '🚋',
  metro: '🚇',
  train: '🚆',
  ferry: '⛴',
  transit: '🚌',
  car: '🚗',
  taxi: '🚕',
  bike: '🚲',
  scooter: '🛴',
}

/** Line colours on the map and on line badges, used when the timetable defines none. */
export const LEG_COLOR: Record<LegKind, string> = {
  walk: '#334155',
  bus: '#2563eb',
  tram: '#dc2626',
  metro: '#7c3aed',
  train: '#ea580c',
  ferry: '#0891b2',
  transit: '#2563eb',
  car: '#334155',
  taxi: '#ca8a04',
  bike: '#16a34a',
  scooter: '#9333ea',
}

/** Where the map starts before any place is known. */
export const DEFAULT_MAP_CENTER: [number, number] = [54.372, 18.61] // Gdańsk
