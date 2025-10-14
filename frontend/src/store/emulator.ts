import { create } from "zustand"

export type EmulatorPayment = {
  rideId: number
  fareCents: number
  paymentId?: number
  status: "pending" | "authorized" | "captured" | "refund_pending" | "refunded" | "failed"
  message?: string
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
  activeBike?: {
    qr_public_id: string
    battery_pct?: number
    lat: number
    lon: number
  }
  payment?: EmulatorPayment
  userToken?: string | null
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
