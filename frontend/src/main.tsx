import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom'
import App from './ui/App'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import LiveMap from './pages/LiveMap'
import Bikes from './pages/Bikes'
import Revenue from './pages/Revenue'
import UserEmulator from './pages/UserEmulator'
import Routing from './pages/Routing'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<App />}>
          <Route index element={<Dashboard />} />
          <Route path="map" element={<LiveMap />} />
          <Route path="routing" element={<Routing />} />
          <Route path="bikes" element={<Bikes />} />
          <Route path="revenue" element={<Revenue />} />
          <Route path="emulator" element={<UserEmulator />} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
