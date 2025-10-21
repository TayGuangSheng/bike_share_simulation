export default function Dashboard() {
  return (
    <div className="card">
      <h3>Get Started</h3>
      <p>This dashboard mirrors the rider app and streams live traffic from every service.</p>

      <div className="section">
        <h4>Quick Tour</h4>
        <div className="info-grid">
          <div className="info-tile">
            <strong>User Emulator</strong>
            <span>Spin up riders, scan bikes, and trigger the full unlock → ride → lock → charge flow.</span>
          </div>
          <div className="info-tile">
            <strong>Service Activity</strong>
            <span>Timeline of every request/response across backend, pricing, weather, and battery services.</span>
          </div>
          <div className="info-tile">
            <strong>Quote &amp; Battery Panels</strong>
            <span>Fare multipliers and telemetry drain update in real time while a ride is in progress.</span>
          </div>
        </div>
      </div>

      <div className="section">
        <h4>Ride Flow</h4>
        <div className="step-list">
          <div className="step-card">
            <div className="step-index">1</div>
            <div>
              <strong>Add Emulator</strong>
              <div>Select a simulated rider profile and bike.</div>
            </div>
          </div>
          <div className="step-card">
            <div className="step-index">2</div>
            <div>
              <strong>Scan &amp; Unlock</strong>
              <div>Kick off the ride and confirm the unlock event in Service Activity.</div>
            </div>
          </div>
          <div className="step-card">
            <div className="step-index">3</div>
            <div>
              <strong>Ride</strong>
              <div>Stream telemetry; watch fares, weather calls, and battery updates tick in.</div>
            </div>
          </div>
          <div className="step-card">
            <div className="step-index">4</div>
            <div>
              <strong>Lock</strong>
              <div>End the trip and review the final fare + nearest parking hints.</div>
            </div>
          </div>
          <div className="step-card">
            <div className="step-index">5</div>
            <div>
              <strong>Charge</strong>
              <div>Capture payment and verify the pricing webhook back to the backend.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h4>Explore Further</h4>
        <ul>
          <li>Open <strong>Live Map</strong> to see bike positions animate as telemetry streams.</li>
          <li>Use <strong>Bikes</strong> for a live inventory table with battery and lock state.</li>
          <li>Check <strong>Revenue</strong> to experiment with pricing scenarios and multipliers.</li>
        </ul>
        <p className="muted">
          Tip: screenshots of the Service Activity timeline and Live Map during a ride make great quick-start visuals for
          teammates.
        </p>
      </div>
    </div>
  );
}
