import { useCallback, useEffect, useRef, useState } from "react"
import { apiGet, apiPost } from "../store/api"
import MultiplierBadge from "../components/MultiplierBadge"
import { useEmulatorStore, EmulatorSession } from "../store/emulator"

const SIM_DOMAIN = "sim.bikeshare.local"
const SIM_USER_PASSWORD = "ride123"
type Session = EmulatorSession
const SG_BOUNDS = {
  minLat: 1.23,
  maxLat: 1.47,
  minLon: 103.60,
  maxLon: 104.05,
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const jitterPosition = (lat: number, lon: number) => {
  const deltaLat = (Math.random() - 0.5) * 0.0008
  const deltaLon = (Math.random() - 0.5) * 0.0012
  return {
    lat: clamp(lat + deltaLat, SG_BOUNDS.minLat, SG_BOUNDS.maxLat),
    lon: clamp(lon + deltaLon, SG_BOUNDS.minLon, SG_BOUNDS.maxLon),
  }
}

const defaultPosition = { lat: 1.305, lon: 103.805 }

function createKey(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2)}`
}

const formatCurrency = (cents: number) => `SGD ${(cents / 100).toFixed(2)}`

async function loginSimUser(email: string): Promise<string | null> {
  try {
    const res = await fetch("http://localhost:8000/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: SIM_USER_PASSWORD }),
    })
    if (!res.ok) {
      return null
    }
    const data = await res.json()
    return typeof data?.access_token === "string" ? data.access_token : null
  } catch {
    return null
  }
}

export default function UserEmulator() {
  const [bikes, setBikes] = useState<any[]>([])
  const sessions = useEmulatorStore((s) => s.sessions)
  const setSessions = useEmulatorStore((s) => s.setSessions)
  const nextIndex = useEmulatorStore((s) => s.nextIndex)
  const [error, setError] = useState<string | null>(null)
  const sessionsRef = useRef<Session[]>([])
  const loadedRef = useRef(false)
  const timersRef = useRef<Record<string, number>>({})
  const paymentTimersRef = useRef<Record<string, number>>({})

  useEffect(() => {
    sessionsRef.current = sessions
  }, [sessions])

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach((timer) => window.clearInterval(timer))
      timersRef.current = {}
      Object.values(paymentTimersRef.current).forEach((timer) => window.clearInterval(timer))
      paymentTimersRef.current = {}
    }
  }, [])

  useEffect(() => {
    loadedRef.current = true
  }, [])

  const updateSession = useCallback((sessionId: string, updates: Partial<Session>) => {
    setSessions((prev) =>
      prev.map((session) => (session.id === sessionId ? { ...session, ...updates } : session))
    )
  }, [])

  const stopPaymentPolling = useCallback((sessionId: string) => {
    const timer = paymentTimersRef.current[sessionId]
    if (timer) {
      window.clearInterval(timer)
      delete paymentTimersRef.current[sessionId]
    }
  }, [])

  const startPaymentPolling = useCallback((sessionId: string, paymentId: number) => {
    const poll = async () => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.payment) {
        stopPaymentPolling(sessionId)
        return
      }
      let token = session.userToken
      if (!token) {
        token = await loginSimUser(session.simEmail)
        if (token) {
          updateSession(sessionId, { userToken: token })
        }
      }
      if (!token) {
        stopPaymentPolling(sessionId)
        updateSession(sessionId, {
          status: "refund request failed (login)",
          payment: { ...session.payment, message: "could not authenticate for refund" },
        })
        return
      }
      try {
        const res = await fetch(`http://localhost:8000/api/v1/payments/${paymentId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        })
        if (!res.ok) {
          if (res.status === 404) {
            stopPaymentPolling(sessionId)
            updateSession(sessionId, {
              payment: { ...session.payment, message: "payment not found" },
            })
          } else if (res.status === 401 || res.status === 403) {
            updateSession(sessionId, { userToken: null })
          }
          return
        }
        const data = await res.json()
        const statusValue = typeof data?.status === "string" ? data.status : session.payment.status
        if (statusValue !== session.payment.status) {
          let message = session.payment.message
          let statusText = session.status
          if (statusValue === "refund_pending") {
            message = "awaiting admin approval"
            statusText = "refund requested"
          } else if (statusValue === "refunded") {
            message = "refund completed"
            statusText = "refund completed"
          }
          updateSession(sessionId, {
            status: statusText,
            payment: { ...session.payment, status: statusValue, message },
          })
        }
        if (statusValue === "refunded") {
          stopPaymentPolling(sessionId)
        }
      } catch {
        // ignore transient errors and retry on next poll
      }
    }
    stopPaymentPolling(sessionId)
    void poll()
    paymentTimersRef.current[sessionId] = window.setInterval(poll, 5000)
  }, [stopPaymentPolling, updateSession])

  useEffect(() => {
    sessions.forEach((session) => {
      const timerActive = Boolean(paymentTimersRef.current[session.id])
      const payment = session.payment
      if (payment && payment.status === "refund_pending" && payment.paymentId) {
        if (!timerActive) {
          startPaymentPolling(session.id, payment.paymentId)
        }
      } else if (timerActive && (!payment || payment.status !== "refund_pending")) {
        stopPaymentPolling(session.id)
      }
    })
  }, [sessions, startPaymentPolling, stopPaymentPolling])

  const stopTelemetry = useCallback((sessionId: string) => {
    const timer = timersRef.current[sessionId]
    if (timer) {
      window.clearInterval(timer)
      delete timersRef.current[sessionId]
    }
    setSessions((prev) =>
      prev.map((session) => (session.id === sessionId ? { ...session, telemetryTimer: null } : session))
    )
  }, [])

  const refreshBikes = useCallback(async () => {
    const { ok, data } = await apiGet("/api/v1/bikes")
    if (!ok || !Array.isArray(data)) {
      setError("Failed to load bikes. Please ensure the backend is running and you are authenticated.")
      setBikes([])
      return
    }
    setError(null)
    const available = data.filter((b: any) => b.status === "ok" && b.lock_state === "locked")
    setBikes(available)
    setSessions((prev) =>
      prev.map((session) => {
        if (session.rideId) return session
        const exists = available.some((b: any) => b.qr_public_id === session.qr)
        const nextQr = exists ? session.qr : available[0]?.qr_public_id ?? ""
        return { ...session, qr: nextQr }
      })
    )
  }, [])

  const startTelemetry = useCallback(
    (sessionId: string, rideId: number, bikeInfo: { qr_public_id: string; battery_pct?: number; lat?: number; lon?: number }) => {
      let currentLat = clamp(bikeInfo.lat ?? defaultPosition.lat, SG_BOUNDS.minLat, SG_BOUNDS.maxLat)
      let currentLon = clamp(bikeInfo.lon ?? defaultPosition.lon, SG_BOUNDS.minLon, SG_BOUNDS.maxLon)

      const postPoint = async () => {
        const session = sessionsRef.current.find((s) => s.id === sessionId)
        if (!session || session.rideId !== rideId) {
          stopTelemetry(sessionId)
          return
        }
        const next = jitterPosition(currentLat, currentLon)
        currentLat = next.lat
        currentLon = next.lon
        const speed = 3 + Math.random() * 1.5
        updateSession(sessionId, {
          status: `riding... (${currentLat.toFixed(5)}, ${currentLon.toFixed(5)})`,
          activeBike: {
            qr_public_id: bikeInfo.qr_public_id,
            battery_pct: bikeInfo.battery_pct,
            lat: currentLat,
            lon: currentLon,
          },
        })
       const { ok, status } = await apiPost(`/api/v1/rides/${rideId}/telemetry`, {
         lat: currentLat,
         lon: currentLon,
         speed_mps: speed,
         ts: Date.now() / 1000,
       })
       if (!ok) {
          if (status === 409) {
            stopTelemetry(sessionId)
            return
          }
          updateSession(sessionId, { status: `telemetry failed (${status})` })
          stopTelemetry(sessionId)
        }
      }

      postPoint()
      const timer = window.setInterval(postPoint, 2000)
      timersRef.current[sessionId] = timer
      setSessions((prev) =>
        prev.map((session) => (session.id === sessionId ? { ...session, telemetryTimer: timer } : session))
      )
    },
    [stopTelemetry, updateSession]
  )

  const addSession = useCallback(() => {
    const index = nextIndex()
    const simEmail = `sim-user-${index}@${SIM_DOMAIN}`
    const defaultQr = bikes[0]?.qr_public_id ?? ""
    const newSession: Session = {
      id: `session-${Date.now()}-${index}`,
      label: `Sim User ${index}`,
      simEmail,
      qr: defaultQr,
      rideId: null,
      status: "idle",
      userToken: null,
      idempUnlock: createKey("idem-u"),
      idempLock: createKey("idem-l"),
      telemetryTimer: null,
      payment: undefined,
    }
    setSessions((prev) => [...prev, newSession])
  }, [bikes, nextIndex, setSessions])

  useEffect(() => {
    refreshBikes()
  }, [refreshBikes])

  useEffect(() => {
    if (sessions.length === 0 && bikes.length > 0 && loadedRef.current) {
      addSession()
    }
  }, [sessions.length, bikes.length, addSession])

  useEffect(() => {
    if (!loadedRef.current) return
    sessions.forEach((session) => {
      if (session.rideId && !session.telemetryTimer) {
        const bikeInfo = session.activeBike ?? {
          qr_public_id: session.qr,
          battery_pct: session.activeBike?.battery_pct,
          lat: session.activeBike?.lat ?? defaultPosition.lat,
          lon: session.activeBike?.lon ?? defaultPosition.lon,
        }
        startTelemetry(session.id, session.rideId, bikeInfo)
      }
    })
  }, [sessions, startTelemetry])

  const removeSession = useCallback(
    (sessionId: string) => {
      stopTelemetry(sessionId)
      stopPaymentPolling(sessionId)
      setSessions((prev) => prev.filter((session) => session.id !== sessionId))
    },
    [stopTelemetry, stopPaymentPolling, setSessions]
  )

  const handleSelect = useCallback(
    (sessionId: string, value: string) => {
      updateSession(sessionId, { qr: value })
    },
    [updateSession]
  )

  const unlockSession = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session) return
      if (!session.qr) {
        updateSession(sessionId, { status: "No bikes available to unlock." })
        return
      }
      const unlockKey = createKey("idem-u")
      updateSession(sessionId, { status: "unlocking...", idempUnlock: unlockKey, payment: undefined })
      try {
        const { ok, status, data } = await apiPost(
          "/api/v1/unlock",
          { qr_public_id: session.qr, simulated_user_email: session.simEmail },
          { "Idempotency-Key": unlockKey }
        )
        if (!ok) {
          updateSession(sessionId, { status: `unlock failed (${status})` })
          await refreshBikes()
          return
        }
        const rideId = data?.ride?.id ?? data?.ride_id
        if (!rideId) {
          updateSession(sessionId, { status: "unlock response missing ride id" })
          await refreshBikes()
          return
        }
        const bike = data?.bike ?? bikes.find((b: any) => b.qr_public_id === session.qr)
        const bikeInfo = {
          qr_public_id: bike?.qr_public_id ?? session.qr,
          battery_pct: bike?.battery_pct,
          lat: bike?.lat ?? defaultPosition.lat,
          lon: bike?.lon ?? defaultPosition.lon,
        }
        updateSession(sessionId, {
          rideId,
          status: "riding...",
          activeBike: bikeInfo,
          idempLock: createKey("idem-l"),
          payment: undefined,
        })
        startTelemetry(sessionId, rideId, bikeInfo)
        await refreshBikes()
      } catch (err) {
        updateSession(sessionId, { status: "unlock failed (network error)" })
      }
    },
    [bikes, refreshBikes, startTelemetry, updateSession]
  )

  const lockSession = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.rideId) return
      stopTelemetry(sessionId)
      updateSession(sessionId, { status: "locking..." })
      try {
        const lat = session.activeBike?.lat ?? defaultPosition.lat
        const lon = session.activeBike?.lon ?? defaultPosition.lon
        const lockKey = session.idempLock ?? createKey("idem-l")
        const { ok, data, status } = await apiPost(
          "/api/v1/lock",
          { ride_id: session.rideId, lat, lon },
          { "Idempotency-Key": lockKey }
        )
        if (ok && data?.ok) {
          const rideId = data?.ride?.id ?? session.rideId
          const fareCents = data?.ride?.metrics?.fare_cents ?? data?.fare_cents ?? 0
          updateSession(sessionId, {
            status: `locked - fare ${fareCents} cents`,
            rideId: null,
            activeBike: undefined,
            telemetryTimer: null,
            idempUnlock: createKey("idem-u"),
            idempLock: createKey("idem-l"),
            payment: rideId
              ? {
                  rideId,
                  fareCents,
                  status: "pending",
                }
              : undefined,
          })
          await refreshBikes()
        } else {
          const detail = !ok ? ` (${status})` : data?.error ? `: ${data.error}` : ""
          updateSession(sessionId, { status: `lock failed${detail}` })
          if (session.rideId) {
            const resumeInfo = session.activeBike ?? {
              qr_public_id: session.qr,
              lat,
              lon,
            }
            startTelemetry(sessionId, session.rideId, resumeInfo)
          }
        }
      } catch {
        updateSession(sessionId, { status: "lock failed (network error)" })
        if (session.rideId) {
          const resumeInfo = session.activeBike ?? {
            qr_public_id: session.qr,
            lat: session.activeBike?.lat ?? defaultPosition.lat,
            lon: session.activeBike?.lon ?? defaultPosition.lon,
          }
          startTelemetry(sessionId, session.rideId, resumeInfo)
        }
      }
    },
    [refreshBikes, startTelemetry, stopTelemetry, updateSession]
  )

  const markPaid = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (
        !session ||
        !session.payment ||
        ["captured", "refund_pending", "refunded"].includes(session.payment.status)
      ) {
        return
      }
      const paymentInfo = session.payment
      updateSession(sessionId, {
        status: "authorizing payment...",
        payment: { ...paymentInfo, status: "pending", message: undefined },
      })
      try {
        const authKey = createKey("idem-pay-auth")
        const authRes = await apiPost(
          "/api/v1/payments/authorize",
          { ride_id: paymentInfo.rideId, amount_cents: paymentInfo.fareCents },
          { "Idempotency-Key": authKey }
        )
        if (!authRes.ok || !authRes.data?.id) {
          updateSession(sessionId, {
            status: `payment authorize failed (${authRes.status})`,
            payment: { ...paymentInfo, status: "failed", message: `authorize ${authRes.status}` },
          })
          return
        }
        const paymentId = authRes.data.id
        updateSession(sessionId, {
          status: "capturing payment...",
          payment: { ...paymentInfo, paymentId, status: "authorized", message: undefined },
        })
        const captureRes = await apiPost(
          "/api/v1/payments/capture",
          { payment_id: paymentId },
          { "Idempotency-Key": createKey("idem-pay-cap") }
        )
        if (!captureRes.ok) {
          updateSession(sessionId, {
            status: `payment capture failed (${captureRes.status})`,
            payment: { ...paymentInfo, paymentId, status: "failed", message: `capture ${captureRes.status}` },
          })
          return
        }
        updateSession(sessionId, {
          status: `payment captured - ${formatCurrency(paymentInfo.fareCents)}`,
          payment: { ...paymentInfo, paymentId, status: "captured", message: undefined },
        })
      } catch (err) {
        updateSession(sessionId, {
          status: "payment failed (network error)",
          payment: { ...paymentInfo, status: "failed", message: "network error" },
        })
      }
    },
    [updateSession]
  )

  const requestRefund = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.payment || session.payment.status !== "captured" || !session.payment.paymentId) {
        return
      }
      const paymentInfo = session.payment
      updateSession(sessionId, {
        status: "requesting refund...",
        payment: { ...paymentInfo, message: "submitting refund request" },
      })
      try {
        let token = session.userToken
        if (!token) {
          token = await loginSimUser(session.simEmail)
          if (token) {
            updateSession(sessionId, { userToken: token })
          }
        }
        if (!token) {
          updateSession(sessionId, {
            status: "refund request failed (login)",
            payment: { ...paymentInfo, message: "could not authenticate for refund" },
          })
          return
        }
        const res = await fetch(`http://localhost:8000/api/v1/payments/${paymentInfo.paymentId}/refund-request`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            "Idempotency-Key": createKey("idem-refund-req"),
          },
          body: JSON.stringify({ reason: "Requested from emulator" }),
        })
        if (!res.ok) {
          updateSession(sessionId, {
            status: `refund request failed (${res.status})`,
            payment: { ...paymentInfo, message: `refund request ${res.status}` },
          })
          return
        }
        updateSession(sessionId, {
          status: "refund requested",
          payment: { ...paymentInfo, status: "refund_pending", message: "awaiting admin approval" },
        })
        startPaymentPolling(sessionId, paymentInfo.paymentId)
      } catch {
        updateSession(sessionId, {
          status: "refund request failed (network error)",
          payment: { ...paymentInfo, message: "refund request network error" },
        })
      }
    },
    [startPaymentPolling, updateSession]
  )

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <h3>User Emulator</h3>
          <MultiplierBadge />
        </div>
        <button className="btn" onClick={addSession}>
          Add Emulator
        </button>
      </div>
      {error && <div style={{ color: "#f87171", marginBottom: 12 }}>{error}</div>}
      {sessions.length === 0 && <div>No emulator sessions yet. Add one to begin.</div>}
      {sessions.map((session) => {
        const canRemove = session.rideId === null
        return (
          <div key={session.id} className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>{session.label}</strong>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: 12, color: "#9ca3af" }}>{session.simEmail}</span>
                <button className="btn" onClick={() => removeSession(session.id)} disabled={!canRemove}>
                  Remove
                </button>
              </div>
            </div>
            {session.rideId ? (
              <div style={{ marginTop: 8 }}>
                <div>Active bike: {session.activeBike?.qr_public_id ?? session.qr}</div>
                {session.activeBike && (
                  <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>
                    ({session.activeBike.lat.toFixed(5)}, {session.activeBike.lon.toFixed(5)})
                  </div>
                )}
              </div>
            ) : (
              <div className="row" style={{ marginTop: 8 }}>
                <select
                  className="input"
                  value={session.qr}
                  onChange={(e) => handleSelect(session.id, e.target.value)}
                >
                  {bikes.length === 0 ? (
                    <option value="">No bikes available</option>
                  ) : (
                    bikes.map((b: any) => (
                      <option key={b.id} value={b.qr_public_id}>
                        {b.qr_public_id} ({b.battery_pct}%)
                      </option>
                    ))
                  )}
                </select>
                <button
                  className="btn"
                  onClick={() => unlockSession(session.id)}
                  disabled={!session.qr || session.rideId !== null}
                >
                  Scan & Unlock
                </button>
              </div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={() => lockSession(session.id)} disabled={session.rideId === null}>
                Lock
              </button>
            </div>
            <p style={{ marginTop: 8 }}>Status: {session.status}</p>
            {session.payment && (
              <div style={{ marginTop: 8, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 14 }}>
                  Fare: {formatCurrency(session.payment.fareCents)} ({session.payment.status}
                  {session.payment.message ? ` - ${session.payment.message}` : ''})
                </span>
                <button
                  className="btn"
                  onClick={() => markPaid(session.id)}
                  disabled={['captured', 'refund_pending', 'refunded'].includes(session.payment.status)}
                >
                  Mark Paid
                </button>
                {session.payment.status === 'captured' && (
                  <button className="btn secondary" onClick={() => requestRefund(session.id)}>
                    Request Refund
                  </button>
                )}
                {session.payment.status === 'refund_pending' && (
                  <span style={{ color: '#f59e0b', fontSize: 13 }}>Refund requested</span>
                )}
                {session.payment.status === 'refunded' && (
                  <span style={{ color: '#10b981', fontSize: 13 }}>Refunded</span>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}






