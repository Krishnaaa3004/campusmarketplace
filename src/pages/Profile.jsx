import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { listingsApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import { useAuth } from '../hooks/useAuth.jsx'
import { useWishlist } from '../hooks/useWishlist.jsx'
import { useToast } from '../hooks/useToast.jsx'
import { initial } from '../lib/format.js'

export default function Profile() {
  const { user, isSeller, isAdmin, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const typeLabel = isAdmin ? 'Admin' : isSeller ? 'Seller' : 'Buyer'
  const details = [user.college, user.course, user.year].filter(Boolean)

  return (
    <div className="mx-auto max-w-[880px] px-6 py-9">
      {location.state?.needsSeller && !isSeller && (
        <p className="mb-5 rounded-xl bg-sun/25 px-4 py-3 text-[13.5px] text-[#946B00]">
          Selling is available to seller accounts. Switch below to start listing items.
        </p>
      )}

      <section className="mb-6 flex flex-wrap items-center gap-5 rounded-slab border border-line bg-paper p-6 md:p-8">
        <div className="flex h-[72px] w-[72px] flex-none items-center justify-center rounded-full bg-brand text-[28px] font-bold text-white">
          {initial(user)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[26px] font-bold leading-tight">{user.name || 'Your account'}</h1>
            <span className={`badge ${isSeller ? 'bg-brand-tint text-brand' : 'bg-leaf/10 text-leaf'}`}>{typeLabel}</span>
          </div>
          <p className="mt-1 truncate text-[14px] text-ink-soft">{user.email}</p>
          {details.length > 0 && <p className="mt-0.5 text-[13.5px] text-ink-faint">{details.join(' · ')}</p>}
        </div>
        <button className="btn-ghost btn-sm" onClick={() => logout().then(() => navigate('/'))}>Log Out</button>
      </section>

      {isSeller ? <SellerSection user={user} /> : <BuyerSection />}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <WishlistTile />
        <Tile
          to="/interests"
          emoji="✨"
          title="Your interests"
          body={user.interests?.length ? user.interests.join(', ') : 'Pick categories to get better recommendations.'}
          cta="Edit interests"
        />
      </div>
    </div>
  )
}

function SellerSection({ user }) {
  const { data, loading } = useApi(
    () => listingsApi.list({ seller_id: user.id, include_sold: true }),
    [user.id]
  )
  const items = data?.items || []
  const count = (status) => items.filter((l) => l.status === status).length
  const stats = [
    { label: 'Active', value: count('available') },
    { label: 'Reserved', value: count('reserved') },
    { label: 'Sold', value: count('sold') },
  ]

  return (
    <section className="rounded-slab border border-line bg-paper p-6 md:p-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[19px] font-semibold">Your shop</h2>
        <div className="flex gap-2">
          <Link to="/dashboard" className="btn-ghost btn-sm">My Listings</Link>
          <Link to="/sell" className="btn-accent btn-sm">Sell an Item</Link>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-card bg-bg px-4 py-3.5">
            <p className="font-display text-[26px] font-bold leading-none">{loading ? '–' : s.value}</p>
            <p className="mt-1.5 text-[13px] text-ink-soft">{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function BuyerSection() {
  const { becomeSeller } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  async function upgrade() {
    setBusy(true)
    try {
      await becomeSeller()
      toast('You can now sell on CampusMarket')
      navigate('/sell')
    } catch (err) {
      toast(err.message || 'Could not switch account')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-slab border border-line bg-paper p-6 md:p-8">
      <div>
        <h2 className="text-[19px] font-semibold">Want to sell something?</h2>
        <p className="mt-1 max-w-md text-[14px] text-ink-soft">
          Your account is set up for buying. Switch to a seller account to list items. You'll still be able to buy.
        </p>
      </div>
      <button className="btn-accent" disabled={busy} onClick={upgrade}>
        {busy ? 'Switching…' : 'Become a Seller'}
      </button>
    </section>
  )
}

function WishlistTile() {
  const { count } = useWishlist()
  return (
    <Tile
      to="/wishlist"
      emoji="♡"
      title="My Wishlist"
      body={count ? `${count} saved item${count === 1 ? '' : 's'}` : 'Nothing saved yet.'}
      cta="View wishlist"
    />
  )
}

function Tile({ to, emoji, title, body, cta }) {
  return (
    <Link to={to} className="group block rounded-card border border-line bg-paper p-5 transition hover:-translate-y-[2px] hover:shadow-lift">
      <span className="mb-2 block text-[22px]" aria-hidden>{emoji}</span>
      <h3 className="text-[16px] font-semibold">{title}</h3>
      <p className="mt-1 line-clamp-2 text-[13.5px] text-ink-soft">{body}</p>
      <p className="mt-3 text-[13.5px] font-semibold text-brand group-hover:underline">{cta} →</p>
    </Link>
  )
}
