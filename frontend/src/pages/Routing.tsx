import { useEffect, useRef, useState } from 'react'
import L, { LeafletMouseEvent } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { apiPost } from '../store/api'

type Coord = { lat: number; lon: number }
type RouteVariant = 'shortest' | 'safest'

export default function Routing() {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const [from, setFrom] = useState<Coord | null>(null)
  const [to, setTo] = useState<Coord | null>(null)
  const [variant, setVariant] = useState<RouteVariant>('shortest')
  const [graph, setGraph] = useState<string>('toy')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [distanceM, setDistanceM] = useState<number | null>(null)
  const [timeS, setTimeS] = useState<number | null>(null)

  const fromMarker = useRef<L.Marker | null>(null)
  const toMarker = useRef<L.Marker | null>(null)
  const routeLayer = useRef<L.GeoJSON<any> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    if (!mapRef.current) {
      mapRef.current = L.map(containerRef.current).setView([1.305, 103.805], 14)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {}).addTo(mapRef.current)
      mapRef.current.on('click', (e: LeafletMouseEvent) => {
        const c: Coord = { lat: e.latlng.lat, lon: e.latlng.lng }
        // First click sets from, second sets to, subsequent clicks alternate to make it easy
        if (!from || (from && to)) {
          setFrom(c)
          setTo(null)
        } else if (!to) {
          setTo(c)
        }
      })
    }
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  // reflect markers
  useEffect(() => {
    if (!mapRef.current) return
    if (from) {
      if (!fromMarker.current) {
        fromMarker.current = L.marker([from.lat, from.lon], { draggable: true, title: 'From' })
          .addTo(mapRef.current)
          .bindPopup('From')
        fromMarker.current.on('dragend', () => {
          const ll = (fromMarker.current as L.Marker).getLatLng()
          setFrom({ lat: ll.lat, lon: ll.lng })
        })
      } else {
        fromMarker.current.setLatLng([from.lat, from.lon])
      }
    } else {
      fromMarker.current?.remove()
      fromMarker.current = null
    }
  }, [from])

  useEffect(() => {
    if (!mapRef.current) return
    if (to) {
      if (!toMarker.current) {
        toMarker.current = L.marker([to.lat, to.lon], { draggable: true, title: 'To' })
          .addTo(mapRef.current)
          .bindPopup('To')
        toMarker.current.on('dragend', () => {
          const ll = (toMarker.current as L.Marker).getLatLng()
          setTo({ lat: ll.lat, lon: ll.lng })
        })
      } else {
        toMarker.current.setLatLng([to.lat, to.lon])
      }
    } else {
      toMarker.current?.remove()
      toMarker.current = null
    }
  }, [to])

  const clearRouteLayer = () => {
    if (routeLayer.current) {
      routeLayer.current.remove()
      routeLayer.current = null
    }
  }

  const fitRoute = (geojson: any) => {
    if (!mapRef.current) return
    const gj = L.geoJSON(geojson)
    const bounds = gj.getBounds()
    if (bounds.isValid()) {
      mapRef.current.fitBounds(bounds.pad(0.2))
    }
  }

  const compute = async () => {
    setError(null)
    setDistanceM(null)
    setTimeS(null)
    clearRouteLayer()
    if (!from || !to) {
      setError('Select both start and end by clicking on the map')
      return
    }
    setBusy(true)
    const body = { from, to, variant, graph }
    const { ok, status, data } = await apiPost('/api/v1/routes', body)
    setBusy(false)
    if (!ok) {
      setError(typeof data?.detail === 'string' ? data.detail : `Routing failed (${status})`)
      return
    }
    setDistanceM(data.total_distance_m)
    setTimeS(data.est_time_s)
    if (mapRef.current) {
      routeLayer.current = L.geoJSON({ type: 'Feature', geometry: data.polyline_geojson, properties: {} }, {
        style: { color: variant === 'safest' ? '#10b981' : '#2563eb', weight: 5, opacity: 0.9 },
      }).addTo(mapRef.current)
    }
    fitRoute(data.polyline_geojson)
  }

  const resetAll = () => {
    setFrom(null)
    setTo(null)
    setDistanceM(null)
    setTimeS(null)
    clearRouteLayer()
  }

  return (
    <div className="card" style={{ height: 'calc(100% - 0px)' }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>
          Graph
          <select className="input" value={graph} onChange={e => setGraph(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="toy">toy</option>
            <option value="civic">civic</option>
          </select>
        </label>
        <label>
          Variant
          <select className="input" value={variant} onChange={e => setVariant(e.target.value as RouteVariant)} style={{ marginLeft: 8 }}>
            <option value="shortest">shortest</option>
            <option value="safest">safest</option>
          </select>
        </label>
        <button className="btn" onClick={compute} disabled={!from || !to || busy}>
          {busy ? 'Computing…' : 'Compute Route'}
        </button>
        <button className="btn secondary" onClick={resetAll} disabled={busy}>
          Reset
        </button>
        <span style={{ marginLeft: 'auto' }}>
          {from ? `From: ${from.lat.toFixed(5)}, ${from.lon.toFixed(5)}` : 'From: click map'}
          {'  '}
          {to ? `To: ${to.lat.toFixed(5)}, ${to.lon.toFixed(5)}` : 'To: click map'}
        </span>
      </div>
      {error && (
        <div style={{ color: '#b91c1c', marginBottom: 8 }}>
          {error}
        </div>
      )}
      {(distanceM !== null || timeS !== null) && (
        <div style={{ marginBottom: 8 }}>
          {distanceM !== null && <span>Distance: {(distanceM / 1000).toFixed(2)} km</span>}
          {'  '}
          {timeS !== null && <span> • Est. Time: {Math.round(timeS)} s</span>}
        </div>
      )}
      <div ref={containerRef} style={{ height: '80vh', minHeight: 480, width: '100%' }} />
    </div>
  )
}

