import { useAuth } from "./auth"

export function getToken(): string | null {
  try {
    const zustandToken = useAuth.getState().token
    if (zustandToken) return zustandToken
    const ls = localStorage.getItem("token")
    return ls
  } catch {
    return null
  }
}

export async function apiGet(path: string): Promise<{ ok: boolean; status: number; data: any }> {
  const token = getToken()
  const res = await fetch(`http://localhost:8000${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "omit",
  })
  let data: any = null
  try { data = await res.json() } catch { data = null }
  return { ok: res.ok, status: res.status, data }
}

export async function apiPost(path: string, body: any, headers: Record<string, string> = {}) {
  const token = getToken()
  const res = await fetch(`http://localhost:8000${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: JSON.stringify(body),
  })
  let data: any = null
  try { data = await res.json() } catch { data = null }
  return { ok: res.ok, status: res.status, data }
}

export async function apiPut(path: string, body: any, headers: Record<string, string> = {}) {
  const token = getToken()
  const res = await fetch(`http://localhost:8000${path}`, {
    method: "PUT",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: JSON.stringify(body),
  })
  let data: any = null
  try { data = await res.json() } catch { data = null }
  return { ok: res.ok, status: res.status, data }
}
