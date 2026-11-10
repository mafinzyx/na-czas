import { ApiError } from '../api/client'
import type { Translate } from '../i18n'

/** Turns any thrown value into a message the user can act on. */
export function describeError(error: unknown, t: Translate): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return t('error.network')
    if (error.status === 409) return t('error.placeInUse')
    return t('error.generic', { message: error.message })
  }
  return t('error.generic', { message: error instanceof Error ? error.message : String(error) })
}
