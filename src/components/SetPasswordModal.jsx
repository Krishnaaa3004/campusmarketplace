import { useState } from 'react'
import Modal from './Modal.jsx'
import PasswordInput from './PasswordInput.jsx'
import { useAuth } from '../hooks/useAuth.jsx'
import { useToast } from '../hooks/useToast.jsx'
import { PASSWORD_HINT, newPasswordErrors } from '../lib/password.js'

// Mandatory for accounts created before passwords existed. Rendered on every page, can't be
// closed (no close button; Escape and backdrop clicks do nothing), and the protected pages
// behind it don't render (RequireAuth). The API refuses everything else for these accounts
// too, so it can't be skipped. Logging out is the only other way out.
export default function SetPasswordModal() {
  const { needsPassword, setPassword: savePassword, logout } = useAuth()
  const toast = useToast()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (!needsPassword) return null

  async function save(e) {
    e.preventDefault()
    setError('')
    const problems = newPasswordErrors(password, confirm)
    setFieldErrors(problems)
    if (Object.keys(problems).length) return
    setBusy(true)
    try {
      await savePassword(password, confirm)
      toast('Password created. Next time, just log in with it.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={() => {}} title="Create a password">
      <p className="mb-4 text-[13.5px] text-ink-soft">
        CampusMarket now uses passwords. Create one to keep going. You'll use it to log in from now on.
      </p>
      <form onSubmit={save} noValidate>
        <label className="field-label" htmlFor="sp-password">Create password</label>
        <PasswordInput id="sp-password" autoFocus autoComplete="new-password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="Create a password" />
        {fieldErrors.password
          ? <p className="mt-1.5 text-[13px] text-coral">{fieldErrors.password}</p>
          : <p className="mt-1.5 text-[12.5px] text-ink-faint">{PASSWORD_HINT}</p>}

        <label className="field-label mt-4" htmlFor="sp-confirm">Confirm password</label>
        <PasswordInput id="sp-confirm" autoComplete="new-password" value={confirm}
          onChange={(e) => setConfirm(e.target.value)} placeholder="Type it again" />
        {fieldErrors.confirm && <p className="mt-1.5 text-[13px] text-coral">{fieldErrors.confirm}</p>}

        {error && <p className="mt-3 text-[13px] text-coral">{error}</p>}
        <button className="btn-primary mt-5 w-full" disabled={busy}>{busy ? 'Saving…' : 'Save password'}</button>
      </form>
      <button type="button" onClick={() => logout()} className="mt-3 w-full text-center text-[12.5px] text-ink-faint hover:text-ink">
        Log out
      </button>
    </Modal>
  )
}
