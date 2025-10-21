import { useEffect, useState } from "react"
import { apiGet } from "../store/api"

export default function Bikes() {
  const [bikes, setBikes] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      const { ok, status, data } = await apiGet("/api/v1/bikes")
      if (!ok) {
        if (cancelled) return
        setBikes([])
        setError(status === 401 ? "Please log in to view bikes." : `Failed to load bikes (${status})`)
        return
      }
      if (!Array.isArray(data)) {
        if (cancelled) return
        setBikes([])
        setError("Unexpected response from server.")
        return
      }
      if (cancelled) return
      setError(null)
      setBikes(data)
    }

    load()
    const intervalId = window.setInterval(load, 2000)
    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const formatBattery = (value: any) => {
    if (typeof value === "number" && Number.isFinite(value)) return `${value}%`
    if (typeof value === "string") return value
    return "-"
  }

  const formatCoord = (value: any) => (typeof value === "number" && Number.isFinite(value) ? value.toFixed(5) : "-")

  return (
    <div className="card">
      <h3>Bikes</h3>
      {error && <div className="p-2" style={{ color: "#f87171" }}>{error}</div>}
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>QR</th>
            <th>Status</th>
            <th>Lock</th>
            <th>Battery</th>
            <th>Lat</th>
            <th>Lon</th>
          </tr>
        </thead>
        <tbody>
          {bikes.map((b) => (
            <tr key={b.id}>
              <td>{b.id}</td>
              <td>{b.qr_public_id}</td>
              <td>{b.status}</td>
              <td>{b.lock_state}</td>
              <td>{formatBattery(b.battery_pct)}</td>
              <td>{formatCoord(b.lat)}</td>
              <td>{formatCoord(b.lon)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
