import { useI18n } from '../i18n'

const WIDTH = 520
const HEIGHT = 90
const PADDING = { top: 14, bottom: 16, left: 4, right: 4 }
/** A flat route should look flat, so the vertical range never shrinks below this. */
const MIN_RANGE_M = 30

/** Height above sea level along a bike route. */
export function ElevationChart({ profile }: { profile: [number, number][] }) {
  const { t } = useI18n()

  const totalKm = profile[profile.length - 1][0] || 1
  const heights = profile.map(([, metres]) => metres)
  const lowest = Math.min(...heights)
  const highest = Math.max(...heights)
  const range = Math.max(highest - lowest, MIN_RANGE_M)

  const x = (km: number) => PADDING.left + (km / totalKm) * (WIDTH - PADDING.left - PADDING.right)
  const y = (metres: number) =>
    HEIGHT - PADDING.bottom - ((metres - lowest) / range) * (HEIGHT - PADDING.top - PADDING.bottom)

  const line = profile.map(([km, metres]) => `${x(km)},${y(metres)}`).join(' ')
  const floor = HEIGHT - PADDING.bottom
  const area = `${x(0)},${floor} ${line} ${x(totalKm)},${floor}`

  return (
    <figure className="elevation-chart">
      <figcaption>
        {t('elevation.title')} · {Math.round(lowest)}–{Math.round(highest)} m
      </figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={t('elevation.title')}>
        <polygon points={area} className="elevation-area" />
        <polyline points={line} className="elevation-line" />
        <text x={PADDING.left} y={HEIGHT - 3} className="traffic-tick">
          0 km
        </text>
        <text x={WIDTH - PADDING.right} y={HEIGHT - 3} textAnchor="end" className="traffic-tick">
          {totalKm.toFixed(1)} km
        </text>
      </svg>
    </figure>
  )
}
