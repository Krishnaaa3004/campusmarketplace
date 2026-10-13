import { createContext, useContext, useEffect, useState } from 'react'
import { authApi } from '../services/api.js'
import { syncHistory } from '../lib/recommendations.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authApi
      .me()
      .then((u) => {
        setUser(u)
        // Stay logged in: each visit renews the session for another 30 days.
        if (u) {
          authApi
            .refreshSession()
            .then((res) => res?.token && localStorage.setItem('cm_token', res.token))
            .catch(() => {})
        }
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  // Merge this account's saved browsing history with anything viewed as a guest on this device.
  useEffect(() => {
    if (user) syncHistory(user)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  function startSession(res) {
    if (res?.token) localStorage.setItem('cm_token', res.token)
    setUser(res.user)
    return res.user
  }

  const value = {
    user,
    loading,
    isVerified: Boolean(user?.verified),
    // Owners (OWNER_EMAILS on the backend) and the admins they approved.
    isAdmin: Boolean(user?.is_admin || user?.role === 'admin'),
    // Only owners can approve or remove admins.
    isOwner: Boolean(user?.is_owner),
    // Sellers can buy and sell; buyers can only buy. Admins can do everything.
    isSeller: user?.account_type === 'seller' || user?.role === 'admin',
    // Accounts from before passwords existed must create one before doing anything else.
    needsPassword: Boolean(user && user.has_password === false),
    async login(email, password) {
      return startSession(await authApi.login(email, password))
    },
    async loginWithCode(email, otp) {
      return startSession(await authApi.loginWithCode(email, otp))
    },
    async signupVerify(payload) {
      return startSession(await authApi.signupVerify(payload))
    },
    async resetPassword(payload) {
      return startSession(await authApi.resetPassword(payload))
    },
    async setPassword(password, confirmPassword) {
      // Returns a fresh session: changing the password logs out the old one.
      return startSession(await authApi.setPassword(password, confirmPassword))
    },
    async completeProfile(payload) {
      const updated = await authApi.completeProfile(payload)
      setUser(updated)
      return updated
    },
    async saveInterests(interests) {
      const updated = await authApi.saveInterests(interests)
      setUser(updated)
      return updated
    },
    async becomeSeller() {
      const updated = await authApi.setAccountType('seller')
      setUser(updated)
      return updated
    },
    async updateProfile(payload) {
      const updated = await authApi.updateProfile(payload)
      setUser(updated)
      return updated
    },
    async uploadAvatar(file) {
      const updated = await authApi.uploadAvatar(file)
      setUser(updated)
      return updated
    },
    async removeAvatar() {
      const updated = await authApi.removeAvatar()
      setUser(updated)
      return updated
    },
    async logout() {
      await authApi.logout()
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
