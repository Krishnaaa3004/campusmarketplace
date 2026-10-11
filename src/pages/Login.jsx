import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { authApi } from '../services/api.js'
import { trackEvent } from '../lib/analytics.js'
import PasswordInput from '../components/PasswordInput.jsx'

// Email + password. Accounts from before passwords existed get a one-time code instead
// (once), and are then made to create a password (see SetPasswordModal).
export default function Login() {
  const { login, loginWithCode } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [step, setStep] = useState('password') // 'password' | 'otp'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function goOn(u) {
    if (u?.profile_completed === false) navigate('/onboarding', { replace: true })
    else navigate(location.state?.from || '/marketplace', { replace: true })
  }

  async function submitPassword(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u = await login(email, password)
      trackEvent('login', { method: 'password' })
      goOn(u)
    } catch (err) {
      if (err.detail?.code === 'password_not_set') {
        // No password on this account yet: log in with an emailed code this one time.
        try {
          await authApi.requestLoginCode(email)
          setStep('otp')
        } catch (codeErr) {
          setError(codeErr.message)
        }
      } else {
        setError(err.message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u = await loginWithCode(email, otp)
      trackEvent('login', { method: 'email_code' })
      goOn(u) // the "Create a password" step appears on top until it's done
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto my-14 w-full max-w-[420px] rounded-slab border border-line bg-paper p-8 md:p-10">
      {step === 'password' ? (
        <>
          <h2 className="mb-2 text-[26px] font-bold">Welcome back</h2>
          <p className="mb-6 text-sm text-ink-soft">Log in with your college email and password.</p>

          <form onSubmit={submitPassword}>
            <label className="field-label" htmlFor="email">Email</label>
            <input id="email" type="email" required autoComplete="email" className="field-input mb-4" value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@medhaviskillsuniversity.edu.in" />

            <div className="flex items-center justify-between">
              <label className="field-label" htmlFor="password">Password</label>
              <Link to="/forgot-password" state={{ email }} className="mb-1.5 text-[13px] font-semibold text-brand hover:underline">
                Forgot password?
              </Link>
            </div>
            <PasswordInput id="password" required autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} placeholder="Your password" />

            {error && <p className="mt-3 text-[13px] text-coral">{error}</p>}
            <button className="btn-primary mt-5 w-full" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
          </form>
        </>
      ) : (
        <>
          <h2 className="mb-2 text-[26px] font-bold">Enter your code</h2>
          <p className="mb-6 text-sm text-ink-soft">
            Your account doesn't have a password yet, so we sent a 6-digit code to {email}. After this you'll create a password.
          </p>

          <form onSubmit={submitCode}>
            <label className="field-label" htmlFor="otp">Verification code</label>
            <input id="otp" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required
              className="field-input mb-4" value={otp}
              onChange={(e) => setOtp(e.target.value)} placeholder="123456" />
            {error && <p className="mb-3 text-[13px] text-coral">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? 'Checking…' : 'Log in'}</button>
          </form>

          <button className="btn-ghost mt-3 w-full" onClick={() => { setStep('password'); setOtp(''); setError('') }}>
            Use a different email
          </button>
        </>
      )}

      <p className="mt-5 flex gap-2 rounded-xl bg-brand-tint px-3.5 py-3 text-[13px] text-brand-deep">
        🔒 CampusMarket is only available to verified students from approved institutional domains.
      </p>

      <p className="mt-5 text-center text-[13.5px] text-ink-soft">
        New here? <Link to="/signup" state={{ email }} className="font-semibold text-brand">Join your campus</Link>
      </p>
    </div>
  )
}
