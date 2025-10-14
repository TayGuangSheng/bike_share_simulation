import React from "react"
import { usePricingMultiplier } from "../hooks/usePricingMultiplier"

export default function MultiplierBadge() {
  const { snapshot, loading } = usePricingMultiplier(15000)
  if (loading || !snapshot) return null
  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      padding: "4px 8px",
      borderRadius: 8,
      background: "#eff6ff",
      color: "#1e40af",
      fontSize: 13,
      fontWeight: 600,
    }} title={`Weather: ${snapshot.weather}; Active rides: ${snapshot.active_rides}`}>
      <span>Multiplier</span>
      <span style={{ padding: "2px 6px", background: "#dbeafe", borderRadius: 6 }}>{snapshot.multiplier.toFixed(2)}x</span>
    </div>
  )
}
