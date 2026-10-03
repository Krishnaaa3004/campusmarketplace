import { useState } from 'react'
import { initial } from '../lib/format.js'

// Profile picture with a coloured initial as fallback (no photo, or it failed to load).
export default function Avatar({ user, size = 28, className = 'bg-brand text-white' }) {
  const [failed, setFailed] = useState(null)
  const src = user?.avatar_url
  const style = { width: size, height: size, fontSize: Math.round(size * 0.42) }

  if (src && failed !== src) {
    return (
      <img
        src={src}
        alt=""
        onError={() => setFailed(src)}
        style={style}
        className="flex-none rounded-full object-cover"
      />
    )
  }
  return (
    <span style={style} className={`flex flex-none items-center justify-center rounded-full font-bold ${className}`}>
      {initial(user)}
    </span>
  )
}
