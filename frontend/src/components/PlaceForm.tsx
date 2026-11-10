import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

import { searchAddress, useSavePlace } from '../api/hooks'
import type { GeocodeResult, Place } from '../api/types'
import { useI18n } from '../i18n'
import { MapPicker } from './MapPicker'
import { ErrorNote } from './ui'

type SearchState = { status: 'idle' | 'loading' | 'failed' } | { status: 'done'; results: GeocodeResult[] }

export function PlaceForm({ place, onDone }: { place?: Place; onDone: () => void }) {
  const { t } = useI18n()
  const save = useSavePlace()

  const [name, setName] = useState(place?.name ?? '')
  const [address, setAddress] = useState(place?.address ?? '')
  const [position, setPosition] = useState(place ? { lat: place.lat, lon: place.lon } : null)
  const [parking, setParking] = useState(place?.parking_cost_pln ?? 0)
  const [search, setSearch] = useState<SearchState>({ status: 'idle' })
  const [missingLocation, setMissingLocation] = useState(false)

  const runSearch = async () => {
    if (address.trim().length < 3) return
    setSearch({ status: 'loading' })
    try {
      setSearch({ status: 'done', results: await searchAddress(address.trim()) })
    } catch {
      setSearch({ status: 'failed' })
    }
  }

  const onSearchKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return
    event.preventDefault() // Enter searches instead of submitting the whole form
    void runSearch()
  }

  const pickResult = (result: GeocodeResult) => {
    setAddress(result.display_name)
    setPosition({ lat: result.lat, lon: result.lon })
    setSearch({ status: 'idle' })
    setMissingLocation(false)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!position) {
      setMissingLocation(true)
      return
    }
    save.mutate(
      {
        id: place?.id,
        data: {
          name: name.trim(),
          address: address.trim().slice(0, 255) || null,
          lat: position.lat,
          lon: position.lon,
          parking_cost_pln: parking,
        },
      },
      { onSuccess: onDone },
    )
  }

  return (
    <form className="form" onSubmit={submit}>
      <label>
        {t('places.field.name')}
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t('places.field.name.placeholder')}
          maxLength={80}
          required
          autoFocus
        />
      </label>

      <label>
        {t('places.field.search')}
        <div className="input-row">
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            onKeyDown={onSearchKey}
            placeholder={t('places.field.search.placeholder')}
          />
          <button type="button" className="btn" onClick={runSearch} disabled={search.status === 'loading'}>
            {search.status === 'loading' ? t('common.loading') : t('places.search')}
          </button>
        </div>
      </label>

      {search.status === 'failed' && <p className="field-error">{t('places.search.failed')}</p>}
      {search.status === 'done' && search.results.length === 0 && (
        <p className="field-error">{t('places.search.empty')}</p>
      )}
      {search.status === 'done' && search.results.length > 0 && (
        <ul className="search-results">
          {search.results.map((result) => (
            <li key={`${result.lat},${result.lon}`}>
              <button type="button" onClick={() => pickResult(result)}>
                {result.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div>
        <MapPicker
          position={position}
          onPick={(lat, lon) => {
            setPosition({ lat, lon })
            setMissingLocation(false)
          }}
        />
        <small className="muted">{t('places.map.hint')}</small>
        {missingLocation && <p className="field-error">{t('places.error.noLocation')}</p>}
      </div>

      <label>
        {t('places.field.parking')}
        <input
          type="number"
          min={0}
          max={500}
          step={0.5}
          value={parking}
          onChange={(event) => setParking(Number(event.target.value))}
        />
        <small className="muted">{t('places.field.parking.hint')}</small>
      </label>

      {save.isError && <ErrorNote error={save.error} />}

      <div className="form-actions">
        <button type="button" className="btn" onClick={onDone}>
          {t('common.cancel')}
        </button>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {t('common.save')}
        </button>
      </div>
    </form>
  )
}
