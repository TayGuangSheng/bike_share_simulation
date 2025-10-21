import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { apiGet } from '../store/api'

export default function LiveMap(){
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersRef = useRef<Record<string, L.CircleMarker>>({})
  const [bikeList, setBikeList] = useState<any[]>([])
  const [selectedBike, setSelectedBike] = useState<string>("")

  const formatPopup = (bike: any) => `Bike ${bike.qr_public_id} (${bike.battery_pct}%)<br />(${bike.lat.toFixed(5)}, ${bike.lon.toFixed(5)})`

  useEffect(()=>{
    if(!containerRef.current) return
    if(!mapRef.current){
      mapRef.current = L.map(containerRef.current).setView([1.305, 103.805], 14)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {}).addTo(mapRef.current)
    }
    return () => {
      Object.values(markersRef.current).forEach(m => m.remove())
      markersRef.current = {}
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(()=>{
    if(!mapRef.current) return
    let cancelled = false
    async function load(){
      const { ok, status, data } = await apiGet('/api/v1/bikes')
      if(!ok || !Array.isArray(data)){
        console.warn('LiveMap load failed', status, data)
        return
      }
      if(cancelled) return
      setBikeList(data)
      setSelectedBike(prev => {
        if (prev && data.some((b:any)=>b.qr_public_id === prev)) return prev
        return data[0]?.qr_public_id ?? ""
      })

      const seen = new Set<string>()

      data.forEach((b: any) => {
        seen.add(b.qr_public_id)
        const isInUse = b.lock_state !== "locked"
        const color = isInUse ? "#ef4444" : "#2563eb"
        const existing = markersRef.current[b.qr_public_id]

        if (existing) {
          existing.setLatLng([b.lat, b.lon])
          existing.setStyle({ color, fillColor: color })
          existing.setPopupContent(formatPopup(b))
        } else {
          const mk = L.circleMarker([b.lat, b.lon], {
            radius: 8,
            color,
            fillColor: color,
            fillOpacity: 1,
            weight: 2,
          }).bindPopup(formatPopup(b))
          mk.addTo(mapRef.current!)
          markersRef.current[b.qr_public_id] = mk
        }
      })

      Object.keys(markersRef.current).forEach((qr) => {
        if (!seen.has(qr)) {
          markersRef.current[qr].remove()
          delete markersRef.current[qr]
        }
      })
    }
    load()
    const interval = setInterval(load, 2000)
    return ()=>{
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const locateSelected = () => {
    if (!selectedBike) return
    const bike = bikeList.find((b:any) => b.qr_public_id === selectedBike)
    if (!bike || !mapRef.current) return
    mapRef.current.flyTo([bike.lat, bike.lon], Math.max(mapRef.current.getZoom(), 16), { duration: 0.8 })
    const marker = markersRef.current[selectedBike]
    if(marker){
      marker.setPopupContent(formatPopup(bike))
      marker.openPopup()
    }
  }

  return <div className="card" style={{height:'calc(100% - 0px)'}}>
    <div style={{display:'flex', gap:12, marginBottom:12}}>
      <select className="input" value={selectedBike} onChange={e=>setSelectedBike(e.target.value)}>
        {bikeList.length === 0 ? <option value="">No bikes</option> : bikeList.map((b:any)=>(
          <option key={b.id ?? b.qr_public_id} value={b.qr_public_id}>
            {b.qr_public_id} ({b.status}/{b.lock_state})
          </option>
        ))}
      </select>
      <button className="btn" onClick={locateSelected} disabled={!selectedBike}>
        Locate
      </button>
    </div>
    <div ref={containerRef} style={{height:'80vh', minHeight:480, width:'100%'}} />
  </div>
}
