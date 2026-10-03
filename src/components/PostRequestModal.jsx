import { useState } from 'react'
import Modal from './Modal.jsx'
import { requestsApi } from '../services/api.js'
import { useToast } from '../hooks/useToast.jsx'

const MAX = 70

export default function PostRequestModal({ open, onClose, onPosted }) {
  const toast = useToast()
  const [product, setProduct] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function close() {
    setError('')
    onClose()
  }

  async function submit(e) {
    e.preventDefault()
    if (!product.trim()) return setError("Tell sellers what you're looking for")
    setBusy(true)
    setError('')
    try {
      await requestsApi.create({ product: product.trim(), description: description.trim() })
      toast('Request sent to sellers')
      onPosted?.()
      setProduct('')
      setDescription('')
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Post a Request">
      <form onSubmit={submit}>
        <p className="-mt-2 mb-4 text-[13.5px] text-ink-soft">Sellers on your campus get notified and can reach out to you.</p>

        <Field
          id="req-product"
          label="What are you looking for?"
          value={product}
          onChange={setProduct}
          placeholder="e.g. Casio fx-991CW calculator"
          required
        />
        <Field
          id="req-description"
          label="One-line description"
          value={description}
          onChange={setDescription}
          placeholder="e.g. Need it for tomorrow's exam, can rent too"
        />

        {error && <p className="mb-3 text-[13px] text-coral">{error}</p>}
        <div className="flex gap-2.5">
          <button type="button" className="btn-ghost flex-1" onClick={close}>Cancel</button>
          <button className="btn-primary flex-1" disabled={busy}>{busy ? 'Posting…' : 'Post Request'}</button>
        </div>
      </form>
    </Modal>
  )
}

function Field({ id, label, value, onChange, placeholder, required }) {
  return (
    <div className="mb-4">
      <div className="flex items-baseline justify-between">
        <label className="field-label" htmlFor={id}>{label}</label>
        <span className={`text-[12px] tabular-nums ${value.length >= MAX ? 'text-coral' : 'text-ink-faint'}`}>
          {value.length}/{MAX}
        </span>
      </div>
      <input
        id={id}
        required={required}
        maxLength={MAX}
        className="field-input"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/[\r\n]+/g, ' '))}
        placeholder={placeholder}
      />
    </div>
  )
}
