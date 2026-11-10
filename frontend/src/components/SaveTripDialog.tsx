import { useState } from 'react'
import type { FormEvent } from 'react'

import { createPlace, createTrip, useRefreshAfterSavingTrip } from '../api/hooks'
import type { Importance, Place, Point } from '../api/types'
import { useI18n } from '../i18n'
import { weekdayNames } from '../lib/format'
import { findPlace } from '../lib/places'
import { ErrorNote, Modal, Segmented } from './ui'

type Schedule = 'weekly' | 'once'

interface Props {
  origin: Point
  destination: Point
  date: string
  time: string // HH:MM, the arrival deadline
  importance: Importance
  places: Place[]
  onClose: () => void
  onSaved: () => void
}

/** Turns the current search into a saved trip, creating places for ad-hoc points on the way. */
export function SaveTripDialog({ origin, destination, date, time, importance, places, onClose, onSaved }: Props) {
  const { t, locale } = useI18n()
  const refresh = useRefreshAfterSavingTrip()

  const [title, setTitle] = useState(destination.name.slice(0, 40))
  const [schedule, setSchedule] = useState<Schedule>('weekly')
  const [weekdays, setWeekdays] = useState<number[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [noDays, setNoDays] = useState(false)

  const toggleDay = (day: number) =>
    setWeekdays((current) => (current.includes(day) ? current.filter((d) => d !== day) : [...current, day]))

  /** A saved trip links two saved places, so a point picked on the map becomes a place first. */
  const ensurePlace = async (point: Point): Promise<number> => {
    const existing = findPlace(places, point)
    if (existing) return existing.id
    const created = await createPlace({
      name: point.name.slice(0, 80),
      address: point.name.slice(0, 255),
      lat: point.lat,
      lon: point.lon,
      parking_cost_pln: 0,
    })
    return created.id
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (schedule === 'weekly' && weekdays.length === 0) return setNoDays(true)
    setSaving(true)
    setError(null)
    try {
      await createTrip({
        title: title.trim(),
        origin_id: await ensurePlace(origin),
        destination_id: await ensurePlace(destination),
        arrive_by: time,
        importance,
        weekdays: schedule === 'weekly' ? weekdays : [],
        date: schedule === 'once' ? date : null,
      })
      refresh()
      onSaved()
    } catch (caught) {
      setError(caught)
      setSaving(false)
    }
  }

  return (
    <Modal title={t('save.title')} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <p className="muted">
          {origin.name} → {destination.name} · {t('trip.arrive', { time })}
        </p>
        <label>
          {t('trips.field.title')}
          <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={80} required autoFocus />
        </label>

        <div className="field">
          <span>{t('trips.field.schedule')}</span>
          <Segmented
            label={t('trips.field.schedule')}
            value={schedule}
            onChange={setSchedule}
            options={[
              { value: 'weekly', label: t('trips.schedule.weekly') },
              { value: 'once', label: `${t('trips.schedule.once')} (${date})` },
            ]}
          />
        </div>

        {schedule === 'weekly' && (
          <div className="weekdays">
            {weekdayNames(locale).map((dayName, day) => (
              <button
                key={day}
                type="button"
                className={weekdays.includes(day) ? 'active' : ''}
                aria-pressed={weekdays.includes(day)}
                onClick={() => {
                  toggleDay(day)
                  setNoDays(false)
                }}
              >
                {dayName}
              </button>
            ))}
          </div>
        )}

        {noDays && <p className="field-error">{t('trips.error.noDays')}</p>}
        {error !== null && <ErrorNote error={error} />}

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {t('common.save')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
