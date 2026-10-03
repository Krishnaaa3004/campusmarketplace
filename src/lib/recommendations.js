// Lightweight, content-based recommendation signal — no ML model, no server
// round trip needed for it. We track which listing categories a student
// actually opens, in localStorage, and use that as an affinity score.
// This is intentionally simple: it's a real, explainable heuristic
// (content-based filtering on category + recency), not a black box.

const KEY = 'cm_view_history'
const MAX_HISTORY = 30
// Chosen interests give a new student relevant results before they have browsed anything.
// Worth roughly one or two recent views, so real browsing quickly takes over.
const INTEREST_WEIGHT = 2

export function recordView(listing) {
  if (!listing?.category) return
  try {
    const history = readHistory()
    history.push({ category: listing.category, campus_id: listing.campus_id, ts: Date.now() })
    localStorage.setItem(KEY, JSON.stringify(history.slice(-MAX_HISTORY)))
  } catch {
    // localStorage can throw in private browsing — recommendations just fall back silently.
  }
}

export function readHistory() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

// Returns { hasHistory, categoryScores } — more recent views count for more,
// so recommendations shift as interest shifts rather than sticking forever.
export function categoryAffinity(interests = []) {
  const history = readHistory()
  const scores = {}
  interests.forEach((c) => {
    scores[c] = (scores[c] || 0) + INTEREST_WEIGHT
  })
  history.forEach((entry, i) => {
    const recencyWeight = 1 + i / history.length // later entries weigh slightly more
    scores[entry.category] = (scores[entry.category] || 0) + recencyWeight
  })
  return { hasHistory: history.length > 0 || interests.length > 0, categoryScores: scores }
}
