import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useDeleteTrip, usePlaces, useTrips } from '../api/hooks'
import type { Trip } from '../api/types'
import { TripForm } from '../components/TripForm'
import { DeleteButton, ErrorNote, Loading, Modal, PageHeader } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDay, weekdayNames } from '../lib/format'

/** undefined = closed, null = creating a new trip, Trip = editing it. */
type Editing = Trip | null | undefined

export function TripsPage() {
  const { t, locale } = useI18n()
  const trips = useTrips()
  const places = usePlaces()
  const remove = useDeleteTrip()
  const [editing, setEditing] = useState<Editing>(undefined)

  const dayNames = weekdayNames(locale)
  const describeSchedule = (trip: Trip) =>
    trip.date
      ? formatDay(trip.date, locale)
      : t('trips.every', { days: trip.weekdays.map((day) => dayNames[day]).join(', ') })

  const canAdd = (places.data?.length ?? 0) >= 2

  return (
    <>
      <PageHeader
        title={t('trips.title')}
        intro={t('trips.intro')}
        action={
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)} disabled={!canAdd}>
            + {t('trips.add')}
          </button>
        }
      />

      {places.data && !canAdd && (
        <div className="note">
          <span>{t('trips.needPlaces')}</span>
          <Link to="/places" className="btn btn-small">
            {t('places.add')}
          </Link>
        </div>
      )}

      {trips.isPending && <Loading />}
      {trips.isError && <ErrorNote error={trips.error} onRetry={() => void trips.refetch()} />}
      {remove.isError && <ErrorNote error={remove.error} />}
      {trips.data?.length === 0 && <p className="muted">{t('trips.empty')}</p>}

      <div className="list">
        {trips.data?.map((trip) => (
          <article key={trip.id} className="card list-item">
            <div>
              <h3>
                {trip.title}
                {trip.importance !== 'normal' && (
                  <span className={`badge ${trip.importance === 'high' ? 'badge-important' : ''}`}>
                    {t(`importance.${trip.importance}`)}
                  </span>
                )}
              </h3>
              <p className="muted">
                {trip.origin.name} → {trip.destination.name} · {t('trip.arrive', { time: trip.arrive_by.slice(0, 5) })}
              </p>
              <p className="muted">{describeSchedule(trip)}</p>
            </div>
            <div className="list-actions">
              <button type="button" className="btn btn-small" onClick={() => setEditing(trip)}>
                {t('common.edit')}
              </button>
              <DeleteButton onConfirm={() => remove.mutate(trip.id)} disabled={remove.isPending} />
            </div>
          </article>
        ))}
      </div>

      {editing !== undefined && places.data && (
        <Modal title={editing ? t('trips.edit') : t('trips.add')} onClose={() => setEditing(undefined)}>
          <TripForm trip={editing ?? undefined} places={places.data} onDone={() => setEditing(undefined)} />
        </Modal>
      )}
    </>
  )
}
