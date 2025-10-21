import { create } from "zustand"

export type EmulatorQuote = {
  baseCents: number
  perMinCents: number
  perKmCents: number
  surgeMultiplier: number
  weather: string
  demandFactor: number
}

export type EmulatorRunningFare = {
  fareCents: number
  multiplier: number
  seconds: number
  meters: number
}

export type EmulatorBattery = {
  pct: number
  lastUpdated: number
}

export type EmulatorPayment = {
  rideId: number
  fareCents: number
  paymentId?: number
  status: "pending" | "authorized" | "captured" | "refund_pending" | "refunded" | "failed"
  message?: string
  metadata?: {
    meters?: number
    seconds?: number
    bikeId?: number
    bikeQr?: string
    userEmail?: string
    rideStartedAt?: string | null
    rideEndedAt?: string | null
  }
}

export type EmulatorProgressActor = "user" | "backend" | "pricing" | "battery" | "weather"

export type EmulatorProgressEntry = {
  id: string
  message: string
  actor: EmulatorProgressActor
  target: EmulatorProgressActor | "system"
  kind: "info" | "success" | "error"
  ts: number
}

export type EmulatorSession = {
  id: string
  label: string
  simEmail: string
  qr: string
  rideId: number | null
  status: string
  idempUnlock: string
  idempLock: string
  telemetryTimer: number | null
  rideStartedAt?: string | null
  rideEndedAt?: string | null
  activeBike?: {
    id?: number
    qr_public_id: string
    battery_pct?: number
    lat: number
    lon: number
  }
  quote?: EmulatorQuote
  runningFare?: EmulatorRunningFare
  battery?: EmulatorBattery
  payment?: EmulatorPayment
  userToken?: string | null
  progressLog: EmulatorProgressEntry[]
}

type EmulatorStore = {
  sessions: EmulatorSession[]
  counter: number
  setSessions: (updater: EmulatorSession[] | ((prev: EmulatorSession[]) => EmulatorSession[])) => void
  reset: () => void
  nextIndex: () => number
}

export const useEmulatorStore = create<EmulatorStore>((set, get) => ({
  sessions: [],
  counter: 0,
  setSessions: (updater) =>
    set((state) => ({
      sessions:
        typeof updater === "function"
          ? (updater as (prev: EmulatorSession[]) => EmulatorSession[])(state.sessions)
          : updater,
    })),
  reset: () => set({ sessions: [], counter: 0 }),
  nextIndex: () => {
    const next = get().counter + 1
    set({ counter: next })
    return next
  },
}))
