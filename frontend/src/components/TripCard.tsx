import { Link } from 'react-router-dom'

import type { TripPlan } from '../api/types'
import { useI18n } from '../i18n'
import { clockTime } from '../lib/format'
import type { SearchPreset } from '../lib/places'
import { Recommendation, TrafficChip, WeatherChip } from './Recommendation'

/** One saved trip on one day of the week view. Details and the map live on the search screen. */
export function TripCard({ plan }: { plan: TripPlan }) {
  const { t } = useI18n()

  const search: SearchPreset = {
    origin: plan.origin,
    destination: plan.destination,
    date: plan.time.slice(0, 10),
    time: clockTime(plan.time),
    timeMode: 'arrive',
    importance: plan.importance,
  }

  return (
    <article className={`card trip-card ${plan.status === 'past' ? 'is-past' : ''}`}>
      <div className="trip-head">
        <div>
          <h3>
            {plan.title}
            {plan.importance !== 'normal' && (
              <span className={`badge ${plan.importance === 'high' ? 'badge-important' : ''}`}>
                {t(`importance.${plan.importance}`)}
              </span>
            )}
            {plan.status === 'past' && <span className="badge">{t('trip.past')}</span>}
          </h3>
          <p className="muted">
            {plan.origin.name} → {plan.destination.name} · {t('trip.distance', { km: plan.distance_km })}
          </p>
        </div>
        <div className="trip-arrive">{t('trip.arrive', { time: clockTime(plan.time) })}</div>
      </div>

      <div className="chips">
        <WeatherChip weather={plan.weather} />
        <TrafficChip congestion={plan.congestion} />
      </div>

      <Recommendation plan={plan} />

      <Link to="/" state={{ search }} className="link-button">
        {t('trip.details')} →
      </Link>
    </article>
  )
}
