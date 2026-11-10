import { useAdvice } from '../api/hooks'
import { useI18n } from '../i18n'
import { ErrorNote } from './ui'

/** Plain-language briefing for the visible week. Requested on demand, because it may call an LLM. */
export function AdvicePanel({ start }: { start: string }) {
  const { t, language } = useI18n()
  const advice = useAdvice()

  const request = () => advice.mutate({ start, language })
  const lines = advice.data?.text.split('\n').map((line) => line.replace(/^-\s*/, '').trim()).filter(Boolean)

  return (
    <section className="card advice">
      <div className="advice-head">
        <div>
          <h2>✨ {t('advice.title')}</h2>
          {!advice.data && <p className="muted">{t('advice.intro')}</p>}
        </div>
        <button type="button" className="btn btn-primary" onClick={request} disabled={advice.isPending}>
          {advice.isPending ? t('advice.loading') : advice.data ? t('advice.refresh') : t('advice.button')}
        </button>
      </div>

      {advice.isError && <ErrorNote error={advice.error} />}

      {lines && (
        <>
          <ul className="advice-list">
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <small className="muted">{t(`advice.source.${advice.data!.source}`)}</small>
        </>
      )}
    </section>
  )
}
