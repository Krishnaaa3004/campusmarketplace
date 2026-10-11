import { useState } from 'react'

// Password field with a Show/Hide toggle. Pass the usual input props (id, value, onChange…).
export default function PasswordInput({ className = '', autoComplete = 'current-password', ...props }) {
  const [shown, setShown] = useState(false)
  return (
    <div className={`relative ${className}`}>
      <input {...props} type={shown ? 'text' : 'password'} autoComplete={autoComplete} className="field-input pr-16" />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? 'Hide password' : 'Show password'}
        aria-pressed={shown}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-[12.5px] font-semibold text-ink-soft hover:text-ink"
      >
        {shown ? 'Hide' : 'Show'}
      </button>
    </div>
  )
}
