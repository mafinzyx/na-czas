import { useEffect, useRef, useState } from 'react'

import { searchAddress } from '../api/hooks'
import type { GeocodeResult, Place, Point } from '../api/types'
import { useI18n } from '../i18n'

const SEARCH_DELAY_MS = 500
const MIN_QUERY_LENGTH = 3

interface Props {
  label: string
  marker: 'A' | 'B'
  value: Point | null
  onChange: (point: Point) => void
  places: Place[]
  /** True while the map is waiting for a click for this field. */
  picking: boolean
  onTogglePick: () => void
}

/** "Where from / where to" field: saved places, address search, or a click on the map. */
export function LocationInput({ label, marker, value, onChange, places, picking, onTogglePick }: Props) {
  const { t } = useI18n()
  const inputRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState<GeocodeResult[]>([])
  const [searching, setSearching] = useState(false)

  const query = text.trim()

  // Address search starts on its own shortly after the user stops typing.
  useEffect(() => {
    if (!open || query.length < MIN_QUERY_LENGTH) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const found = await searchAddress(query)
        if (!cancelled) setResults(found)
      } catch {
        if (!cancelled) setResults([])
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, SEARCH_DELAY_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [open, query])

  const choose = (point: Point) => {
    onChange(point)
    setOpen(false)
    inputRef.current?.blur()
  }

  const matchingPlaces = places.filter((place) =>
    `${place.name} ${place.address ?? ''}`.toLowerCase().includes(query.toLowerCase()),
  )
  const addresses = query.length >= MIN_QUERY_LENGTH ? results : []

  return (
    <div className="location-input">
      <span className={`map-pin map-pin-${marker === 'A' ? 'origin' : 'destination'}`} aria-hidden="true">
        {marker}
      </span>
      <div className="location-field">
        <input
          ref={inputRef}
          aria-label={label}
          placeholder={label}
          value={open ? text : (value?.name ?? '')}
          onChange={(event) => setText(event.target.value)}
          onFocus={() => {
            setText('')
            setOpen(true)
          }}
          // Delayed so that a click on a suggestion is registered first.
          onBlur={() => setTimeout(() => setOpen(false), 150)}
        />
        {open && (
          <ul className="suggestions">
            {matchingPlaces.map((place) => (
              <li key={`place-${place.id}`}>
                <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => choose(place)}>
                  <strong>⭐ {place.name}</strong>
                  {place.address && <small className="muted">{place.address}</small>}
                </button>
              </li>
            ))}
            {addresses.map((result) => (
              <li key={`${result.lat},${result.lon}`}>
                <button
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose({ name: result.display_name, lat: result.lat, lon: result.lon })}
                >
                  📍 {result.display_name}
                </button>
              </li>
            ))}
            {searching && <li className="suggestion-note">{t('common.loading')}</li>}
            {!searching && matchingPlaces.length === 0 && addresses.length === 0 && (
              <li className="suggestion-note">{t('search.typeAddress')}</li>
            )}
          </ul>
        )}
      </div>
      <button
        type="button"
        className={`btn btn-small ${picking ? 'btn-primary' : ''}`}
        onClick={onTogglePick}
        aria-pressed={picking}
        title={t('search.pickOnMap')}
      >
        🗺
      </button>
    </div>
  )
}
