import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'

import type { Leg, Point, RouteOption } from '../api/types'
import { clockTime } from '../lib/format'
import { DEFAULT_MAP_CENTER, LEG_COLOR } from '../lib/modes'

interface Props {
  origin: Point | null
  destination: Point | null
  /** The route drawn in full colour. */
  option: RouteOption | null
  /** Other variants of the same mode, drawn faintly for comparison. */
  alternatives: RouteOption[]
  /** While true, the next click reports a point instead of panning. */
  picking: boolean
  onPick: (lat: number, lon: number) => void
}

function endpointIcon(letter: string, className: string): L.DivIcon {
  return L.divIcon({ className: '', html: `<span class="map-pin ${className}">${letter}</span>`, iconSize: [28, 28], iconAnchor: [14, 14] })
}

function legColor(leg: Leg): string {
  return leg.color ?? LEG_COLOR[leg.kind]
}

function drawOption(option: RouteOption, layer: L.LayerGroup): void {
  for (const leg of option.legs) {
    if (leg.geometry.length < 2) continue
    const walking = leg.kind === 'walk'
    // A white casing underneath keeps the line readable on a busy map.
    if (!walking) L.polyline(leg.geometry, { color: '#ffffff', weight: 9, opacity: 0.9 }).addTo(layer)
    L.polyline(leg.geometry, {
      color: legColor(leg),
      weight: walking ? 4 : 5,
      dashArray: walking ? '1 8' : undefined,
    }).addTo(layer)
  }

  // Stops where you board, change and get off.
  for (const leg of option.legs) {
    if (leg.kind === 'walk' || leg.geometry.length < 2 || !leg.depart || !leg.arrive) continue
    const stops: [typeof leg.geometry[number], string][] = [
      [leg.geometry[0], `${leg.line ?? ''} · ${leg.from_name ?? ''} ${clockTime(leg.depart)}`],
      [leg.geometry[leg.geometry.length - 1], `${leg.to_name ?? ''} ${clockTime(leg.arrive)}`],
    ]
    for (const [position, text] of stops) {
      L.circleMarker(position, { radius: 6, color: legColor(leg), weight: 3, fillColor: '#ffffff', fillOpacity: 1 })
        .bindTooltip(text.trim(), { direction: 'top', offset: [0, -6] })
        .addTo(layer)
    }
  }
}

/** The main map: the selected route with its stops, the two endpoints, and click-to-pick. */
export function RouteMap({ origin, destination, option, alternatives, picking, onPick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)
  const pickRef = useRef({ picking, onPick })
  useEffect(() => {
    pickRef.current = { picking, onPick }
  }, [picking, onPick])

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current).setView(DEFAULT_MAP_CENTER, 12)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map)
    map.on('click', (event) => {
      if (pickRef.current.picking) pickRef.current.onPick(event.latlng.lat, event.latlng.lng)
    })
    mapRef.current = map
    layerRef.current = L.layerGroup().addTo(map)

    return () => {
      map.remove()
      mapRef.current = null
      layerRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()

    for (const other of alternatives) {
      for (const leg of other.legs) {
        if (leg.geometry.length >= 2) L.polyline(leg.geometry, { color: '#94a3b8', weight: 4, opacity: 0.7 }).addTo(layer)
      }
    }
    if (option) drawOption(option, layer)

    if (origin) L.marker([origin.lat, origin.lon], { icon: endpointIcon('A', 'map-pin-origin') }).bindTooltip(origin.name).addTo(layer)
    if (destination) {
      L.marker([destination.lat, destination.lon], { icon: endpointIcon('B', 'map-pin-destination') })
        .bindTooltip(destination.name)
        .addTo(layer)
    }

    const points: L.LatLngTuple[] = []
    if (origin) points.push([origin.lat, origin.lon])
    if (destination) points.push([destination.lat, destination.lon])
    for (const leg of option?.legs ?? []) points.push(...leg.geometry)

    if (points.length >= 2) {
      map.fitBounds(L.latLngBounds(points), { padding: [36, 36] })
    } else if (points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 14))
    }
  }, [origin, destination, option, alternatives])

  return <div ref={containerRef} className={`route-map ${picking ? 'is-picking' : ''}`} />
}
