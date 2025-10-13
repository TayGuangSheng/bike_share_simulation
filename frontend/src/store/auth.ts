import { create } from 'zustand'

type AuthState = {
  token: string | null
  setToken: (t: string | null) => void
}

export const useAuth = create<AuthState>((set) => ({
  token: typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null,
  setToken: (t) => {
    try {
      if (t) localStorage.setItem('token', t)
      else localStorage.removeItem('token')
    } catch {}
    set({ token: t })
  }
}))
