import type { Place, Point } from '../api/types'

/** The saved place at exactly this point, if there is one. */
export function findPlace(places: Place[], point: Point): Place | undefined {
  return places.find((place) => place.lat === point.lat && place.lon === point.lon)
}

/** What the search screen needs to be opened with a journey already filled in. */
export interface SearchPreset {
  origin: Point
  destination: Point
  date: string // YYYY-MM-DD
  time: string // HH:MM
  timeMode: 'arrive' | 'depart'
  importance: 'low' | 'normal' | 'high'
}
