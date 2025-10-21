import { useEffect, useState } from "react"
import { apiGet } from "../store/api"

type PricingSnapshot = {
  multiplier: number
  weather: string
  active_rides: number
  demand_factor: number
  weather_factor: number
}

export function usePricingMultiplier(pollMs: number = 15000) {
  const [snapshot, setSnapshot] = useState<PricingSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    const res = await apiGet("/api/v1/pricing/current", "pricing")
    if (!res.ok) {
      setError(`Failed to load multiplier (${res.status})`)
      return
    }
    setSnapshot(res.data as PricingSnapshot)
    setError(null)
    setLoading(false)
  }

  useEffect(() => {
    load()
    const id = window.setInterval(load, pollMs)
    return () => window.clearInterval(id)
  }, [pollMs])

  return { snapshot, loading, error }
}
