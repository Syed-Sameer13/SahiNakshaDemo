import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function formatDate(value) {
  if (!value) return "Unknown date";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return "Unknown date";
  }
}

export default function UploadPanel({ onComplete, history = [], onOpenPrevious, onRemovePrevious }) {
  const [file, setFile] = useState(null);
  const [reference, setReference] = useState(null);
  const [groundTruth, setGroundTruth] = useState(null);
  const [dsm, setDsm] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPrevious, setShowPrevious] = useState(false);

  function chooseImage(f) {
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) {
      setError("Please choose a JPG, JPEG or PNG image.");
      return;
    }
    setError("");
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  function chooseGeoJson(f, setter, label) {
    if (!f) return;
    if (!/\.(json|geojson)$/i.test(f.name)) {
      setError(label + " must be a .json or .geojson file.");
      return;
    }
    setError("");
    setter(f);
  }

  function chooseDsm(f) {
    if (!f) return;
    if (!/\.(jpg|jpeg|png)$/i.test(f.name)) {
      setError("DSM prototype input must currently be an aligned PNG/JPG grayscale raster.");
      return;
    }
    setError("");
    setDsm(f);
  }

  async function analyze() {
    if (!file) {
      setError("Choose a drone or orthomosaic image before analysis.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const body = new FormData();
      body.append("file", file);
      if (reference) body.append("reference_parcels", reference);
      if (groundTruth) body.append("ground_truth", groundTruth);
      if (dsm) body.append("dsm", dsm);

      const response = await fetch(API + "/analyze", { method: "POST", body });
      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json")
        ? await response.json()
        : { detail: await response.text() };

      if (!response.ok) {
        throw new Error(
          data.detail ||
          data.message ||
          "Backend returned HTTP " + response.status
        );
      }

      onComplete({ ...data, original_image_url: API + data.original_image_url });
    } catch (e) {
      if (e instanceof TypeError && /fetch/i.test(e.message)) {
        setError("Cannot reach the SahiNaksha backend. The server may be waking up or temporarily unavailable. Please wait 30–60 seconds and try again.");
      } else {
        setError(e.message || "Unable to analyze image.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="gov-portal">
      <div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div><div className="gov-tools"><span>Skip to main content</span><span>हिन्दी</span><span>English</span><span>A−</span><span>A</span><span>A+</span></div></div>
      <header className="gov-header"><div className="gov-brand"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem" /><div><div className="gov-hindi">ग्रामीण विकास मंत्रालय</div><div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div><div className="gov-subtitle">GOVERNMENT OF INDIA</div></div></div><div className="header-identity"><img className="ministry-logo" src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Ministry_of_Rural_Development.png/250px-Ministry_of_Rural_Development.png" alt="Ministry of Rural Development logo" /><div className="sahinaksha-brand"><strong>SahiNaksha</strong><span>AI-Assisted Cadastral Mapping</span></div></div></header>
      <nav className="gov-nav"><span>Home</span><span>About SahiNaksha</span><span>Land &amp; Survey</span><span>GIS Services</span><span>Reports</span><span>Help &amp; Support</span></nav>
      <div className="gov-notice"><b>Prototype Portal</b> — SahiNaksha is an SIH 2026 demonstration system and is not an official Government of India service.</div>
      <section className="hero gov-content" id="main-content">
        <div className="gov-page-title"><span>Digital Land Records &amp; Geospatial Services</span><small>Department of Land Resources • Demonstration Portal</small></div>
        <div className="service-intro"><div><span className="badge">SAHINAKSHA • GEOSPATIAL DEMONSTRATION</span><h1>AI-Assisted <span>Cadastral Mapping</span></h1><p>Drone imagery processing, GIS parcel refinement, topology validation and human-reviewed map generation.</p></div><div className="service-seal">GIS<br/><small>e-Governance</small></div></div>

        <button
          className="previous-works-button"
          onClick={() => setShowPrevious((current) => !current)}
          type="button"
        >
          <span>↩</span>
          Previous Works
          <small>{history.length}</small>
        </button>

        {showPrevious && (
          <div className="previous-works-panel">
            <div className="previous-works-header">
              <div>
                <span className="report-kicker">LOCAL HISTORY</span>
                <h2>Previous analyses</h2>
                <p>Open an earlier analysis with one click. Review decisions and attribute edits remain linked to its analysis ID.</p>
              </div>
              <button className="secondary-button" onClick={() => setShowPrevious(false)} type="button">Close</button>
            </div>

            {history.length === 0 ? (
              <div className="previous-empty">
                <strong>No previous works yet</strong>
                <span>Completed analyses will automatically appear here.</span>
              </div>
            ) : (
              <div className="previous-list">
                {history.map((item) => (
                  <div className="previous-item" key={item.analysis_id}>
                    <div className="previous-item-main">
                      <strong>Analysis {item.analysis_id || "Unknown"}</strong>
                      <span>{formatDate(item.saved_at)}</span>
                      <small>
                        {item.buildings?.features?.length || 0} buildings · {item.roads?.features?.length || 0} roads · {item.parcels?.features?.length || 0} parcels
                      </small>
                    </div>
                    <div className="previous-item-actions">
                      <button className="primary-button compact" type="button" onClick={() => onOpenPrevious(item)}>
                        Open Analysis
                      </button>
                      <button className="secondary-button compact" type="button" onClick={() => onRemovePrevious(item.analysis_id)}>
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="workflow-heading"><span>Online Service</span><h2>Generate Preliminary Cadastral Map</h2><p>Upload the required survey imagery and optional GIS reference layers to begin processing.</p></div>
        <div className="upload-card">
          <div className="service-steps"><div><b>01</b><span>Upload imagery</span></div><div><b>02</b><span>Run geospatial analysis</span></div><div><b>03</b><span>Review &amp; validate</span></div></div>
          <p>Minimum input is a high-resolution drone/orthomosaic image. Existing parcel GIS, DSM and ground-truth layers can be added for additional validation.</p>

          <label className="file-picker">
            <input type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={(e) => chooseImage(e.target.files?.[0])}/>
            <span>{file ? file.name : "1. Required — Drone / Orthomosaic Image"}</span>
          </label>

          <label className="file-picker">
            <input type="file" accept=".json,.geojson" onChange={(e) => chooseGeoJson(e.target.files?.[0], setReference, "Existing parcel layer")}/>
            <span>{reference ? reference.name : "2. Recommended — Existing Parcel GIS (.geojson)"}</span>
          </label>

          <label className="file-picker">
            <input type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={(e) => chooseDsm(e.target.files?.[0])}/>
            <span>{dsm ? dsm.name : "3. Optional — Aligned DSM / Height Raster"}</span>
          </label>

          <label className="file-picker">
            <input type="file" accept=".json,.geojson" onChange={(e) => chooseGeoJson(e.target.files?.[0], setGroundTruth, "Ground truth layer")}/>
            <span>{groundTruth ? groundTruth.name : "4. Optional — Ground Truth for Accuracy Metrics"}</span>
          </label>

          {preview && <img className="preview" src={preview} alt="Selected aerial preview"/>}

          <div className="gov-form-note"><b>Service note:</b> Generated maps are preliminary outputs for demonstration and survey-support workflows. They require authoritative cadastral and field validation before legal use.</div>
          <div className="muted api-note">Service endpoint: {API}</div>

          {error && <p className="error">{error}</p>}

          <button className="primary-button" onClick={analyze} disabled={loading}>
            {loading ? "Running AI cadastral pipeline…" : "Generate Preliminary Cadastral Map"}
          </button>
        </div>
      </section>
      <footer className="gov-footer"><div><b>Government of India</b><br/>Ministry of Rural Development • SahiNaksha Demonstration Portal</div><div>Privacy Policy &nbsp;|&nbsp; Terms &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Contact</div></footer>
    </main>
  );
}
