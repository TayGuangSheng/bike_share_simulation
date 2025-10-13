import { useEffect } from "react"
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom"
import "./styles.css"
import { useAuth } from "../store/auth"

export default function App() {
  const loc = useLocation()
  const navigate = useNavigate()
  const token = useAuth((s) => s.token)
  const setToken = useAuth((s) => s.setToken)

  useEffect(() => {
    if (!token) {
      navigate("/login", { replace: true })
    }
  }, [token, navigate])

  const logout = () => {
    setToken(null)
    navigate("/login", { replace: true })
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>ELEN90061</h2>
        <nav>
          <Link className={loc.pathname === "/" ? "active" : ""} to="/">
            Dashboard
          </Link>
          <Link className={loc.pathname.startsWith("/map") ? "active" : ""} to="/map">
            Live Map
          </Link>
          <Link className={loc.pathname.startsWith("/bikes") ? "active" : ""} to="/bikes">
            Bikes
          </Link>
          <Link className={loc.pathname.startsWith("/revenue") ? "active" : ""} to="/revenue">
            Revenue
          </Link>
          <Link className={loc.pathname.startsWith("/emulator") ? "active" : ""} to="/emulator">
            User Emulator
          </Link>
        </nav>
      </aside>
      <main className="content">
        <header className="topbar">
          <span>Dockless Bike-Share Admin Portal</span>
          <div className="topbar-actions">
            <button className="btn secondary" onClick={() => navigate("/login")} disabled={!!token}>
              Login
            </button>
            <button className="btn" onClick={logout} disabled={!token}>
              Logout
            </button>
          </div>
        </header>
        <div className="page">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
