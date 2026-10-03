import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './useAuth.jsx'

const WishlistContext = createContext(null)

// Saved listings live in localStorage, one list per user (or "guest").
// Each entry is a snapshot of the listing so the wishlist page can render
// immediately; the page refreshes them from the API when it loads.
function storageKey(user) {
  return `cm_wishlist_${user?.id || 'guest'}`
}

function read(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function WishlistProvider({ children }) {
  const { user } = useAuth()
  const key = storageKey(user)
  const [items, setItems] = useState(() => read(key))

  useEffect(() => {
    setItems(read(key))
  }, [key])

  const persist = useCallback((next) => {
    setItems(next)
    try {
      localStorage.setItem(key, JSON.stringify(next))
    } catch {
      // storage full or blocked — keep the in-memory list
    }
  }, [key])

  const isSaved = useCallback((id) => items.some((l) => l.id === id), [items])

  const toggle = useCallback((listing) => {
    const saved = items.some((l) => l.id === listing.id)
    persist(saved ? items.filter((l) => l.id !== listing.id) : [listing, ...items])
    return !saved
  }, [items, persist])

  const remove = useCallback((id) => persist(items.filter((l) => l.id !== id)), [items, persist])

  const value = { items, count: items.length, isSaved, toggle, remove }

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>
}

export function useWishlist() {
  const ctx = useContext(WishlistContext)
  if (!ctx) throw new Error('useWishlist must be used inside WishlistProvider')
  return ctx
}
