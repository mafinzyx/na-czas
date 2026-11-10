import { useState } from 'react'
import type { FormEvent } from 'react'

import { useProfile, useSaveProfile } from '../api/hooks'
import type { Priority, Profile } from '../api/types'
import { ErrorNote, Loading, PageHeader } from '../components/ui'
import { useI18n } from '../i18n'
import type { TranslationKey } from '../i18n/en'

const PRIORITIES: Priority[] = ['balanced', 'cheapest', 'fastest']

type BooleanField = 'has_car' | 'has_bike' | 'bike_is_electric' | 'has_scooter' | 'has_transit_pass'
type NumberField = Exclude<keyof Profile, BooleanField | 'priority'>

const OWNED: { field: Exclude<BooleanField, 'bike_is_electric'>; icon: string }[] = [
  { field: 'has_car', icon: '🚗' },
  { field: 'has_bike', icon: '🚲' },
  { field: 'has_scooter', icon: '🛴' },
  { field: 'has_transit_pass', icon: '🎫' },
]

function ProfileForm({ initial }: { initial: Profile }) {
  const { t } = useI18n()
  const save = useSaveProfile()
  const [profile, setProfile] = useState(initial)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  const update = (changes: Partial<Profile>) => {
    setProfile({ ...profile, ...changes })
    setSavedAt(null)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate(profile, { onSuccess: () => setSavedAt(Date.now()) })
  }

  const numberInput = (field: NumberField, label: TranslationKey, step: number, disabled = false) => (
    <label>
      {t(label)}
      <input
        type="number"
        min={0}
        step={step}
        value={profile[field]}
        disabled={disabled}
        onChange={(event) => update({ [field]: Number(event.target.value) })}
        required
      />
    </label>
  )

  return (
    <form className="form profile-form" onSubmit={submit}>
      <section className="card">
        <h2>{t('profile.section.own')}</h2>
        <div className="toggles">
          {OWNED.map(({ field, icon }) => (
            <label key={field} className={`toggle ${profile[field] ? 'active' : ''}`}>
              <input
                type="checkbox"
                checked={profile[field]}
                onChange={(event) => update({ [field]: event.target.checked })}
              />
              <span aria-hidden="true">{icon}</span>
              {t(`profile.${field}`)}
            </label>
          ))}
        </div>
        {profile.has_bike && (
          <label className="inline-check">
            <input
              type="checkbox"
              checked={profile.bike_is_electric}
              onChange={(event) => update({ bike_is_electric: event.target.checked })}
            />
            <span>
              ⚡ {t('profile.bike_is_electric')}
              <small className="muted"> · {t('profile.bike_is_electric.hint')}</small>
            </span>
          </label>
        )}
      </section>

      <section className="card">
        <h2>{t('profile.section.car')}</h2>
        <div className="form-grid">
          {numberInput('fuel_consumption_l_per_100km', 'profile.fuel_consumption', 0.1, !profile.has_car)}
          {numberInput('fuel_price_pln_per_l', 'profile.fuel_price', 0.01, !profile.has_car)}
        </div>
      </section>

      <section className="card">
        <h2>{t('profile.section.fares')}</h2>
        <div className="form-grid">
          {numberInput('transit_ticket_price_pln', 'profile.ticket', 0.1, profile.has_transit_pass)}
          {numberInput('transit_transfer_ticket_price_pln', 'profile.ticket_transfer', 0.1, profile.has_transit_pass)}
          {numberInput('taxi_base_fare_pln', 'profile.taxi_base', 0.5)}
          {numberInput('taxi_per_km_pln', 'profile.taxi_km', 0.1)}
        </div>
        <small className="muted">{t('profile.ticket.hint')}</small>
      </section>

      <section className="card">
        <h2>{t('profile.section.priority')}</h2>
        <div className="priorities">
          {PRIORITIES.map((priority) => (
            <label key={priority} className={`priority ${profile.priority === priority ? 'active' : ''}`}>
              <input
                type="radio"
                name="priority"
                checked={profile.priority === priority}
                onChange={() => update({ priority })}
              />
              <strong>{t(`profile.priority.${priority}`)}</strong>
              <small className="muted">{t(`profile.priority.${priority}.hint`)}</small>
            </label>
          ))}
        </div>
      </section>

      {save.isError && <ErrorNote error={save.error} />}

      <div className="form-actions">
        {savedAt !== null && <span className="saved">✓ {t('common.saved')}</span>}
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {t('common.save')}
        </button>
      </div>
    </form>
  )
}

export function ProfilePage() {
  const { t } = useI18n()
  const profile = useProfile()

  return (
    <>
      <PageHeader title={t('profile.title')} intro={t('profile.intro')} />
      {profile.isPending && <Loading />}
      {profile.isError && <ErrorNote error={profile.error} onRetry={() => void profile.refetch()} />}
      {profile.data && <ProfileForm initial={profile.data} />}
    </>
  )
}
