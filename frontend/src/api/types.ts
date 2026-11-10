// Mirrors the Pydantic schemas in backend/app/schemas.py.

export type Mode = 'car' | 'taxi' | 'transit' | 'bike' | 'scooter' | 'walk'
export type Importance = 'low' | 'normal' | 'high'
export type Priority = 'balanced' | 'cheapest' | 'fastest'
export type Language = 'en' | 'pl'
/** arrive: be there by the given time. depart: leave at the given time. */
export type TimeMode = 'arrive' | 'depart'
export type LegKind = 'walk' | 'bus' | 'tram' | 'metro' | 'train' | 'ferry' | 'transit' | 'car' | 'taxi' | 'bike' | 'scooter'
export type LatLon = [number, number]

export interface Profile {
  has_car: boolean
  fuel_consumption_l_per_100km: number
  fuel_price_pln_per_l: number
  has_bike: boolean
  bike_is_electric: boolean
  has_scooter: boolean
  has_transit_pass: boolean
  transit_ticket_price_pln: number
  transit_transfer_ticket_price_pln: number
  taxi_base_fare_pln: number
  taxi_per_km_pln: number
  priority: Priority
}

export interface PlaceInput {
  name: string
  address: string | null
  lat: number
  lon: number
  parking_cost_pln: number
}

export interface Place extends PlaceInput {
  id: number
}

export interface GeocodeResult {
  display_name: string
  lat: number
  lon: number
}

export interface TripInput {
  title: string
  origin_id: number
  destination_id: number
  arrive_by: string // HH:MM
  importance: Importance
  weekdays: number[] // 0 = Monday
  date: string | null // YYYY-MM-DD
}

export interface Trip extends TripInput {
  id: number
  origin: Place
  destination: Place
}

export interface Weather {
  temperature_c: number
  precipitation_mm: number
  precipitation_probability: number | null
  wind_kmh: number
}

/** One continuous part of a route: a walk, a ride on one line, a drive. */
export interface Leg {
  kind: LegKind
  line: string | null
  headsign: string | null
  color: string | null
  from_name: string | null // null = the journey's own origin
  to_name: string | null // null = the journey's own destination
  depart: string | null
  arrive: string | null
  minutes: number
  distance_km: number | null
  stops: number | null
  geometry: LatLon[]
}

/** One concrete way of making the journey, e.g. "bus 168" or "bike, route 2". */
export interface RouteOption {
  id: string
  mode: Mode
  label: string | null
  estimated: boolean
  depart_at: string
  arrive_at: string
  arrive_worst: string
  typical_minutes: number
  worst_minutes: number
  buffer_minutes: number
  cost_pln: number
  distance_km: number | null
  ascent_m: number | null
  transfers: number | null
  reliability: 'stable' | 'variable' | 'unpredictable'
  too_late: boolean
  risky: boolean
  score: number
  tags: string[]
  warnings: string[]
  legs: Leg[]
  elevation_profile: [number, number][] // (km, metres)
}

export interface BackupPlan {
  option_id: string
  mode: Mode
  label: string | null
  board_stop: string | null
  depart_at: string
  decide_by: string
  commit_early: boolean
}

export interface Point {
  name: string
  lat: number
  lon: number
}

export interface JourneyRequest {
  origin: Point
  destination: Point
  time: string
  time_mode: TimeMode
  importance: Importance
  parking_cost_pln: number
}

export interface JourneyPlan {
  origin: Point
  destination: Point
  time: string
  time_mode: TimeMode
  importance: Importance
  distance_km: number
  transit_source: 'timetable' | 'estimate'
  congestion: number
  weather: Weather | null
  status: 'ok' | 'late' | 'past'
  late_by_minutes: number | null
  recommended: string
  backup: BackupPlan | null
  options: RouteOption[]
}

export interface TripPlan extends JourneyPlan {
  trip_id: number
  title: string
}

export interface DayPlan {
  date: string
  trips: TripPlan[]
}

export interface WeekSummary {
  trips_count: number
  recommended_cost_pln: number
  car_only_cost_pln: number | null
  travel_minutes: number
  commit_early_count: number
}

export interface WeekPlan {
  start: string
  days: DayPlan[]
  summary: WeekSummary
}

export interface TrafficPoint {
  hour: number
  factor: number
}

export interface Advice {
  source: 'ai' | 'rules'
  text: string
}
