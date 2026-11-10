// Minimal i18n: two dictionaries, a context and a t() function with {placeholders}.

import { createContext, useContext } from 'react'

import type { Language } from '../api/types'
import { en } from './en'
import type { TranslationKey } from './en'

export type Translate = (key: TranslationKey, params?: Record<string, string | number>) => string

export interface I18n {
  language: Language
  /** BCP 47 tag for Intl formatters. */
  locale: string
  setLanguage: (language: Language) => void
  t: Translate
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const context = useContext(I18nContext)
  if (context === null) throw new Error('useI18n must be used inside I18nProvider')
  return context
}

/** For keys built at runtime from API codes (tags, warnings). */
export function isTranslationKey(key: string): key is TranslationKey {
  return key in en
}
