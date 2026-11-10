import type { JourneyPlan, Weather } from '../api/types'
import { useI18n } from '../i18n'
import { clockTime, formatMoney } from '../lib/format'
import { MODE_ICON } from '../lib/modes'
import { findOption } from '../lib/plan'

export function WeatherChip({ weather }: { weather: Weather | null }) {
  const { t } = useI18n()
  if (!weather) return <span className="chip">{t('weather.unknown')}</span>

  const chance = weather.precipitation_probability ?? 0
  const wet = weather.precipitation_mm >= 0.3 || chance >= 60
  const rainText =
    weather.precipitation_mm >= 0.3
      ? t('weather.rain', { mm: weather.precipitation_mm.toFixed(1) })
      : chance >= 30
        ? t('weather.rainChance', { percent: chance })
        : t('weather.dry')

  return (
    <span className={`chip ${wet ? 'chip-warn' : ''}`}>
      {wet ? '🌧' : '🌤'} {Math.round(weather.temperature_c)}°C, {rainText}
    </span>
  )
}

export function TrafficChip({ congestion }: { congestion: number }) {
  const { t } = useI18n()
  if (congestion >= 1.4) return <span className="chip chip-warn">🚦 {t('traffic.heavy')}</span>
  if (congestion >= 1.15) return <span className="chip">🚦 {t('traffic.moderate')}</span>
  return <span className="chip">🚦 {t('traffic.free')}</span>
}

function BackupNote({ plan }: { plan: JourneyPlan }) {
  const { t } = useI18n()
  const { backup } = plan
  if (!backup) return <p className="backup muted">{t('backup.none')}</p>

  const name = [t(`mode.${backup.mode}`), backup.label].filter(Boolean).join(' ')
  return (
    <div className={`backup ${backup.commit_early ? 'backup-early' : ''}`}>
      <strong>
        {MODE_ICON[backup.mode]} {t('backup.title', { mode: name })}
      </strong>
      <span>
        {backup.commit_early
          ? t('backup.early', { time: clockTime(backup.decide_by) })
          : t('backup.safe', { time: clockTime(backup.depart_at) })}
        {backup.board_stop && ` ${t('backup.stop', { stop: backup.board_stop })}`}
      </span>
    </div>
  )
}

/** The verdict for one journey: what to take, when to leave, and the plan B deadline. */
export function Recommendation({ plan }: { plan: JourneyPlan }) {
  const { t, locale } = useI18n()
  const chosen = findOption(plan, plan.recommended)
  if (!chosen) return null

  const departing = plan.time_mode === 'depart'
  const late = plan.status === 'late'
  return (
    <>
      {plan.status === 'late' && (
        <div className="note note-error">
          <span>
            <strong>{t('trip.late.title')}.</strong>{' '}
            {t('trip.late.text', { mode: t(`mode.${chosen.mode}`), minutes: plan.late_by_minutes ?? 0 })}
          </span>
        </div>
      )}

      <div className="recommendation">
        <span className="mode-icon" aria-hidden="true">
          {MODE_ICON[chosen.mode]}
        </span>
        <div className="recommendation-main">
          <small>{t('trip.recommended')}</small>
          <strong>
            {t(`mode.${chosen.mode}`)} {chosen.label}
          </strong>
          <span className="muted">
            {t('trip.duration', { typical: chosen.typical_minutes, worst: chosen.worst_minutes })} ·{' '}
            {chosen.cost_pln === 0 ? t('trip.free') : formatMoney(chosen.cost_pln, locale)}
          </span>
        </div>
        <div className="leave-by">
          <small>{departing ? t('trip.arriveAbout') : t('trip.leaveBy')}</small>
          <strong>{late ? t('trip.now') : clockTime(departing ? chosen.arrive_at : chosen.depart_at)}</strong>
        </div>
      </div>

      {plan.status === 'ok' && !departing && <BackupNote plan={plan} />}
    </>
  )
}
