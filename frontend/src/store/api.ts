import { useAuth } from "./auth"

export type ApiService = "main" | "pricing" | "battery" | "weather"

const API_BASES: Record<ApiService, string> = {
  main: import.meta.env.VITE_API_MAIN ?? "http://localhost:8000",
  pricing: import.meta.env.VITE_API_PRICE ?? "http://localhost:8101",
  battery: import.meta.env.VITE_API_BATTERY ?? "http://localhost:8103",
  weather: import.meta.env.VITE_API_WEATHER ?? "http://localhost:8102",
}

function resolveBase(service: ApiService): string {
  return API_BASES[service] ?? API_BASES.main
}

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

export async function apiGet(
  path: string,
  service: ApiService = "main"
): Promise<{ ok: boolean; status: number; data: any }> {
  const token = getToken()
  try {
    const res = await fetch(`${resolveBase(service)}${path}`, {
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
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export async function apiPost(
  path: string,
  body: any,
  headers: Record<string, string> = {},
  service: ApiService = "main"
) {
  const token = getToken()
  try {
    const res = await fetch(`${resolveBase(service)}${path}`, {
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
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

export async function apiPut(
  path: string,
  body: any,
  headers: Record<string, string> = {},
  service: ApiService = "main"
) {
  const token = getToken()
  try {
    const res = await fetch(`${resolveBase(service)}${path}`, {
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
  } catch {
    return { ok: false, status: 0, data: null }
  }
}
