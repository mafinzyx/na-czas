import { useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { useJourney, usePlaces } from '../api/hooks'
import type { Importance, JourneyRequest, Point, TimeMode } from '../api/types'
import { LocationInput } from '../components/LocationInput'
import { OptionList } from '../components/OptionList'
import { Recommendation, TrafficChip, WeatherChip } from '../components/Recommendation'
import { RouteMap } from '../components/RouteMap'
import { SaveTripDialog } from '../components/SaveTripDialog'
import { TrafficChart } from '../components/TrafficChart'
import { ErrorNote, Loading, Segmented } from '../components/ui'
import { useI18n } from '../i18n'
import { localIsoDate, localIsoDateTime } from '../lib/format'
import { findPlace } from '../lib/places'
import { findOption } from '../lib/plan'
import type { SearchPreset } from '../lib/places'

type PickTarget = 'origin' | 'destination' | null
const IMPORTANCE_LEVELS: Importance[] = ['low', 'normal', 'high']
const ROUNDING_MINUTES = 5

/** Local time rounded up to the next five minutes, optionally some minutes ahead. */
function roundedNow(minutesAhead = 0): Date {
  const date = new Date(Date.now() + minutesAhead * 60_000)
  date.setMinutes(Math.ceil(date.getMinutes() / ROUNDING_MINUTES) * ROUNDING_MINUTES, 0, 0)
  return date
}

export function SearchPage() {
  const { t } = useI18n()
  const places = usePlaces()
  // The week view opens this screen with a journey already filled in.
  const preset = (useLocation().state as { search?: SearchPreset } | null)?.search

  const [initialTime] = useState(() => roundedNow(60))
  const [origin, setOrigin] = useState<Point | null>(preset?.origin ?? null)
  const [destination, setDestination] = useState<Point | null>(preset?.destination ?? null)
  const [timeMode, setTimeMode] = useState<TimeMode>(preset?.timeMode ?? 'arrive')
  const [date, setDate] = useState(preset?.date ?? localIsoDate(initialTime))
  const [time, setTime] = useState(preset?.time ?? localIsoDateTime(initialTime).slice(11, 16))
  const [importance, setImportance] = useState<Importance>(preset?.importance ?? 'normal')
  const [pickTarget, setPickTarget] = useState<PickTarget>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedNote, setSavedNote] = useState(false)

  const savedPlaces = useMemo(() => places.data ?? [], [places.data])

  const request = useMemo<JourneyRequest | null>(() => {
    if (!origin || !destination || !date || !time) return null
    if (origin.lat === destination.lat && origin.lon === destination.lon) return null
    return {
      origin: { name: origin.name, lat: origin.lat, lon: origin.lon },
      destination: { name: destination.name, lat: destination.lat, lon: destination.lon },
      time: `${date}T${time}:00`,
      time_mode: timeMode,
      importance,
      // Parking is a property of a saved place; a point picked ad hoc has none.
      parking_cost_pln: findPlace(savedPlaces, destination)?.parking_cost_pln ?? 0,
    }
  }, [origin, destination, date, time, timeMode, importance, savedPlaces])

  const journey = useJourney(request)
  const plan = request ? journey.data : undefined

  const selected = plan ? (findOption(plan, selectedId ?? '') ?? findOption(plan, plan.recommended) ?? null) : null
  // Bike variants are drawn faintly next to the selected one, so the routes can be compared.
  const alternatives = useMemo(
    () =>
      plan && selected?.mode === 'bike'
        ? plan.options.filter((o) => o.mode === 'bike' && o.id !== selected.id)
        : [],
    [plan, selected],
  )

  const setPoint = (target: 'origin' | 'destination', point: Point) => {
    if (target === 'origin') setOrigin(point)
    else setDestination(point)
    setSelectedId(null)
    setSavedNote(false)
  }

  const pickOnMap = (lat: number, lon: number) => {
    if (!pickTarget) return
    const rounded = { lat: Number(lat.toFixed(5)), lon: Number(lon.toFixed(5)) }
    setPoint(pickTarget, { name: t('search.mapPoint', { lat: rounded.lat, lon: rounded.lon }), ...rounded })
    setPickTarget(null)
  }

  const swap = () => {
    setOrigin(destination)
    setDestination(origin)
    setSelectedId(null)
  }

  const leaveNow = () => {
    const now = roundedNow()
    setTimeMode('depart')
    setDate(localIsoDate(now))
    setTime(localIsoDateTime(now).slice(11, 16))
  }

  const togglePick = (target: 'origin' | 'destination') => setPickTarget(pickTarget === target ? null : target)

  return (
    <div className="search-layout">
      <div className="search-panel">
        <section className="card search-form">
          <h1>{t('search.title')}</h1>

          <div className="location-rows">
            <div>
              <LocationInput
                label={t('search.from')}
                marker="A"
                value={origin}
                onChange={(point) => setPoint('origin', point)}
                places={savedPlaces}
                picking={pickTarget === 'origin'}
                onTogglePick={() => togglePick('origin')}
              />
              <LocationInput
                label={t('search.to')}
                marker="B"
                value={destination}
                onChange={(point) => setPoint('destination', point)}
                places={savedPlaces}
                picking={pickTarget === 'destination'}
                onTogglePick={() => togglePick('destination')}
              />
            </div>
            <button type="button" className="btn btn-small" onClick={swap} title={t('search.swap')} aria-label={t('search.swap')}>
              ⇅
            </button>
          </div>

          {pickTarget && <p className="note">{t('search.pickHint')}</p>}

          <div className="time-row">
            <Segmented
              label={t('search.timeMode')}
              value={timeMode}
              onChange={setTimeMode}
              options={[
                { value: 'arrive', label: t('search.arriveBy') },
                { value: 'depart', label: t('search.departAt') },
              ]}
            />
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} aria-label={t('trips.field.date')} />
            <input type="time" value={time} onChange={(event) => setTime(event.target.value)} aria-label={t('search.time')} />
            <button type="button" className="btn btn-small" onClick={leaveNow}>
              {t('search.now')}
            </button>
          </div>

          {timeMode === 'arrive' && (
            <div className="importance-row">
              <small className="muted">{t('trips.field.importance')}</small>
              <Segmented
                label={t('trips.field.importance')}
                value={importance}
                onChange={setImportance}
                options={IMPORTANCE_LEVELS.map((level) => ({ value: level, label: t(`importance.${level}`) }))}
              />
            </div>
          )}
        </section>

        {!request && (
          <div className="card empty">
            <h2>{t('search.empty.title')}</h2>
            <p className="muted">{t('search.empty.text')}</p>
          </div>
        )}

        {request && journey.isPending && <Loading />}
        {request && journey.isError && <ErrorNote error={journey.error} onRetry={() => void journey.refetch()} />}

        {plan && (
          <div className={`results ${journey.isPlaceholderData ? 'is-stale' : ''}`}>
            <section className="card trip-card">
              <div className="chips">
                <WeatherChip weather={plan.weather} />
                <TrafficChip congestion={plan.congestion} />
                <span className="chip">
                  {plan.transit_source === 'timetable' ? `🕒 ${t('search.timetable')}` : `⚠ ${t('search.noTimetable')}`}
                </span>
              </div>
              <Recommendation plan={plan} />
              <div className="result-actions">
                {savedNote ? (
                  <span className="saved">
                    ✓ {t('save.done')} <Link to="/week">{t('nav.week')}</Link>
                  </span>
                ) : (
                  timeMode === 'arrive' && (
                    <button type="button" className="btn btn-small" onClick={() => setSaving(true)}>
                      ＋ {t('save.button')}
                    </button>
                  )
                )}
              </div>
            </section>

            <OptionList plan={plan} selectedId={selected?.id ?? ''} onSelect={setSelectedId} />

            <section className="card">
              <TrafficChart day={plan.time.slice(0, 10)} arriveAt={plan.time} />
            </section>
          </div>
        )}
      </div>

      <div className="search-map">
        <RouteMap
          origin={origin}
          destination={destination}
          option={selected}
          alternatives={alternatives}
          picking={pickTarget !== null}
          onPick={pickOnMap}
        />
      </div>

      {saving && origin && destination && (
        <SaveTripDialog
          origin={origin}
          destination={destination}
          date={date}
          time={time}
          importance={importance}
          places={savedPlaces}
          onClose={() => setSaving(false)}
          onSaved={() => {
            setSaving(false)
            setSavedNote(true)
          }}
        />
      )}
    </div>
  )
}
