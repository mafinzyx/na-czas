// Date, time and money helpers. The API uses local times without a timezone.

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

/** YYYY-MM-DD in local time (toISOString would convert to UTC and may shift the day). */
export function localIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function localIsoDateTime(date: Date): string {
  return `${localIsoDate(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
}

export function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00`)
  date.setDate(date.getDate() + days)
  return localIsoDate(date)
}

/** "2026-11-12T07:46:00" -> "07:46" */
export function clockTime(isoDateTime: string): string {
  return isoDateTime.slice(11, 16)
}

export function formatDay(isoDate: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long' }).format(
    new Date(`${isoDate}T00:00:00`),
  )
}

export function formatShortDate(isoDate: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' }).format(
    new Date(`${isoDate}T00:00:00`),
  )
}

export function formatMoney(amount: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'PLN', currencyDisplay: 'narrowSymbol' }).format(amount)
}

/** Monday-first weekday names for the given locale. 2024-01-01 was a Monday. */
export function weekdayNames(locale: string): string[] {
  const formatter = new Intl.DateTimeFormat(locale, { weekday: 'short' })
  return Array.from({ length: 7 }, (_, index) => formatter.format(new Date(2024, 0, 1 + index)))
}
