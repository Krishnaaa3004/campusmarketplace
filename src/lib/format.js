export function formatPrice(price) {
  if (price === 0) return 'Free'
  return `₹${Number(price).toLocaleString('en-IN')}`
}

// WhatsApp number for "Contact Seller", in international format without "+" (91 = India).
const SELLER_WHATSAPP = '917008699207'

export function contactLink(listing, { phone = SELLER_WHATSAPP } = {}) {
  const text = `Hi! I'm interested in your ${listing.title} listed on CampusMarket. Is it still available?`
  return {
    whatsapp: `https://wa.me/${phone}?text=${encodeURIComponent(text)}`,
    email: `mailto:?subject=${encodeURIComponent(`CampusMarket — ${listing.title}`)}&body=${encodeURIComponent(text)}`,
  }
}

export function titleCase(s = '') {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

// First letter of a user's name (or email) for avatar circles.
export function initial(user) {
  return (user?.name || user?.email || '?').trim().charAt(0).toUpperCase()
}
