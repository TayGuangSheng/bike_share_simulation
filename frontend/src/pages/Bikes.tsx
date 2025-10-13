import { useEffect, useState } from 'react'
import { apiGet } from '../store/api'

export default function Bikes(){
  const [bikes, setBikes] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(()=>{ (async()=>{
    setError(null)
    const { ok, status, data } = await apiGet('/api/v1/bikes')
    if(!ok){
      setBikes([])
      setError(status === 401 ? 'Please log in to view bikes.' : `Failed to load bikes (${status})`)
      return
    }
    if(!Array.isArray(data)){
      setBikes([]); setError('Unexpected response from server.'); return
    }
    setBikes(data)
  })() }, [])

  return (
    <div className="card">
      <h3>Bikes</h3>
      {error && <div className="p-2" style={{color:'#f87171'}}>{error}</div>}
      <table className="table">
        <thead><tr><th>ID</th><th>QR</th><th>Status</th><th>Lock</th><th>Battery</th><th>Lat</th><th>Lon</th></tr></thead>
        <tbody>
          {bikes.map(b=>(
            <tr key={b.id}>
              <td>{b.id}</td><td>{b.qr_public_id}</td><td>{b.status}</td><td>{b.lock_state}</td>
              <td>{b.battery_pct}%</td><td>{b.lat.toFixed(5)}</td><td>{b.lon.toFixed(5)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
