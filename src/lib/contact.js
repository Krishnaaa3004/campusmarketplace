import { contactApi } from '../services/api.js'
import { trackEvent } from './analytics.js'

// Phone numbers and emails aren't in any page data. When a student taps a contact button we
// ask the server for that ONE person's WhatsApp or email (logged and rate-limited there),
// then open WhatsApp / Gmail. The tab opens first so popup blockers allow it.
export async function openContact({ targetType, targetId, channel, subject, message }) {
  const win = window.open('', '_blank')
  if (win) win.opener = null
  try {
    const contact = await contactApi.reveal(targetType, targetId, channel)
    trackEvent('contact_seller', { item_type: targetType, channel })
    const url = channel === 'whatsapp'
      ? `https://wa.me/${contact.phone}?text=${encodeURIComponent(message)}`
      : `https://mail.google.com/mail/?${new URLSearchParams({ view: 'cm', fs: '1', to: contact.email, su: subject, body: message })}`
    if (win) win.location.href = url
    else window.location.href = url
  } catch (err) {
    win?.close()
    throw err
  }
}
