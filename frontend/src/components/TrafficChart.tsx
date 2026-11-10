import { useTrafficCurve } from '../api/hooks'
import { useI18n } from '../i18n'

const START_HOUR = 5
const END_HOUR = 22
const WIDTH = 560
const HEIGHT = 110
const PADDING = { top: 8, bottom: 20, x: 6 }
const MAX_FACTOR = 1.9

function x(hour: number): number {
  return PADDING.x + ((hour - START_HOUR) / (END_HOUR - START_HOUR)) * (WIDTH - 2 * PADDING.x)
}

function y(factor: number): number {
  const usable = HEIGHT - PADDING.top - PADDING.bottom
  return PADDING.top + usable * (1 - (factor - 1) / (MAX_FACTOR - 1))
}

/** Congestion through the day with a marker at the trip's arrival time. */
export function TrafficChart({ day, arriveAt }: { day: string; arriveAt: string }) {
  const { t } = useI18n()
  const { data } = useTrafficCurve(day)
  if (!data) return null

  const points = data.filter((point) => point.hour >= START_HOUR && point.hour <= END_HOUR)
  const line = points.map((point) => `${x(point.hour)},${y(point.factor)}`).join(' ')
  const baseline = y(1)
  const area = `${x(START_HOUR)},${baseline} ${line} ${x(END_HOUR)},${baseline}`

  const arrivalHour = Number(arriveAt.slice(11, 13)) + Number(arriveAt.slice(14, 16)) / 60
  const markerVisible = arrivalHour >= START_HOUR && arrivalHour <= END_HOUR
  const ticks = [6, 8, 10, 12, 14, 16, 18, 20]

  return (
    <figure className="traffic-chart">
      <figcaption>{t('traffic.chart')}</figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={t('traffic.chart')}>
        <polygon points={area} className="traffic-area" />
        <polyline points={line} className="traffic-line" />
        {ticks.map((hour) => (
          <text key={hour} x={x(hour)} y={HEIGHT - 5} textAnchor="middle" className="traffic-tick">
            {hour}:00
          </text>
        ))}
        {markerVisible && (
          <>
            <line x1={x(arrivalHour)} x2={x(arrivalHour)} y1={PADDING.top} y2={baseline} className="traffic-marker" />
            <text
              x={x(arrivalHour)}
              y={PADDING.top + 2}
              dx={arrivalHour > 18 ? -6 : 6}
              textAnchor={arrivalHour > 18 ? 'end' : 'start'}
              dominantBaseline="hanging"
              className="traffic-marker-label"
            >
              {t('traffic.chart.arrival')}
            </text>
          </>
        )}
      </svg>
    </figure>
  )
}
