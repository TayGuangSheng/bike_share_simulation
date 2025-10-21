import { useCallback, useEffect, useRef, useState } from "react"
import { apiGet, apiPost } from "../store/api"
import MultiplierBadge from "../components/MultiplierBadge"
import {
  useEmulatorStore,
  EmulatorSession,
  EmulatorPayment,
  EmulatorProgressEntry,
  EmulatorProgressActor,
} from "../store/emulator"

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

const PROGRESS_ACTOR_ORDER: EmulatorProgressActor[] = ["user", "backend", "pricing", "battery", "weather"]

const PROGRESS_ACTOR_DETAILS: Record<
  EmulatorProgressActor,
  { label: string; accent: string }
> = {
  user: { label: "Simulated User", accent: "#38bdf8" },
  backend: { label: "Backend API", accent: "#f97316" },
  pricing: { label: "Pricing Service", accent: "#a855f7" },
  battery: { label: "Battery Service", accent: "#22c55e" },
  weather: { label: "Weather Service", accent: "#60a5fa" },
}

const describeHttp = (methodOrStatus: string, path: string, detail: string) =>
  `${methodOrStatus.toUpperCase()} ${path} â€“ ${detail}`

function equalBikeLists(prev: any[], next: any[]): boolean {
  if (prev.length !== next.length) return false
  for (let i = 0; i < prev.length; i += 1) {
    const a = prev[i]
    const b = next[i]
    if (
      a.id !== b.id ||
      a.lock_state !== b.lock_state ||
      a.status !== b.status ||
      a.qr_public_id !== b.qr_public_id ||
      a.lat !== b.lat ||
      a.lon !== b.lon ||
      a.battery_pct !== b.battery_pct
    ) {
      return false
    }
  }
  return true
}

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

  const updateSession = useCallback(
    (sessionId: string, updates: Partial<Session>) => {
      setSessions((prev) =>
        prev.map((session) => (session.id === sessionId ? { ...session, ...updates } : session))
      )
    },
    [setSessions]
  )

  const pushProgress = useCallback(
    (
      sessionId: string,
      message: string,
      actor: EmulatorProgressActor,
      target: EmulatorProgressActor | "system",
      kind: EmulatorProgressEntry["kind"] = "info"
    ) => {
      const entry: EmulatorProgressEntry = {
        id: createKey("progress"),
        message,
        actor,
        target,
        kind,
        ts: Date.now(),
      }
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== sessionId) return session
          const nextLog = [...(session.progressLog ?? []), entry]
          return { ...session, progressLog: nextLog }
        })
      )
    },
    [setSessions]
  )

  const fetchQuote = useCallback(
    async (sessionId: string, bike?: any) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      const targetBike = bike ?? bikes.find((b: any) => b.qr_public_id === session?.qr)
      if (!session || !targetBike) {
        updateSession(sessionId, { quote: undefined })
        return
      }
      const params = new URLSearchParams({
        bike_id: String(targetBike.id),
        lat: String(targetBike.lat ?? defaultPosition.lat),
        lon: String(targetBike.lon ?? defaultPosition.lon),
      })
      pushProgress(
        sessionId,
        describeHttp("OPTIONS", "/api/v1/price/quote", "CORS preflight before requesting fare quote"),
        "user",
        "pricing",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp("GET", `/api/v1/price/quote?bike_id=${targetBike.id}`, "request fare quote for selected bike"),
        "user",
        "pricing",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp("GET", "/api/v1/weather/current", "pricing service fetching weather context"),
        "pricing",
        "weather",
        "info"
      )
      try {
        const res = await apiGet(`/api/v1/price/quote?${params.toString()}`, "pricing")
        if (res.ok && res.data) {
          const weather = res.data.weather ?? "unknown"
          pushProgress(
            sessionId,
            describeHttp("200 GET", "/api/v1/weather/current", `conditions supplied (${weather})`),
            "weather",
            "pricing",
            "success"
          )
          pushProgress(
            sessionId,
            describeHttp(
              "200 GET",
              `/api/v1/price/quote?bike_id=${targetBike.id}`,
              `quote ready: base SGD ${((res.data.base_cents ?? 0) / 100).toFixed(2)}, multiplier x${(res.data.surge_multiplier ?? 1).toFixed(2)}`
            ),
            "pricing",
            "user",
            "success"
          )
          updateSession(sessionId, {
            quote: {
              baseCents: res.data.base_cents ?? 0,
              perMinCents: res.data.per_min_cents ?? 0,
              perKmCents: res.data.per_km_cents ?? 0,
              surgeMultiplier: res.data.surge_multiplier ?? 1,
              weather: res.data.weather ?? "clear",
              demandFactor: res.data.demand_factor ?? 1,
            },
          })
        } else {
          updateSession(sessionId, { quote: undefined })
          pushProgress(
            sessionId,
            describeHttp(`${res.status} GET`, `/api/v1/price/quote?bike_id=${targetBike.id}`, "quote failed"),
            "pricing",
            "user",
            "error"
          )
        }
      } catch {
        updateSession(sessionId, { quote: undefined })
        pushProgress(
          sessionId,
          describeHttp("0 GET", `/api/v1/price/quote?bike_id=${targetBike.id}`, "network error while requesting quote"),
          "pricing",
          "user",
          "error"
        )
      }
    },
    [bikes, updateSession]
  )

  const stopPaymentPolling = useCallback((sessionId: string) => {
    const timer = paymentTimersRef.current[sessionId]
    if (timer) {
      window.clearInterval(timer)
      delete paymentTimersRef.current[sessionId]
    }
  }, [])

  const startPaymentPolling = useCallback(
    (sessionId: string, paymentId: number) => {
      const poll = async () => {
        const session = sessionsRef.current.find((s) => s.id === sessionId)
        if (!session || !session.payment) {
          stopPaymentPolling(sessionId)
          return
        }

        let token = session.userToken
        if (!token) {
          pushProgress(
            sessionId,
            describeHttp("OPTIONS", "/api/v1/auth/login", "CORS preflight before simulated user login"),
            "user",
            "backend",
            "info"
          )
          pushProgress(
            sessionId,
            describeHttp("POST", "/api/v1/auth/login", `authenticate simulated user ${session.simEmail}`),
            "user",
            "backend",
            "info"
          )
          const newToken = await loginSimUser(session.simEmail)
          if (newToken) {
            pushProgress(
              sessionId,
              describeHttp("200 POST", "/api/v1/auth/login", "token issued for simulated user"),
              "backend",
              "user",
              "success"
            )
            updateSession(sessionId, { userToken: newToken })
            token = newToken
          } else {
            pushProgress(
              sessionId,
              describeHttp("401 POST", "/api/v1/auth/login", "authentication failed for simulated user"),
              "backend",
              "user",
              "error"
            )
          }
        }

        if (!token) {
          stopPaymentPolling(sessionId)
          updateSession(sessionId, {
            status: "refund request failed (login)",
            payment: { ...session.payment, message: "could not authenticate for refund" },
          })
          pushProgress(
            sessionId,
            describeHttp("401 GET", `/api/v1/payments/${paymentId}`, "refund polling stopped – login required"),
            "backend",
            "user",
            "error"
          )
          return
        }

        try {
          pushProgress(
            sessionId,
            describeHttp("OPTIONS", `/api/v1/payments/${paymentId}`, "CORS preflight before checking payment status"),
            "user",
            "backend",
            "info"
          )
          pushProgress(
            sessionId,
            describeHttp("GET", `/api/v1/payments/${paymentId}`, "poll payment status"),
            "user",
            "backend",
            "info"
          )
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
              pushProgress(
                sessionId,
                describeHttp("404", `/api/v1/payments/${paymentId}`, "payment not found during refund poll"),
                "backend",
                "user",
                "error"
              )
            } else if (res.status === 401 || res.status === 403) {
              updateSession(sessionId, { userToken: null })
              pushProgress(
                sessionId,
                describeHttp(`${res.status} GET`, `/api/v1/payments/${paymentId}`, "auth token expired"),
                "backend",
                "user",
                "error"
              )
            }
            return
          }

          const data = await res.json()
          pushProgress(
            sessionId,
            describeHttp(`${res.status} GET`, `/api/v1/payments/${paymentId}`, "payment record fetched"),
            "backend",
            "user",
            "success"
          )
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
            pushProgress(
              sessionId,
              describeHttp(
                String(res.status),
                `/api/v1/payments/${paymentId}`,
                `refund status is now ${statusValue}`
              ),
              "backend",
              "user",
              "success"
            )
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
    },
    [pushProgress, stopPaymentPolling, updateSession]
  )

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
  }, [setSessions])

  const refreshBikes = useCallback(async () => {
    sessionsRef.current.forEach((session) => {
      pushProgress(
        session.id,
        describeHttp("OPTIONS", "/api/v1/bikes", "CORS preflight before requesting bike catalogue"),
        "user",
        "backend",
        "info"
      )
      pushProgress(
        session.id,
        describeHttp("GET", "/api/v1/bikes", "request list of available bikes"),
        "user",
        "backend",
        "info"
      )
    })
    const { ok, data, status } = await apiGet("/api/v1/bikes")
    if (!ok || !Array.isArray(data)) {
      setError("Failed to load bikes. Please ensure the backend is running and you are authenticated.")
      setBikes([])
      sessionsRef.current.forEach((session) => {
        pushProgress(
          session.id,
          describeHttp(`${status || 0} GET`, "/api/v1/bikes", "failed to load bike list"),
          "backend",
          "user",
          "error"
        )
      })
      return
    }
    setError(null)
    const available = data.filter((b: any) => b.status === "ok" && b.lock_state === "locked")
    let bikesChanged = false
    setBikes((prev) => {
      const equal = equalBikeLists(prev, available)
      if (!equal) {
        bikesChanged = true
        return available
      }
      return prev
    })
    if (bikesChanged) {
      sessionsRef.current.forEach((session) => {
        pushProgress(
          session.id,
          describeHttp(`${status || 200} GET`, "/api/v1/bikes", `${available.length} bikes available`),
          "backend",
          "user",
          "success"
        )
      })
    }
    setSessions((prev) => {
      let changed = false
      const nextSessions = prev.map((session) => {
        if (session.rideId) return session
        const exists = available.some((b: any) => b.qr_public_id === session.qr)
        const nextQr = exists ? session.qr : available[0]?.qr_public_id ?? ""
        const targetBike = available.find((b: any) => b.qr_public_id === nextQr)
        const shouldFetchQuote = !session.quote || nextQr !== session.qr
        if (shouldFetchQuote && targetBike) {
          void fetchQuote(session.id, targetBike)
        }
        if (nextQr !== session.qr) {
          changed = true
          return {
            ...session,
            qr: nextQr,
            quote: shouldFetchQuote ? undefined : session.quote,
          }
        }
        return session
      })
      return changed ? nextSessions : prev
    })
  }, [fetchQuote, pushProgress, setSessions])

  const startTelemetry = useCallback(
    (
      sessionId: string,
      rideId: number,
      bikeInfo: { id?: number; qr_public_id: string; battery_pct?: number; lat?: number; lon?: number }
    ) => {
      let currentLat = clamp(bikeInfo.lat ?? defaultPosition.lat, SG_BOUNDS.minLat, SG_BOUNDS.maxLat)
      let currentLon = clamp(bikeInfo.lon ?? defaultPosition.lon, SG_BOUNDS.minLon, SG_BOUNDS.maxLon)
      let loggedTelemetryRequest = false
      let loggedTelemetryResponse = false
      let loggedFareRequest = false
      let fareStaticCounter = 0
      let loggedBatteryRequest = false
      let batteryStaticCounter = 0

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
        const timestamp = Date.now() / 1000

        const baseUpdate: Partial<Session> = {
          status: `riding... (${currentLat.toFixed(5)}, ${currentLon.toFixed(5)})`,
          activeBike: {
            id: bikeInfo.id ?? session.activeBike?.id,
            qr_public_id: bikeInfo.qr_public_id,
            battery_pct: session.activeBike?.battery_pct ?? bikeInfo.battery_pct,
            lat: currentLat,
            lon: currentLon,
          },
        }

        updateSession(sessionId, baseUpdate)

        if (!loggedTelemetryRequest) {
          pushProgress(
            sessionId,
            describeHttp(
              "POST",
              `/api/v1/rides/${rideId}/telemetry`,
              `submit telemetry sample (lat=${currentLat.toFixed(5)}, lon=${currentLon.toFixed(5)})`
            ),
            "user",
            "backend",
            "info"
          )
          loggedTelemetryRequest = true
        }

        const telemetryRes = await apiPost(
          `/api/v1/rides/${rideId}/telemetry`,
          {
            lat: currentLat,
            lon: currentLon,
            speed_mps: speed,
            ts: timestamp,
          }
        )

        if (!telemetryRes.ok) {
          if (telemetryRes.status === 409) {
            stopTelemetry(sessionId)
            return
          }
          updateSession(sessionId, { status: `telemetry failed (${telemetryRes.status})` })
          pushProgress(
            sessionId,
            describeHttp(
              `${telemetryRes.status} POST`,
              `/api/v1/rides/${rideId}/telemetry`,
              "telemetry request rejected"
            ),
            "backend",
            "user",
            "error"
          )
          stopTelemetry(sessionId)
          return
        }

        if (!loggedTelemetryResponse) {
          pushProgress(
            sessionId,
            describeHttp(
              `${telemetryRes.status ?? 200} POST`,
              `/api/v1/rides/${rideId}/telemetry`,
              `telemetry accepted for ride ${rideId}`
            ),
            "backend",
            "user",
            "success"
          )
          loggedTelemetryResponse = true
        }

        const updates: Partial<Session> = {}
        const metrics = telemetryRes.data ?? {}
        try {
          if (!loggedFareRequest) {
            pushProgress(
              sessionId,
              describeHttp(
                "GET",
                `/api/v1/price/ride/${rideId}/current?meters=${metrics.meters ?? 0}&seconds=${
                  metrics.seconds ?? 0
                }`,
                "poll live fare estimate"
              ),
              "user",
              "pricing",
              "info"
            )
            pushProgress(
              sessionId,
              describeHttp("GET", "/api/v1/weather/current", "pricing service fetching weather for fare estimate"),
              "pricing",
              "weather",
              "info"
            )
            loggedFareRequest = true
          }
          const params = new URLSearchParams({
            meters: String(metrics.meters ?? 0),
            seconds: String(metrics.seconds ?? 0),
            lat: String(currentLat),
            lon: String(currentLon),
          })
          const fareRes = await apiGet(`/api/v1/price/ride/${rideId}/current?${params.toString()}`, "pricing")
          if (fareRes.ok && fareRes.data) {
            updates.runningFare = {
              fareCents: fareRes.data.fare_cents ?? 0,
              multiplier: fareRes.data.multiplier ?? 1,
              seconds: fareRes.data.seconds ?? metrics.seconds ?? 0,
              meters: fareRes.data.meters ?? metrics.meters ?? 0,
            }
            pushProgress(
              sessionId,
              describeHttp("200 GET", "/api/v1/weather/current", "conditions supplied for fare calculation"),
              "weather",
              "pricing",
              "success"
            )
            const newFareCents = updates.runningFare.fareCents
            const prevFare = session.runningFare
            const fareChanged =
              !prevFare ||
              prevFare.fareCents !== newFareCents ||
              prevFare.multiplier !== updates.runningFare.multiplier
            if (fareChanged) {
              fareStaticCounter = 0
              pushProgress(
                sessionId,
                describeHttp(
                  "200 GET",
                  `/api/v1/price/ride/${rideId}/current`,
                  `live fare updated (SGD ${(newFareCents / 100).toFixed(2)})`
                ),
                "pricing",
                "user",
                "success"
              )
            } else {
              fareStaticCounter += 1
              if (fareStaticCounter >= 3) {
                pushProgress(
                  sessionId,
                  describeHttp(
                    "200 GET",
                    `/api/v1/price/ride/${rideId}/current`,
                    `fare unchanged (still SGD ${((prevFare?.fareCents ?? newFareCents) / 100).toFixed(2)})`
                  ),
                  "pricing",
                  "user",
                  "info"
                )
                fareStaticCounter = 0
              }
              // no change, skip updating fare in session
              delete updates.runningFare
            }
          }
        } catch {
          // ignore pricing errors for now
        }

        const bikeId = baseUpdate.activeBike?.id ?? bikeInfo.id ?? session.activeBike?.id
        if (bikeId) {
          try {
            if (!loggedBatteryRequest) {
              pushProgress(
                sessionId,
                describeHttp(
                  "POST",
                  `/api/v1/battery/bikes/${bikeId}/telemetry`,
                  "send battery telemetry sample"
                ),
                "user",
                "battery",
                "info"
              )
              loggedBatteryRequest = true
            }
            const batteryRes = await apiPost(
              `/api/v1/battery/bikes/${bikeId}/telemetry`,
              {
                ride_id: rideId,
                lat: currentLat,
                lon: currentLon,
                speed_mps: speed,
                ts: timestamp,
              },
              {},
              "battery"
            )
            if (batteryRes.ok && batteryRes.data?.battery_pct != null) {
              const rawPct = Number.parseFloat(String(batteryRes.data.battery_pct))
              const pctValue = Number.isFinite(rawPct) ? Math.max(0, Math.min(100, rawPct)) : 0
              const prevBattery = session.battery?.pct
              const batteryChanged = prevBattery == null || Math.abs(prevBattery - pctValue) > 0.05
              if (batteryChanged) {
                updates.battery = { pct: pctValue, lastUpdated: Date.now() }
              }
              updates.activeBike = {
                ...(baseUpdate.activeBike ?? {
                  id: bikeId,
                  qr_public_id: bikeInfo.qr_public_id,
                  lat: currentLat,
                  lon: currentLon,
                }),
                id: bikeId,
                battery_pct: pctValue,
                lat: currentLat,
                lon: currentLon,
              }
              if (batteryChanged) {
                batteryStaticCounter = 0
                if (bikeId) {
                  setBikes((prev) =>
                    prev.map((bike: any) =>
                      bike.id === bikeId ? { ...bike, battery_pct: Number(pctValue.toFixed(1)) } : bike
                    )
                  )
                }
                const pctText = Math.max(0, Math.min(100, pctValue)).toFixed(1)
                pushProgress(
                  sessionId,
                  describeHttp(
                    "200 POST",
                    `/api/v1/battery/bikes/${bikeId}/telemetry`,
                    `battery updated to ${pctText}%`
                  ),
                  "battery",
                  "user",
                  "success"
                )
              } else {
                batteryStaticCounter += 1
                if (batteryStaticCounter >= 3) {
                  const pctText = Math.max(0, Math.min(100, prevBattery ?? pctValue)).toFixed(1)
                  pushProgress(
                    sessionId,
                    describeHttp(
                      "200 POST",
                      `/api/v1/battery/bikes/${bikeId}/telemetry`,
                      `battery unchanged (still ${pctText}%)`
                    ),
                    "battery",
                    "user",
                    "info"
                  )
                  batteryStaticCounter = 0
                }
              }
            }
          } catch {
            // best effort; ignore failure
          }
        }

        const latestSession = sessionsRef.current.find((s) => s.id === sessionId)
        if (!latestSession || latestSession.rideId !== rideId) {
          stopTelemetry(sessionId)
          return
        }

        if (Object.keys(updates).length > 0) {
          updateSession(sessionId, updates)
        }
      }

      postPoint()
      const timer = window.setInterval(postPoint, 2000)
      timersRef.current[sessionId] = timer
      pushProgress(
        sessionId,
        `User: scheduling telemetry loop every 2s for ride ${rideId} (bike ${bikeInfo.qr_public_id})`,
        "user",
        "system",
        "info"
      )
      setSessions((prev) =>
        prev.map((session) => (session.id === sessionId ? { ...session, telemetryTimer: timer } : session))
      )
    },
    [pushProgress, setBikes, setSessions, stopTelemetry, updateSession]
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
    quote: undefined,
    runningFare: undefined,
    battery: undefined,
    payment: undefined,
    progressLog: [],
    rideStartedAt: null,
    rideEndedAt: null,
    }
    setSessions((prev) => [...prev, newSession])
    const targetBike = bikes.find((b: any) => b.qr_public_id === defaultQr)
    if (targetBike) {
      void fetchQuote(newSession.id, targetBike)
    }
  }, [bikes, fetchQuote, nextIndex, setSessions])

  useEffect(() => {
    void refreshBikes()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (sessions.length === 0 && bikes.length > 0 && loadedRef.current) {
      addSession()
    }
  }, [sessions.length, bikes.length, addSession])

  useEffect(() => {
    if (!loadedRef.current) return
    sessions.forEach((session) => {
      if (session.rideId && !session.telemetryTimer) {
        const fallbackBike = bikes.find((b: any) => b.qr_public_id === session.qr)
        const bikeInfo = session.activeBike ?? {
          id: fallbackBike?.id,
          qr_public_id: session.qr,
          battery_pct: fallbackBike?.battery_pct,
          lat: fallbackBike?.lat ?? defaultPosition.lat,
          lon: fallbackBike?.lon ?? defaultPosition.lon,
        }
        startTelemetry(session.id, session.rideId, bikeInfo)
      }
    })
  }, [bikes, sessions, startTelemetry])

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
      const bike = bikes.find((b: any) => b.qr_public_id === value)
      fetchQuote(sessionId, bike)
    },
    [bikes, fetchQuote, updateSession]
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
      pushProgress(
        sessionId,
        describeHttp("OPTIONS", "/api/v1/unlock", "CORS preflight before unlocking bike"),
        "user",
        "backend",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp("POST", "/api/v1/unlock", `unlock bike ${session.qr} on behalf of ${session.simEmail}`),
        "user",
        "backend",
        "info"
      )
      updateSession(sessionId, { status: "unlocking...", idempUnlock: unlockKey, payment: undefined })
      try {
        const { ok, status, data } = await apiPost(
          "/api/v1/unlock",
          { qr_public_id: session.qr, simulated_user_email: session.simEmail },
          { "Idempotency-Key": unlockKey }
        )
        if (!ok) {
          updateSession(sessionId, { status: `unlock failed (${status})` })
          pushProgress(
            sessionId,
            describeHttp(`${status} POST`, "/api/v1/unlock", "unlock failed"),
            "backend",
            "user",
            "error"
          )
          await refreshBikes()
          return
        }
        const rideId = data?.ride?.id ?? data?.ride_id
        if (!rideId) {
          updateSession(sessionId, { status: "unlock response missing ride id" })
          pushProgress(
            sessionId,
            describeHttp(`${status || 500} POST`, "/api/v1/unlock", "unlock response missing ride id"),
            "backend",
            "user",
            "error"
          )
          await refreshBikes()
          return
        }
        const bike = data?.bike ?? bikes.find((b: any) => b.qr_public_id === session.qr)
        const initialBattery = bike?.battery_pct != null ? Number.parseFloat(String(bike.battery_pct)) : undefined
        const normalizedBattery =
          initialBattery != null && Number.isFinite(initialBattery)
            ? Math.max(0, Math.min(100, initialBattery))
            : undefined
        const bikeInfo = {
          id: bike?.id,
          qr_public_id: bike?.qr_public_id ?? session.qr,
          battery_pct: normalizedBattery,
          lat: bike?.lat ?? defaultPosition.lat,
          lon: bike?.lon ?? defaultPosition.lon,
        }
        updateSession(sessionId, {
          rideId,
          status: "riding...",
          activeBike: bikeInfo,
          idempLock: createKey("idem-l"),
          runningFare: undefined,
          battery:
            normalizedBattery != null ? { pct: normalizedBattery, lastUpdated: Date.now() } : undefined,
          payment: undefined,
          rideStartedAt: data?.ride?.started_at ?? session.rideStartedAt ?? null,
          rideEndedAt: null,
        })
        pushProgress(
          sessionId,
          describeHttp(
            String(status || 200),
            "/api/v1/unlock",
            `ride ${rideId} unlocked (bike ${bikeInfo.qr_public_id}), waiting for telemetry`
          ),
          "backend",
          "user",
          "success"
        )
        startTelemetry(sessionId, rideId, bikeInfo)
        await refreshBikes()
      } catch (err) {
        updateSession(sessionId, { status: "unlock failed (network error)" })
        pushProgress(
          sessionId,
          describeHttp("0", "/api/v1/unlock", "network error while unlocking bike"),
          "backend",
          "user",
          "error"
        )
      }
    },
    [bikes, pushProgress, refreshBikes, startTelemetry, updateSession]
  )

  const chargeRide = useCallback(
    async (
      sessionId: string,
      paymentInfo: EmulatorPayment,
      metadata?: EmulatorPayment["metadata"]
    ) => {
      const meta = metadata ?? paymentInfo.metadata
      pushProgress(
        sessionId,
        describeHttp("OPTIONS", "/api/v1/payments/charge", "CORS preflight before charging fare"),
        "user",
        "pricing",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp(
          "POST",
          "/api/v1/payments/charge",
          `charge ride ${paymentInfo.rideId} for ${formatCurrency(paymentInfo.fareCents)}`
        ),
        "user",
        "pricing",
        "info"
      )
      updateSession(sessionId, {
        status: "charging fare...",
        payment: { ...paymentInfo, status: "pending", message: "processing payment" },
      })
      try {
        const res = await apiPost(
          "/api/v1/payments/charge",
          {
            ride_id: paymentInfo.rideId,
            amount_cents: paymentInfo.fareCents,
            meters: meta?.meters,
            seconds: meta?.seconds,
            bike_id: meta?.bikeId,
            bike_qr: meta?.bikeQr,
            user_email: meta?.userEmail,
            ride_started_at: meta?.rideStartedAt,
            ride_ended_at: meta?.rideEndedAt,
          },
          { "Idempotency-Key": createKey("idem-charge") },
          "pricing"
        )
        if (!res.ok) {
          const statusLabel = res.status === 0 ? "network error" : String(res.status)
          updateSession(sessionId, {
            status: `payment failed (${statusLabel})`,
            payment: {
              ...paymentInfo,
              status: "failed",
              message: statusLabel === "network error" ? "network error" : `charge ${statusLabel}`,
            },
          })
          pushProgress(
            sessionId,
            describeHttp(`${res.status || 0} POST`, "/api/v1/payments/charge", `charge failed (${statusLabel})`),
            "pricing",
            "user",
            "error"
          )
          return false
        }
        const amount = res.data?.amount_cents ?? paymentInfo.fareCents
        const paymentId = res.data?.payment_id ?? paymentInfo.paymentId
        updateSession(sessionId, {
          status: `payment captured - ${formatCurrency(amount)}`,
          payment: { ...paymentInfo, paymentId, fareCents: amount, status: "captured", message: undefined },
        })
        pushProgress(
          sessionId,
          describeHttp(
            `${res.status ?? 201} POST`,
            "/api/v1/payments/charge",
            `charge captured ${formatCurrency(amount)} (payment ${paymentId ?? "n/a"})`
          ),
          "pricing",
          "user",
          "success"
        )
        return true
      } catch {
        updateSession(sessionId, {
          status: "payment failed (network error)",
          payment: { ...paymentInfo, status: "failed", message: "network error" },
        })
        pushProgress(
          sessionId,
          describeHttp("0 POST", "/api/v1/payments/charge", "network error while charging fare"),
          "pricing",
          "user",
          "error"
        )
        return false
      }
    },
    [pushProgress, updateSession]
  )

  const lockSession = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.rideId) return
      stopTelemetry(sessionId)
      pushProgress(
        sessionId,
        describeHttp("OPTIONS", "/api/v1/lock", "CORS preflight before locking bike"),
        "user",
        "backend",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp(
          "POST",
          "/api/v1/lock",
          `lock ride ${session.rideId} at ${(
            session.activeBike?.lat ?? defaultPosition.lat
          ).toFixed(5)}, ${(session.activeBike?.lon ?? defaultPosition.lon).toFixed(5)}`
        ),
        "user",
        "backend",
        "info"
      )
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
          const metrics = data?.ride?.metrics ?? {}
          const bikeId = data?.ride?.bike_id ?? session.activeBike?.id
          const paymentDetails: EmulatorPayment | undefined = rideId
            ? {
                rideId,
                fareCents,
                status: "pending",
                metadata: {
                  meters: metrics?.meters,
                  seconds: metrics?.seconds,
                  bikeId: bikeId ?? undefined,
                  bikeQr: session.activeBike?.qr_public_id ?? session.qr,
                  userEmail: session.simEmail,
                  rideStartedAt: session.rideStartedAt ?? data?.ride?.started_at ?? null,
                  rideEndedAt: data?.ride?.ended_at ?? session.rideEndedAt ?? null,
                },
              }
            : undefined

          updateSession(sessionId, {
            status: paymentDetails ? "locked - awaiting payment" : `locked - fare ${fareCents} cents`,
            rideId: null,
            activeBike: undefined,
            runningFare: undefined,
            battery: undefined,
            telemetryTimer: null,
            idempUnlock: createKey("idem-u"),
            idempLock: createKey("idem-l"),
            payment: paymentDetails,
            rideEndedAt: data?.ride?.ended_at ?? session.rideEndedAt ?? null,
          })
          pushProgress(
            sessionId,
            describeHttp(
              String(status || 200),
              "/api/v1/lock",
              paymentDetails
                ? `bike locked, fare ${formatCurrency(fareCents)} ready to charge`
                : "bike locked without fare due"
            ),
            "backend",
            "user",
            "success"
          )

          await refreshBikes()
        } else {
          const detail = !ok ? ` (${status})` : data?.error ? `: ${data.error}` : ""
          updateSession(sessionId, { status: `lock failed${detail}` })
          pushProgress(
            sessionId,
            describeHttp(`${status || 500} POST`, "/api/v1/lock", `lock failed${detail}`),
            "backend",
            "user",
            "error"
          )
          if (session.rideId) {
            const fallbackBike = bikes.find((b: any) => b.qr_public_id === session.qr)
            const resumeInfo = session.activeBike ?? {
              id: fallbackBike?.id,
              qr_public_id: session.qr,
              lat,
              lon,
            }
            startTelemetry(sessionId, session.rideId, resumeInfo)
          }
        }
      } catch {
        updateSession(sessionId, { status: "lock failed (network error)" })
        pushProgress(
          sessionId,
          describeHttp("0 POST", "/api/v1/lock", "network error while locking bike"),
          "backend",
          "user",
          "error"
        )
        if (session.rideId) {
          const fallbackBike = bikes.find((b: any) => b.qr_public_id === session.qr)
          const resumeInfo = session.activeBike ?? {
            id: fallbackBike?.id,
            qr_public_id: session.qr,
            lat: session.activeBike?.lat ?? fallbackBike?.lat ?? defaultPosition.lat,
            lon: session.activeBike?.lon ?? fallbackBike?.lon ?? defaultPosition.lon,
          }
          startTelemetry(sessionId, session.rideId, resumeInfo)
        }
      }
    },
    [bikes, pushProgress, refreshBikes, startTelemetry, stopTelemetry, updateSession]
  )

  const markPaid = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.payment || session.payment.status === "captured") {
        return
      }
      await chargeRide(sessionId, session.payment, session.payment.metadata)
    },
    [chargeRide]
  )

  const requestRefund = useCallback(
    async (sessionId: string) => {
      const session = sessionsRef.current.find((s) => s.id === sessionId)
      if (!session || !session.payment || session.payment.status !== "captured" || !session.payment.paymentId) {
        return
      }
      const paymentInfo = session.payment
      pushProgress(
        sessionId,
        describeHttp("OPTIONS", "/api/v1/payments/refund", "CORS preflight before refund request"),
        "user",
        "pricing",
        "info"
      )
      pushProgress(
        sessionId,
        describeHttp("POST", "/api/v1/payments/refund", `request refund for payment ${paymentInfo.paymentId}`),
        "user",
        "pricing",
        "info"
      )
      updateSession(sessionId, {
        status: "requesting refund...",
        payment: { ...paymentInfo, message: "submitting refund request" },
      })
      try {
        const res = await apiPost(
          "/api/v1/payments/refund",
          { payment_id: paymentInfo.paymentId, reason: "Requested from emulator" },
          { "Idempotency-Key": createKey("idem-refund") },
          "pricing"
        )
        if (!res.ok) {
          updateSession(sessionId, {
            status: `refund request failed (${res.status})`,
            payment: { ...paymentInfo, message: `refund ${res.status}` },
          })
          pushProgress(
            sessionId,
            describeHttp(`${res.status} POST`, "/api/v1/payments/refund", `refund request failed (${res.status})`),
            "pricing",
            "user",
            "error"
          )
          return
        }
        updateSession(sessionId, {
          status: "refunded",
          payment: { ...paymentInfo, status: "refunded", message: "refund completed" },
        })
        pushProgress(
          sessionId,
          describeHttp(`${res.status ?? 200} POST`, "/api/v1/payments/refund", "refund completed"),
          "pricing",
          "user",
          "success"
        )
      } catch {
        updateSession(sessionId, {
          status: "refund request failed (network error)",
          payment: { ...paymentInfo, message: "refund request network error" },
        })
        pushProgress(
          sessionId,
          describeHttp("0 POST", "/api/v1/payments/refund", "network error while requesting refund"),
          "pricing",
          "user",
          "error"
        )
      }
    },
    [pushProgress, updateSession]
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
        const actorGroups = PROGRESS_ACTOR_ORDER.map((actor) => ({
          actor,
          entries: (session.progressLog ?? []).filter((entry) => entry.actor === actor),
        })).filter((group) => group.entries.length > 0)
        const actorColumnCount = Math.min(Math.max(actorGroups.length, 1), 3)
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
                {session.runningFare && (
                  <div style={{ marginTop: 6, fontSize: 13 }}>
                    Live fare: {formatCurrency(session.runningFare.fareCents)} (x
                    {session.runningFare.multiplier.toFixed(2)})
                  </div>
                )}
                {session.battery && (
                  <div
                    style={{
                      marginTop: 4,
                      fontSize: 12,
                      color: session.battery.pct <= 25 ? "#f97316" : "#6b7280",
                    }}
                  >
                    Battery: {session.battery.pct.toFixed(1)}%
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
            {!session.rideId && session.quote && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
                Quote: base {formatCurrency(session.quote.baseCents)} x multiplier x
                {session.quote.surgeMultiplier.toFixed(2)} ({session.quote.weather})
              </div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={() => lockSession(session.id)} disabled={session.rideId === null}>
                Lock
              </button>
            </div>
            <p style={{ marginTop: 8 }}>Status: {session.status}</p>
            {actorGroups.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 4 }}>Service activity</div>
                <div
                  style={{
                    display: "grid",
                    gap: 8,
                    gridTemplateColumns: `repeat(${actorColumnCount}, minmax(0, 1fr))`,
                  }}
                >
                  {actorGroups.map(({ actor, entries }) => {
                    const detail = PROGRESS_ACTOR_DETAILS[actor]
                    const recentEntries = entries.slice(-6)
                    return (
                      <div
                        key={actor}
                        style={{
                          border: "1px solid #1f2937",
                          borderRadius: 6,
                          background: "#0f172a",
                          padding: "6px 8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          borderTop: `2px solid ${detail.accent}`,
                          maxHeight: 180,
                          overflowY: "auto",
                        }}
                      >
                        <div style={{ fontSize: 12, color: detail.accent, fontWeight: 600 }}>
                          {detail.label}
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {recentEntries.map((entry) => {
                            const color =
                              entry.kind === "error"
                                ? "#f87171"
                                : entry.kind === "success"
                                ? "#34d399"
                                : "#9ca3af"
                            return (
                              <div key={entry.id} style={{ fontSize: 12, color, whiteSpace: "pre-wrap" }}>
                                {new Date(entry.ts).toLocaleTimeString()} - {entry.message}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
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








