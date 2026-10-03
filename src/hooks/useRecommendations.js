import { useMemo } from 'react'
import { listingsApi } from '../services/api.js'
import { useApi } from './useApi.js'
import { categoryAffinity } from '../lib/recommendations.js'
import { useAuth } from './useAuth.jsx'

// One hook, two callers (Marketplace, ListingDetail). Reads the client-side
// affinity signal once per mount so both consumers score against the same snapshot.
export function useRecommendations({ excludeId } = {}) {
  const { user } = useAuth()
  const { hasHistory, categoryScores } = useMemo(() => categoryAffinity(user?.interests || []), [user?.interests])

  const { data, loading } = useApi(
    () => listingsApi.recommended({ excludeId, campusId: user?.campus_id, categoryScores }),
    [excludeId, user?.campus_id, hasHistory, user?.interests]
  )

  return {
    items: data?.items || [],
    personalized: Boolean(data?.personalized),
    loading,
  }
}
