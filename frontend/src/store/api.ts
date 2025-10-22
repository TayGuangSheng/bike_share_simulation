import { useAuth } from "./auth"

export type ApiService = "main" | "pricing" | "battery" | "weather"

export type ChaosMetadata = {
  effect: string | null
  delaySeconds: number | null
  stale: boolean
  state: string | null
}

const API_BASES: Record<ApiService, string> = {
  main: import.meta.env.VITE_API_MAIN ?? "http://localhost:8000",
  pricing: import.meta.env.VITE_API_PRICE ?? "http://localhost:8101",
  battery: import.meta.env.VITE_API_BATTERY ?? "http://localhost:8103",
  weather: import.meta.env.VITE_API_WEATHER ?? "http://localhost:8102",
}

function resolveBase(service: ApiService): string {
  return API_BASES[service] ?? API_BASES.main
}

function parseDelay(raw: string | null): number | null {
  if (!raw) return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

function extractChaos(res: Response): ChaosMetadata | null {
  const effect = res.headers.get("X-Chaos-Effect")
  const state = res.headers.get("X-Chaos-State")
  const stale = res.headers.get("X-Chaos-Stale")
  const delay = parseDelay(res.headers.get("X-Chaos-Delay"))
  if (!effect && !state && !stale && delay === null) {
    return null
  }
  return {
    effect,
    state,
    delaySeconds: delay,
    stale: stale === "true",
  }
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

type ApiResponse<T = any> = {
  ok: boolean
  status: number
  data: T
  chaos: ChaosMetadata | null
}

async function handleJson(res: Response): Promise<any> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

export async function apiGet<T = any>(
  path: string,
  service: ApiService = "main"
): Promise<ApiResponse<T>> {
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
    const data = await handleJson(res)
    return { ok: res.ok, status: res.status, data, chaos: extractChaos(res) }
  } catch {
    return { ok: false, status: 0, data: null as T, chaos: null }
  }
}

export async function apiPost<T = any>(
  path: string,
  body: any,
  headers: Record<string, string> = {},
  service: ApiService = "main"
): Promise<ApiResponse<T>> {
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
    const data = await handleJson(res)
    return { ok: res.ok, status: res.status, data, chaos: extractChaos(res) }
  } catch {
    return { ok: false, status: 0, data: null as T, chaos: null }
  }
}

export async function apiPut<T = any>(
  path: string,
  body: any,
  headers: Record<string, string> = {},
  service: ApiService = "main"
): Promise<ApiResponse<T>> {
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
    const data = await handleJson(res)
    return { ok: res.ok, status: res.status, data, chaos: extractChaos(res) }
  } catch {
    return { ok: false, status: 0, data: null as T, chaos: null }
  }
}
