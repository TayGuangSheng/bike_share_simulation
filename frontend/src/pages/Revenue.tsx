import { useEffect, useMemo, useState } from "react"
import { apiGet, apiPost, apiPut } from "../store/api"

const formatCurrency = (cents: number) => `SGD ${(cents / 100).toFixed(2)}`
const formatDate = (value: string | null | undefined) => {
  if (!value) return "-"
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
  refunded_at?: string | null
  refund_reason?: string | null
  meters?: number
  seconds?: number
}

type PricingConfig = {
  weather: string
  base_multiplier: number
  demand_slope: number
  demand_threshold: number
  min_multiplier: number
  max_multiplier: number
}

type PricingSnapshot = {
  multiplier: number
  weather: string
  active_rides: number
  demand_factor: number
  weather_factor: number
}

const weatherOptions = [
  { value: "clear", label: "Clear" },
  { value: "rain", label: "Rain" },
  { value: "storm", label: "Storm" },
]

export default function Revenue() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [records, setRecords] = useState<PaymentRecord[]>([])
  const [config, setConfig] = useState<PricingConfig | null>(null)
  const [snapshot, setSnapshot] = useState<PricingSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [refundProcessing, setRefundProcessing] = useState<number | null>(null)

  // sample fare preview (10 min, 2 km) - display only
  const sampleFareCents = useMemo(() => {
    if (!snapshot) return null
    // Default plan estimate; backend still computes canonical fare at lock
    const base_cents = 100
    const per_min_cents = 20
    const per_km_cents = 60
    const minutes = 10
    const km = 2
    const planSurge = 1.0
    const raw = (base_cents + per_min_cents * minutes + per_km_cents * km) * planSurge * snapshot.multiplier
    return Math.round(raw)
  }, [snapshot])

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)
    setNotice(null)
    const [summaryRes, recordsRes, configRes, currentRes] = await Promise.all([
      apiGet("/api/v1/payments/summary"),
      apiGet("/api/v1/payments/records"),
      apiGet("/api/v1/pricing/config"),
      apiGet("/api/v1/pricing/current"),
    ])

    if (!summaryRes.ok) {
      setError(`Failed to load revenue summary (${summaryRes.status})`)
      setLoading(false)
      return
    }
    setSummary(summaryRes.data as Summary)

    if (!recordsRes.ok) {
      setError(`Failed to load payment records (${recordsRes.status})`)
      setRecords([])
    } else {
      setRecords(Array.isArray(recordsRes.data?.records) ? (recordsRes.data.records as PaymentRecord[]) : [])
    }

    if (!configRes.ok) {
      setError(prev => prev ?? `Failed to load pricing config (${configRes.status})`)
      setConfig(null)
    } else {
      const cfg = configRes.data as PricingConfig
      setConfig(cfg)
    }

    if (!currentRes.ok) {
      setError(prev => prev ?? `Failed to load pricing multiplier (${currentRes.status})`)
      setSnapshot(null)
    } else {
      setSnapshot(currentRes.data as PricingSnapshot)
    }

    if (!summaryRes.ok || !recordsRes.ok || !configRes.ok || !currentRes.ok) {
      setLoading(false)
      return
    }

    setError(null)
    setLoading(false)
  }

  const updateConfigField = <K extends keyof PricingConfig>(key: K, value: PricingConfig[K]) => {
    setConfig(prev => (prev ? { ...prev, [key]: value } : prev))
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    setNotice(null)
    const payload: any = { weather: config.weather }
    if (showAdvanced) {
      payload.base_multiplier = config.base_multiplier
      payload.demand_slope = config.demand_slope
      payload.demand_threshold = config.demand_threshold
      payload.min_multiplier = config.min_multiplier
      payload.max_multiplier = config.max_multiplier
    }
    const res = await apiPut("/api/v1/pricing/config", payload)
    setSaving(false)
    if (!res.ok) {
      setError(`Failed to update pricing (${res.status})`)
      return
    }
    setError(null)
    setConfig(res.data as PricingConfig)
    loadCurrent()
  }

  async function loadCurrent() {
    const current = await apiGet("/api/v1/pricing/current")
    if (current.ok) {
      setSnapshot(current.data as PricingSnapshot)
    }
  }

  const handleRefund = async (paymentId: number) => {
    setError(null)
    setNotice(null)
    setRefundProcessing(paymentId)
    const res = await apiPost(
      "/api/v1/payments/refund",
      { payment_id: paymentId },
      { "Idempotency-Key": `refund-${paymentId}-${Date.now()}` },
    )
    if (!res.ok) {
      const message =
        typeof res.data?.detail === "string" ? res.data.detail : `Refund failed (${res.status})`
      setError(message)
      setRefundProcessing(null)
      return
    }
    await loadAll()
    setRefundProcessing(null)
    setNotice("Payment refunded.")
  }

  return (
    <div className="card">
      <h3>Platform Revenue</h3>
      {error && <div style={{ color: "#f87171", marginTop: 12 }}>{error}</div>}
      {notice && !error && <div style={{ color: "#34d399", marginTop: 12 }}>{notice}</div>}
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
          {snapshot && (
            <div style={{ minWidth: 360 }}>
              <div style={{ fontSize: 12, textTransform: "uppercase", color: "#93c5fd", marginBottom: 6 }}>
                Current Pricing
              </div>
              <table className="table" style={{ width: "100%" }}>
                <tbody>
                  <tr>
                    <td>Weather</td>
                    <td style={{ textTransform: "capitalize" }}>{snapshot.weather}</td>
                  </tr>
                  <tr>
                    <td>Active Rides</td>
                    <td>{snapshot.active_rides}</td>
                  </tr>
                  <tr>
                    <td>Weather Factor</td>
                    <td>{snapshot.weather_factor.toFixed(2)}x</td>
                  </tr>
                  <tr>
                    <td>Demand Factor</td>
                    <td>{snapshot.demand_factor.toFixed(2)}x</td>
                  </tr>
                  <tr>
                    <td>Effective Multiplier</td>
                    <td style={{ fontWeight: 600 }}>{snapshot.multiplier.toFixed(2)}x</td>
                  </tr>
                  {sampleFareCents !== null && (
                    <tr>
                      <td>Sample Fare (10 min, 2 km)</td>
                      <td style={{ fontWeight: 600 }}>{formatCurrency(sampleFareCents)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : loading ? (
        <div style={{ marginTop: 12 }}>Loading summary...</div>
      ) : null}

      <section style={{ marginTop: 24 }}>
        <h4>Dynamic Pricing Controls</h4>
        {config ? (
          <div style={{ display: "grid", gap: 12, marginTop: 12, maxWidth: 640 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span>Weather</span>
              <select
                className="input"
                value={config.weather}
                onChange={(e) => updateConfigField("weather", e.target.value)}
              >
                {weatherOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ marginTop: 8 }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={showAdvanced} onChange={(e) => setShowAdvanced(e.target.checked)} />
                <span>Show advanced controls</span>
              </label>
            </div>
            {showAdvanced && (
              <label style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <span>Base Multiplier</span>
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  min="0.1"
                  value={config.base_multiplier}
                  onChange={(e) => updateConfigField("base_multiplier", parseFloat((e.target as HTMLInputElement).value))}
                />
              </label>
            )}
            {showAdvanced && (
              <label style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <span>Demand Slope</span>
                <input
                  className="input"
                  type="number"
                  step="0.005"
                  min="0"
                  value={config.demand_slope}
                  onChange={(e) => updateConfigField("demand_slope", parseFloat((e.target as HTMLInputElement).value))}
                />
              </label>
            )}
            {showAdvanced && (
              <label style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <span>Demand Threshold</span>
                <input
                  className="input"
                  type="number"
                  min="0"
                  value={config.demand_threshold}
                  onChange={(e) => updateConfigField("demand_threshold", parseInt((e.target as HTMLInputElement).value, 10) || 0)}
                />
              </label>
            )}
            {showAdvanced && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <span>Min Multiplier</span>
                  <input
                    className="input"
                    type="number"
                    step="0.05"
                    min="0.1"
                    value={config.min_multiplier}
                    onChange={(e) => updateConfigField("min_multiplier", parseFloat((e.target as HTMLInputElement).value))}
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <span>Max Multiplier</span>
                  <input
                    className="input"
                    type="number"
                    step="0.05"
                    min="0.1"
                    value={config.max_multiplier}
                    onChange={(e) => updateConfigField("max_multiplier", parseFloat((e.target as HTMLInputElement).value))}
                  />
                </label>
              </div>
            )}
            <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
              <button className="btn" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
              <button className="btn secondary" onClick={loadCurrent}>
                Refresh Multiplier
              </button>
            </div>
          </div>
        ) : (
          <div>Loading pricing controls...</div>
        )}
      </section>

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
                <th>Refunded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.payment_id}>
                  <td>{record.ride_id}</td>
                  <td>{record.bike_qr}</td>
                  <td>{record.user_email ?? "-"}</td>
                  <td>{formatCurrency(record.amount_cents)}</td>
                  <td style={{ textTransform: "capitalize" }}>
                    {record.status.replace(/_/g, " ")}
                    {record.status === "refund_pending" && record.refund_reason ? (
                      <div style={{ fontSize: 12, color: "#f59e0b" }}>Reason: {record.refund_reason}</div>
                    ) : null}
                  </td>
                  <td>{formatDate(record.ride_started_at)}</td>
                  <td>{formatDate(record.ride_ended_at)}</td>
                  <td>{formatDate(record.authorized_at)}</td>
                  <td>{formatDate(record.captured_at)}</td>
                  <td>{formatDate(record.refunded_at)}</td>
                  <td>
                    {["captured", "refund_pending"].includes(record.status) ? (
                      <button
                        className="btn secondary"
                        onClick={() => handleRefund(record.payment_id)}
                        disabled={refundProcessing === record.payment_id}
                      >
                        {refundProcessing === record.payment_id
                          ? "Processing..."
                          : record.status === "refund_pending"
                          ? "Complete Refund"
                          : "Refund"}
                      </button>
                    ) : record.status === "refunded" ? (
                      <span style={{ color: "#10b981", fontWeight: 600 }}>Refunded</span>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

