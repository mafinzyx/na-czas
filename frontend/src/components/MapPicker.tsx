import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'

import { DEFAULT_MAP_CENTER } from '../lib/modes'

interface Props {
  position: { lat: number; lon: number } | null
  onPick: (lat: number, lon: number) => void
}

/** Small map for forms: shows the chosen point and lets the user pick one by clicking. */
export function MapPicker({ position, onPick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.CircleMarker | null>(null)
  // Keeps the latest callback without re-creating the map on every render.
  const onPickRef = useRef(onPick)
  useEffect(() => {
    onPickRef.current = onPick
  }, [onPick])

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current).setView(DEFAULT_MAP_CENTER, 12)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map)
    map.on('click', (event) => onPickRef.current(event.latlng.lat, event.latlng.lng))
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !position) return
    const point: L.LatLngTuple = [position.lat, position.lon]

    if (markerRef.current) {
      markerRef.current.setLatLng(point)
    } else {
      markerRef.current = L.circleMarker(point, { radius: 9, color: '#0f766e', fillOpacity: 0.6 }).addTo(map)
    }
    map.setView(point, Math.max(map.getZoom(), 14))
  }, [position])

  return <div ref={containerRef} className="map" />
}
