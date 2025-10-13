import { useEffect, useState, FormEvent } from "react"
import { useAuth } from "../store/auth"
import { useNavigate } from "react-router-dom"

export default function Login() {
  const [email, setEmail] = useState("admin@demo")
  const [password, setPassword] = useState("admin123")
  const [loading, setLoading] = useState(false)
  const setToken = useAuth((s) => s.setToken)
  const token = useAuth((s) => s.token)
  const nav = useNavigate()

  useEffect(() => {
    if (token) {
      nav("/", { replace: true })
    }
  }, [token, nav])

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    try {
      const r = await fetch("http://localhost:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
      if (!r.ok) throw new Error("Login failed")
      const data = await r.json()
      setToken(data.access_token)
      nav("/")
    } catch (err) {
      alert("Login failed")
    }
    setLoading(false)
  }

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh" }}>
      <form className="card" onSubmit={submit} style={{ width: 360 }}>
        <h3>Login</h3>
        <div>
          <input
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            autoComplete="email"
          />
        </div>
        <div>
          <input
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete="current-password"
          />
        </div>
        <div style={{ display: "flex", marginTop: 12 }}>
          <button className="btn" disabled={loading} type="submit" style={{ width: "100%" }}>
            Sign in
          </button>
        </div>
      </form>
    </div>
  )
}
