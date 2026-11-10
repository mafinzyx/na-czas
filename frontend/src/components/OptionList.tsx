import type { JourneyPlan, Leg, Mode, RouteOption } from '../api/types'
import { isTranslationKey, useI18n } from '../i18n'
import { clockTime, formatMoney } from '../lib/format'
import { LEG_COLOR, LEG_ICON, MODE_ICON } from '../lib/modes'
import { ElevationChart } from './ElevationChart'

interface Props {
  plan: JourneyPlan
  selectedId: string
  onSelect: (id: string) => void
}

/** Options grouped by transport mode, in the order of each mode's best option. */
function groupByMode(options: RouteOption[]): [Mode, RouteOption[]][] {
  const groups = new Map<Mode, RouteOption[]>()
  for (const option of options) {
    groups.set(option.mode, [...(groups.get(option.mode) ?? []), option])
  }
  return [...groups.entries()]
}

function LineBadge({ leg }: { leg: Leg }) {
  return (
    <span className="line-badge" style={{ background: leg.color ?? LEG_COLOR[leg.kind] }}>
      {LEG_ICON[leg.kind]} {leg.line}
    </span>
  )
}

function LegTimeline({ option, plan }: { option: RouteOption; plan: JourneyPlan }) {
  const { t } = useI18n()
  return (
    <ol className="legs">
      {option.legs.map((leg, index) => {
        if (leg.kind === 'walk') {
          const metres = leg.distance_km === null ? null : Math.round(leg.distance_km * 1000)
          return (
            <li key={index} className="leg leg-walk">
              <span className="leg-icon">🚶</span>
              <span>
                {t('leg.walk', { minutes: leg.minutes, to: leg.to_name ?? plan.destination.name })}
                {metres !== null && <small className="muted"> · {metres} m</small>}
              </span>
            </li>
          )
        }
        return (
          <li key={index} className="leg" style={{ borderColor: leg.color ?? LEG_COLOR[leg.kind] }}>
            <span className="leg-icon">
              <LineBadge leg={leg} />
            </span>
            <span>
              {leg.headsign && <strong>{t('leg.direction', { headsign: leg.headsign })}</strong>}
              <span className="leg-stop">
                <b>{leg.depart && clockTime(leg.depart)}</b> {t('leg.board', { stop: leg.from_name ?? '' })}
              </span>
              <span className="leg-stop">
                <b>{leg.arrive && clockTime(leg.arrive)}</b> {t('leg.alight', { stop: leg.to_name ?? '' })}
                {leg.stops !== null && <small className="muted"> · {t('leg.stops', { count: leg.stops })}</small>}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function OptionRow({ option, variant, plan, selected, onSelect }: {
  option: RouteOption
  variant: number
  plan: JourneyPlan
  selected: boolean
  onSelect: () => void
}) {
  const { t, locale } = useI18n()
  const code = (prefix: string, value: string) => {
    const key = `${prefix}.${value}`
    return isTranslationKey(key) ? t(key) : value
  }

  const rides = option.legs.filter((leg) => leg.kind !== 'walk' && leg.line)
  const facts: string[] = []
  if (option.mode === 'bike') facts.push(t('option.route', { number: variant + 1 }))
  if (option.distance_km !== null) facts.push(`${option.distance_km} km`)
  if (option.ascent_m !== null) facts.push(t('option.ascent', { metres: option.ascent_m }))
  if (option.transfers !== null && !option.estimated) {
    facts.push(option.transfers === 0 ? t('option.direct') : t('option.transfers', { count: option.transfers }))
  }
  if (option.estimated) facts.push(t('option.estimated'))

  const unusable = option.too_late || option.risky
  return (
    <li className={`option ${selected ? 'is-selected' : ''} ${unusable ? 'is-unusable' : ''}`}>
      <button type="button" className="option-summary" onClick={onSelect} aria-expanded={selected}>
        <span className="option-times">
          <strong>{clockTime(option.depart_at)}</strong> → {clockTime(option.arrive_at)}
        </span>
        <span className="option-middle">
          {rides.length > 0 && (
            <span className="line-badges">
              {rides.map((leg, index) => (
                <LineBadge key={index} leg={leg} />
              ))}
            </span>
          )}
          <small className="muted">{facts.join(' · ')}</small>
        </span>
        <span className="option-numbers">
          <strong>{option.typical_minutes} min</strong>
          <small>{option.cost_pln === 0 ? t('trip.free') : formatMoney(option.cost_pln, locale)}</small>
        </span>
      </button>

      <div className="option-badges">
        {option.id === plan.recommended && <span className="badge badge-best">{t('trip.recommended')}</span>}
        {option.too_late && <span className="badge badge-danger">{t('options.tooLate')}</span>}
        {option.risky && <span className="badge badge-danger">{t('options.risky')}</span>}
        {option.tags.map((tag) => (
          <span key={tag} className="badge badge-good">
            {code('tag', tag)}
          </span>
        ))}
        {option.warnings.map((warning) => (
          <span key={warning} className="badge badge-warn">
            {code('warning', warning)}
          </span>
        ))}
      </div>

      {selected && (
        <div className="option-details">
          <p className="muted">
            {plan.time_mode === 'arrive' && `${t('option.buffer', { minutes: option.buffer_minutes })} · `}
            {t('option.worstArrival', { time: clockTime(option.arrive_worst) })} ·{' '}
            {t(`reliability.${option.reliability}`)}
          </p>
          {option.mode === 'transit' && option.legs.length > 0 && <LegTimeline option={option} plan={plan} />}
          {option.elevation_profile.length > 1 && <ElevationChart profile={option.elevation_profile} />}
        </div>
      )}
    </li>
  )
}

/** Every way of making the journey; clicking one shows it on the map and opens its details. */
export function OptionList({ plan, selectedId, onSelect }: Props) {
  const { t } = useI18n()

  return (
    <div className="option-groups">
      {groupByMode(plan.options).map(([mode, options]) => (
        <section key={mode} className="card option-group">
          <h3>
            <span aria-hidden="true">{MODE_ICON[mode]}</span> {t(`mode.${mode}`)}
            {options.length > 1 && <small className="muted">{t('option.variants', { count: options.length })}</small>}
          </h3>
          <ul>
            {options.map((option, index) => (
              <OptionRow
                key={option.id}
                option={option}
                variant={index}
                plan={plan}
                selected={option.id === selectedId}
                onSelect={() => onSelect(option.id)}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
