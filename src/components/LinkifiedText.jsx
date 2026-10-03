// Renders plain text with any web links turned into clickable links that open
// in a new tab. Builds React elements (no innerHTML), so user text can't inject markup.
const URL_RE = /((?:https?:\/\/|www\.)[^\s<]+)/gi
// Trailing punctuation usually belongs to the sentence, not the link.
const TRAILING = /[.,!?;:'")\]]+$/

export default function LinkifiedText({ text }) {
  if (!text) return null
  return text.split(URL_RE).map((part, i) => {
    if (i % 2 === 0) return part // odd indexes are the captured links
    const trail = part.match(TRAILING)?.[0] || ''
    const link = trail ? part.slice(0, -trail.length) : part
    const href = /^https?:\/\//i.test(link) ? link : `https://${link}`
    return (
      <span key={i}>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="break-all font-medium text-brand underline underline-offset-2 hover:text-brand-deep"
        >
          {link}
        </a>
        {trail}
      </span>
    )
  })
}
