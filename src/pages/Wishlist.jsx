import { useEffect, useState } from 'react'
import { listingsApi } from '../services/api.js'
import { useWishlist } from '../hooks/useWishlist.jsx'
import ListingCard from '../components/ListingCard.jsx'
import EmptyState from '../components/EmptyState.jsx'

export default function Wishlist() {
  const { items } = useWishlist()
  // Fresh copies from the API (price/status may have changed since saving),
  // keyed by id. Falls back to the saved snapshot if a fetch fails.
  const [fresh, setFresh] = useState({})

  useEffect(() => {
    let cancelled = false
    Promise.allSettled(items.map((l) => listingsApi.get(l.id))).then((results) => {
      if (cancelled) return
      const next = {}
      results.forEach((r, i) => {
        if (r.status === 'fulfilled' && r.value) next[items[i].id] = r.value
      })
      setFresh(next)
    })
    return () => { cancelled = true }
    // Only refetch when the set of saved ids changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.map((l) => l.id).join(',')])

  const listings = items.map((l) => fresh[l.id] || l)

  return (
    <div className="mx-auto max-w-[1180px] px-6 py-9">
      <div className="mb-6 flex items-baseline gap-3">
        <h1 className="text-[30px] font-bold">My Wishlist</h1>
        {listings.length > 0 && (
          <span className="text-[14.5px] text-ink-faint">
            {listings.length} saved item{listings.length === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {listings.length === 0 ? (
        <EmptyState
          emoji="♡"
          title="Your wishlist is empty"
          body="Tap the heart on any listing to save it here for later."
          actionLabel="Browse Marketplace"
          actionTo="/marketplace"
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {listings.map((l) => <ListingCard key={l.id} listing={l} />)}
        </div>
      )}
    </div>
  )
}
