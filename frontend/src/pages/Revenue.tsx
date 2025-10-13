import { useEffect, useState } from "react"
import { apiGet } from "../store/api"

const formatCurrency = (cents: number) => `SGD ${(cents / 100).toFixed(2)}`
const formatDate = (value: string | null | undefined) => {
  if (!value) return "—"
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

type Summary = {
  captured_cents: number
  captured_count: number
}

type PaymentRecord = {
  payment_id: number
  ride_id: number
  amount_cents: number
  status: string
  bike_qr: string
  user_email?: string
  ride_started_at?: string | null
  ride_ended_at?: string | null
  authorized_at?: string | null
  captured_at?: string | null
  meters?: number
  seconds?: number
}

export default function Revenue() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [records, setRecords] = useState<PaymentRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [summaryRes, recordsRes] = await Promise.all([
        apiGet("/api/v1/payments/summary"),
        apiGet("/api/v1/payments/records"),
      ])
      if (!summaryRes.ok) {
        setError(`Failed to load revenue summary (${summaryRes.status})`)
        setSummary(null)
        setRecords([])
        setLoading(false)
        return
      }
      if (!recordsRes.ok) {
        setError(`Failed to load payment records (${recordsRes.status})`)
        setSummary(summaryRes.data as Summary)
        setRecords([])
        setLoading(false)
        return
      }
      setSummary(summaryRes.data as Summary)
      setRecords(Array.isArray(recordsRes.data?.records) ? (recordsRes.data.records as PaymentRecord[]) : [])
      setError(null)
      setLoading(false)
    }
    load()
  }, [])

  return (
    <div className="card">
      <h3>Platform Revenue</h3>
      {error && <div style={{ color: "#f87171", marginTop: 12 }}>{error}</div>}
      {summary ? (
        <div style={{ display: "flex", gap: 24, marginTop: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 12, textTransform: "uppercase", color: "#93c5fd" }}>Total Captured</div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>{formatCurrency(summary.captured_cents)}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, textTransform: "uppercase", color: "#93c5fd" }}>Captured Rides</div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>{summary.captured_count}</div>
          </div>
        </div>
      ) : loading ? (
        <div style={{ marginTop: 12 }}>Loading summary...</div>
      ) : null}

      <h4 style={{ marginTop: 24 }}>Payments</h4>
      {loading ? (
        <div>Loading payments...</div>
      ) : records.length === 0 ? (
        <div>No payments recorded yet.</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Ride</th>
                <th>Bike</th>
                <th>User</th>
                <th>Fare</th>
                <th>Status</th>
                <th>Started</th>
                <th>Ended</th>
                <th>Authorized</th>
                <th>Captured</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.payment_id}>
                  <td>{record.ride_id}</td>
                  <td>{record.bike_qr}</td>
                  <td>{record.user_email ?? "—"}</td>
                  <td>{formatCurrency(record.amount_cents)}</td>
                  <td style={{ textTransform: "capitalize" }}>{record.status}</td>
                  <td>{formatDate(record.ride_started_at)}</td>
                  <td>{formatDate(record.ride_ended_at)}</td>
                  <td>{formatDate(record.authorized_at)}</td>
                  <td>{formatDate(record.captured_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
