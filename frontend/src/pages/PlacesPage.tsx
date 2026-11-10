import { useState } from 'react'

import { useDeletePlace, usePlaces } from '../api/hooks'
import type { Place } from '../api/types'
import { PlaceForm } from '../components/PlaceForm'
import { DeleteButton, ErrorNote, Loading, Modal, PageHeader } from '../components/ui'
import { useI18n } from '../i18n'
import { formatMoney } from '../lib/format'

/** undefined = closed, null = creating a new place, Place = editing it. */
type Editing = Place | null | undefined

export function PlacesPage() {
  const { t, locale } = useI18n()
  const places = usePlaces()
  const remove = useDeletePlace()
  const [editing, setEditing] = useState<Editing>(undefined)

  return (
    <>
      <PageHeader
        title={t('places.title')}
        intro={t('places.intro')}
        action={
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            + {t('places.add')}
          </button>
        }
      />

      {places.isPending && <Loading />}
      {places.isError && <ErrorNote error={places.error} onRetry={() => void places.refetch()} />}
      {remove.isError && <ErrorNote error={remove.error} />}
      {places.data?.length === 0 && <p className="muted">{t('places.empty')}</p>}

      <div className="list">
        {places.data?.map((place) => (
          <article key={place.id} className="card list-item">
            <div>
              <h3>
                📍 {place.name}
                {place.parking_cost_pln > 0 && (
                  <span className="badge">
                    {t('places.parking', { amount: formatMoney(place.parking_cost_pln, locale) })}
                  </span>
                )}
              </h3>
              {place.address && <p className="muted">{place.address}</p>}
            </div>
            <div className="list-actions">
              <button type="button" className="btn btn-small" onClick={() => setEditing(place)}>
                {t('common.edit')}
              </button>
              <DeleteButton onConfirm={() => remove.mutate(place.id)} disabled={remove.isPending} />
            </div>
          </article>
        ))}
      </div>

      {editing !== undefined && (
        <Modal title={editing ? t('places.edit') : t('places.add')} onClose={() => setEditing(undefined)}>
          <PlaceForm place={editing ?? undefined} onDone={() => setEditing(undefined)} />
        </Modal>
      )}
    </>
  )
}
