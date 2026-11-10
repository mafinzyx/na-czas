import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import type { Language } from '../api/types'
import { I18nContext } from './context'
import type { I18n, Translate } from './context'
import { en } from './en'
import type { TranslationKey } from './en'
import { pl } from './pl'

const dictionaries: Record<Language, Record<TranslationKey, string>> = { en, pl }
const STORAGE_KEY = 'language'

function initialLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'en' || stored === 'pl') return stored
  return navigator.language.startsWith('pl') ? 'pl' : 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage)

  const setLanguage = useCallback((next: Language) => {
    localStorage.setItem(STORAGE_KEY, next)
    document.documentElement.lang = next
    setLanguageState(next)
  }, [])

  const value = useMemo<I18n>(() => {
    const t: Translate = (key, params = {}) =>
      dictionaries[language][key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? ''))
    return { language, locale: language === 'pl' ? 'pl-PL' : 'en-GB', setLanguage, t }
  }, [language, setLanguage])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
