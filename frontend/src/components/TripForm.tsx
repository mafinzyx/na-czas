import { useState } from 'react'
import type { FormEvent } from 'react'

import { useSaveTrip } from '../api/hooks'
import type { Importance, Place, Trip } from '../api/types'
import { useI18n } from '../i18n'
import { localIsoDate, weekdayNames } from '../lib/format'
import { ErrorNote, Segmented } from './ui'

type Schedule = 'weekly' | 'once'
const IMPORTANCE_LEVELS: Importance[] = ['low', 'normal', 'high']

export function TripForm({ trip, places, onDone }: { trip?: Trip; places: Place[]; onDone: () => void }) {
  const { t, locale } = useI18n()
  const save = useSaveTrip()

  const [title, setTitle] = useState(trip?.title ?? '')
  const [originId, setOriginId] = useState(trip?.origin_id ?? places[0].id)
  const [destinationId, setDestinationId] = useState(trip?.destination_id ?? places[1].id)
  const [arriveBy, setArriveBy] = useState(trip?.arrive_by.slice(0, 5) ?? '09:00')
  const [importance, setImportance] = useState<Importance>(trip?.importance ?? 'normal')
  const [schedule, setSchedule] = useState<Schedule>(trip?.date ? 'once' : 'weekly')
  const [weekdays, setWeekdays] = useState<number[]>(trip?.weekdays ?? [])
  const [date, setDate] = useState(() => trip?.date ?? localIsoDate(new Date()))
  const [error, setError] = useState<string | null>(null)

  const toggleDay = (day: number) =>
    setWeekdays((current) => (current.includes(day) ? current.filter((d) => d !== day) : [...current, day]))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (originId === destinationId) return setError(t('trips.error.samePlace'))
    if (schedule === 'weekly' && weekdays.length === 0) return setError(t('trips.error.noDays'))
    setError(null)

    save.mutate(
      {
        id: trip?.id,
        data: {
          title: title.trim(),
          origin_id: originId,
          destination_id: destinationId,
          arrive_by: arriveBy,
          importance,
          weekdays: schedule === 'weekly' ? weekdays : [],
          date: schedule === 'once' ? date : null,
        },
      },
      { onSuccess: onDone },
    )
  }

  const placeOptions = places.map((place) => (
    <option key={place.id} value={place.id}>
      {place.name}
    </option>
  ))

  return (
    <form className="form" onSubmit={submit}>
      <label>
        {t('trips.field.title')}
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={t('trips.field.title.placeholder')}
          maxLength={80}
          required
          autoFocus
        />
      </label>

      <div className="form-grid">
        <label>
          {t('trips.field.from')}
          <select value={originId} onChange={(event) => setOriginId(Number(event.target.value))}>
            {placeOptions}
          </select>
        </label>
        <label>
          {t('trips.field.to')}
          <select value={destinationId} onChange={(event) => setDestinationId(Number(event.target.value))}>
            {placeOptions}
          </select>
        </label>
      </div>

      <label>
        {t('trips.field.arrive')}
        <input type="time" value={arriveBy} onChange={(event) => setArriveBy(event.target.value)} required />
      </label>

      <div className="field">
        <span>{t('trips.field.importance')}</span>
        <Segmented
          label={t('trips.field.importance')}
          value={importance}
          onChange={setImportance}
          options={IMPORTANCE_LEVELS.map((level) => ({ value: level, label: t(`importance.${level}`) }))}
        />
      </div>

      <div className="field">
        <span>{t('trips.field.schedule')}</span>
        <Segmented
          label={t('trips.field.schedule')}
          value={schedule}
          onChange={setSchedule}
          options={[
            { value: 'weekly', label: t('trips.schedule.weekly') },
            { value: 'once', label: t('trips.schedule.once') },
          ]}
        />
      </div>

      {schedule === 'weekly' ? (
        <div className="weekdays">
          {weekdayNames(locale).map((dayName, day) => (
            <button
              key={day}
              type="button"
              className={weekdays.includes(day) ? 'active' : ''}
              aria-pressed={weekdays.includes(day)}
              onClick={() => toggleDay(day)}
            >
              {dayName}
            </button>
          ))}
        </div>
      ) : (
        <label>
          {t('trips.field.date')}
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
        </label>
      )}

      {error && <p className="field-error">{error}</p>}
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
