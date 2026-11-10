import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useWeekPlan } from '../api/hooks'
import type { WeekSummary } from '../api/types'
import { AdvicePanel } from '../components/AdvicePanel'
import { TripCard } from '../components/TripCard'
import { ErrorNote, Loading } from '../components/ui'
import { useI18n } from '../i18n'
import { addDays, formatDay, formatMoney, formatShortDate, localIsoDate } from '../lib/format'

function SummaryTiles({ summary }: { summary: WeekSummary }) {
  const { t, locale } = useI18n()
  const saving =
    summary.car_only_cost_pln === null ? null : summary.car_only_cost_pln - summary.recommended_cost_pln
  const hours = Math.floor(summary.travel_minutes / 60)
  const minutes = summary.travel_minutes % 60

  return (
    <section className="tiles">
      <div className="tile">
        <small>{t('summary.trips')}</small>
        <strong>{summary.trips_count}</strong>
      </div>
      <div className="tile">
        <small>{t('summary.cost')}</small>
        <strong>{formatMoney(summary.recommended_cost_pln, locale)}</strong>
      </div>
      {saving !== null && (
        <div className="tile tile-good">
          <small>{t('summary.saving')}</small>
          <strong>{formatMoney(Math.max(saving, 0), locale)}</strong>
        </div>
      )}
      <div className="tile">
        <small>{t('summary.time')}</small>
        <strong>{hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`}</strong>
      </div>
      <div className={`tile ${summary.commit_early_count > 0 ? 'tile-warn' : ''}`} title={t('summary.decisions.hint')}>
        <small>{t('summary.decisions')}</small>
        <strong>{summary.commit_early_count}</strong>
      </div>
    </section>
  )
}

export function WeekPage() {
  const { t, locale, language } = useI18n()
  const [today] = useState(() => localIsoDate(new Date()))
  const [start, setStart] = useState(today)
  const plan = useWeekPlan(start)

  return (
    <>
      <header className="page-header">
        <div>
          <h1>{t('nav.week')}</h1>
          <p className="muted">
            {formatShortDate(start, locale)} – {formatShortDate(addDays(start, 6), locale)}
          </p>
        </div>
        <div className="week-nav">
          <button type="button" className="btn" onClick={() => setStart(addDays(start, -7))} aria-label={t('week.previous')}>
            ←
          </button>
          <button type="button" className="btn" onClick={() => setStart(today)} disabled={start === today}>
            {t('week.today')}
          </button>
          <button type="button" className="btn" onClick={() => setStart(addDays(start, 7))} aria-label={t('week.next')}>
            →
          </button>
        </div>
      </header>

      {plan.isPending && <Loading />}
      {plan.isError && <ErrorNote error={plan.error} onRetry={() => void plan.refetch()} />}

      {plan.data && plan.data.summary.trips_count === 0 && (
        <div className="card empty">
          <h2>{t('week.empty.title')}</h2>
          <p className="muted">{t('week.empty.text')}</p>
          <Link to="/" className="btn btn-primary">
            {t('week.empty.action')}
          </Link>
        </div>
      )}

      {plan.data && plan.data.summary.trips_count > 0 && (
        <>
          <SummaryTiles summary={plan.data.summary} />
          {/* The key resets the briefing when the week or the language changes. */}
          <AdvicePanel key={`${start}-${language}`} start={start} />

          {plan.data.days.map((day) => (
            <section key={day.date} className="day">
              <h2 className={day.date === today ? 'is-today' : ''}>
                {formatDay(day.date, locale)}
                {day.date === today && <span className="badge badge-good">{t('week.today')}</span>}
              </h2>
              {day.trips.length === 0 ? (
                <p className="muted day-empty">{t('week.noTrips')}</p>
              ) : (
                day.trips.map((trip) => <TripCard key={`${trip.trip_id}-${day.date}`} plan={trip} />)
              )}
            </section>
          ))}
        </>
      )}
    </>
  )
}
