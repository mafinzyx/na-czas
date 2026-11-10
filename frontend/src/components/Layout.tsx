import { NavLink, Outlet, useLocation } from 'react-router-dom'

import type { Language } from '../api/types'
import { useI18n } from '../i18n'

const LANGUAGES: Language[] = ['pl', 'en']

export function Layout() {
  const { t, language, setLanguage } = useI18n()
  // The search screen shows a map next to the results and needs the full width.
  const wide = useLocation().pathname === '/'

  return (
    <>
      <header className="topbar">
        <div className={`topbar-inner ${wide ? 'is-wide' : ''}`}>
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              ⏱
            </span>
            <div>
              <strong>{t('app.name')}</strong>
              <small>{t('app.tagline')}</small>
            </div>
          </div>

          <nav className="nav">
            <NavLink to="/" end>
              {t('nav.search')}
            </NavLink>
            <NavLink to="/week">{t('nav.week')}</NavLink>
            <NavLink to="/trips">{t('nav.trips')}</NavLink>
            <NavLink to="/places">{t('nav.places')}</NavLink>
            <NavLink to="/profile">{t('nav.profile')}</NavLink>
          </nav>

          <div className="language-switch" role="group" aria-label="Language">
            {LANGUAGES.map((code) => (
              <button
                key={code}
                type="button"
                className={code === language ? 'active' : ''}
                aria-pressed={code === language}
                onClick={() => setLanguage(code)}
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className={`container ${wide ? 'is-wide' : ''}`}>
        <Outlet />
      </main>
    </>
  )
}
