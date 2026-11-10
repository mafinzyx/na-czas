// React Query hooks: every server resource is read and changed through these.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { localIsoDateTime } from '../lib/format'
import { api } from './client'
import type {
  Advice,
  GeocodeResult,
  JourneyPlan,
  JourneyRequest,
  Language,
  Place,
  PlaceInput,
  Profile,
  TrafficPoint,
  Trip,
  TripInput,
  WeekPlan,
} from './types'

const keys = {
  places: ['places'] as const,
  trips: ['trips'] as const,
  profile: ['profile'] as const,
  plan: ['plan'] as const,
}

/** Any change to places, trips or the profile changes the calculated plans. */
function useInvalidate(key: readonly string[]) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: key })
    void queryClient.invalidateQueries({ queryKey: keys.plan })
  }
}

// --- Places ---

export function usePlaces() {
  return useQuery({ queryKey: keys.places, queryFn: () => api.get<Place[]>('/api/places') })
}

export function createPlace(data: PlaceInput) {
  return api.post<Place>('/api/places', data)
}

export function useSavePlace() {
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: PlaceInput }) =>
      id === undefined ? createPlace(data) : api.put<Place>(`/api/places/${id}`, data),
    onSuccess: useInvalidate(keys.places),
  })
}

export function useDeletePlace() {
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/places/${id}`),
    onSuccess: useInvalidate(keys.places),
  })
}

export function searchAddress(query: string) {
  return api.get<GeocodeResult[]>(`/api/places/search?q=${encodeURIComponent(query)}`)
}

// --- Trips ---

export function useTrips() {
  return useQuery({ queryKey: keys.trips, queryFn: () => api.get<Trip[]>('/api/trips') })
}

export function createTrip(data: TripInput) {
  return api.post<Trip>('/api/trips', data)
}

export function useSaveTrip() {
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: TripInput }) =>
      id === undefined ? createTrip(data) : api.put<Trip>(`/api/trips/${id}`, data),
    onSuccess: useInvalidate(keys.trips),
  })
}

export function useDeleteTrip() {
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/trips/${id}`),
    onSuccess: useInvalidate(keys.trips),
  })
}

/** Invalidates everything a newly saved trip (and its places) can affect. */
export function useRefreshAfterSavingTrip() {
  const queryClient = useQueryClient()
  return () => {
    for (const key of [keys.places, keys.trips, keys.plan]) {
      void queryClient.invalidateQueries({ queryKey: key })
    }
  }
}

// --- Profile ---

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => api.get<Profile>('/api/profile') })
}

export function useSaveProfile() {
  return useMutation({
    mutationFn: (data: Profile) => api.put<Profile>('/api/profile', data),
    onSuccess: useInvalidate(keys.profile),
  })
}

// --- Plans ---

/** Compares all ways of making one journey. Runs as soon as a complete request exists. */
export function useJourney(request: JourneyRequest | null) {
  return useQuery({
    queryKey: [...keys.plan, 'journey', request],
    // The client's clock decides which departures are already too late.
    queryFn: () => api.post<JourneyPlan>('/api/plan/journey', { ...request, now: localIsoDateTime(new Date()) }),
    enabled: request !== null,
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useWeekPlan(start: string) {
  return useQuery({
    queryKey: [...keys.plan, 'week', start],
    queryFn: () => api.get<WeekPlan>(`/api/plan/week?start=${start}&now=${localIsoDateTime(new Date())}`),
    refetchInterval: 5 * 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useTrafficCurve(day: string) {
  return useQuery({
    queryKey: [...keys.plan, 'traffic', day],
    queryFn: () => api.get<TrafficPoint[]>(`/api/plan/traffic?day=${day}`),
    staleTime: Infinity,
  })
}

export function useAdvice() {
  return useMutation({
    mutationFn: ({ start, language }: { start: string; language: Language }) =>
      api.post<Advice>('/api/plan/advice', { start, language, now: localIsoDateTime(new Date()) }),
  })
}
