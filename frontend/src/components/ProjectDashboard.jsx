import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function shell(content) {
  return (
    <main className="gov-portal">
      <div className="gov-top-strip">
        <div>भारत सरकार &nbsp;|&nbsp; Government of India</div>
        <div className="gov-tools">
          <span>Accessibility</span>
          <span>हिन्दी</span>
          <span>English</span>
        </div>
      </div>
      <header className="gov-header">
        <div className="gov-brand">
          <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem" />
          <div>
            <div className="gov-hindi">ग्रामीण विकास मंत्रालय</div>
            <div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div>
            <div className="gov-subtitle">GOVERNMENT OF INDIA</div>
          </div>
        </div>
        <div className="sahinaksha-brand">
          <strong>Sahi<span>Naksha</span></strong>
          <span>AI-Assisted Cadastral Mapping</span>
        </div>
      </header>
      <div className="gov-notice">
        <b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.
      </div>
      {content}
      <footer className="gov-footer">
        <div><b>Government of India</b><br />Ministry of Rural Development • SahiNaksha Demonstration Portal</div>
        <div>Privacy Policy &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Help &amp; Support</div>
      </footer>
    </main>
  );
}

export default function ProjectDashboard({ onStartSurvey, onOpenResults }) {
  const [projects, setProjects] = useState([]);
  const [surveys, setSurveys] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [surveyName, setSurveyName] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Authentication session expired. Please sign in again.");
      const { data, error: projectError } = await supabase.from("projects").select("*").order("created_at", { ascending: false });
      if (projectError) throw projectError;
      setProjects(data || []);
    } catch (e) {
      setError(e.message || "Database unavailable.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createProject(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const { data: { user } } = await supabase.auth.getUser();
      const { data, error: insertError } = await supabase.from("projects").insert({
        owner_id: user.id,
        name: projectName.trim(),
        description: projectDescription.trim()
      }).select().single();
      if (insertError) throw insertError;
      setProjectName("");
      setProjectDescription("");
      setMessage("Project created successfully.");
      await load();
      setSelectedProject(data);
    } catch (e) {
      setError(e.message || "Unable to create project.");
    }
  }

  async function openProject(project) {
    setSelectedProject(project);
    setError("");
    setMessage("");
    const { data, error: surveyError } = await supabase.from("surveys").select("*").eq("project_id", project.id).order("created_at", { ascending: false });
    if (surveyError) setError(surveyError.message);
    else setSurveys(data || []);
  }

  async function openPersistedResults(survey) {
    setError("");
    setMessage("");
    try {
      const { data, error: jobError } = await supabase
        .from("processing_jobs")
        .select("id,analysis_id,status,result_snapshot,created_at,completed_at")
        .eq("survey_id", survey.id)
        .eq("status", "completed")
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (jobError) throw jobError;
      if (!data?.result_snapshot) throw new Error("No persisted processing result is available for this survey.");
      onOpenResults(selectedProject, survey, {
        ...data.result_snapshot,
        original_image_url: (data.result_snapshot.original_image_url || "").startsWith("http")
          ? data.result_snapshot.original_image_url
          : API.replace(/\/$/, "") + (data.result_snapshot.original_image_url || "")
      });
    } catch (e) {
      setError(e.message || "Unable to load persisted survey results.");
    }
  }

  async function createSurvey(e) {
    e.preventDefault();
    if (!selectedProject) return;
    setError("");
    setMessage("");
    try {
      const { data, error: insertError } = await supabase.from("surveys").insert({
        project_id: selectedProject.id,
        name: surveyName.trim(),
        status: "created"
      }).select().single();
      if (insertError) throw insertError;
      setSurveyName("");
      setSurveys(x => [data, ...x]);
      setMessage("Survey created. Upload the orthomosaic to begin.");
    } catch (e) {
      setError(e.message || "Unable to create survey.");
    }
  }

  if (busy) {
    return shell(
      <section className="auth-loading">
        <h1>Loading Sahi<span>Naksha</span>…</h1>
        <p>Loading project workspace.</p>
      </section>
    );
  }

  return shell(
    <>
      <nav className="gov-nav">
        <button type="button" className="active">📁 Project Workspace</button>
        <button type="button" onClick={load}>🔄 Refresh Data</button>
      </nav>
      <section className="gov-content">
        <div className="gov-page-title">
          <span>Digital Land Records &amp; Geospatial Services</span>
          <small>Project &amp; Survey Workspace</small>
        </div>
        <div className="workflow-heading">
          <span>01 • PROJECTS</span>
          <h2>Project Dashboard</h2>
          <p>Create a project, then configure a survey workspace before uploading high-resolution drone imagery.</p>
        </div>

        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "20px" }}>
          <form className="upload-card" onSubmit={createProject}>
            <h3><span>➕ Create New Project</span></h3>
            <div className="file-picker">
              <span>Project Name</span>
              <input required value={projectName} onChange={e => setProjectName(e.target.value)} placeholder="e.g. Rampur Village Cadastral Survey" />
            </div>
            <div className="file-picker">
              <span>Description / Location Notes</span>
              <textarea value={projectDescription} onChange={e => setProjectDescription(e.target.value)} placeholder="District, Tehsil, survey parameters or notes" />
            </div>
            <button className="primary-button" style={{ width: "100%", marginTop: "10px" }} disabled={!projectName.trim()}>
              Create Project
            </button>
          </form>

          <div className="upload-card">
            <h3><span>📂 Available Projects</span> <span className="badge">{projects.length} Total</span></h3>
            {projects.length === 0 ? (
              <p className="muted" style={{ padding: "20px 0", textAlign: "center" }}>No projects created yet. Use the form to start your first project.</p>
            ) : (
              <div style={{ maxHeight: "360px", overflowY: "auto", display: "grid", gap: "8px" }}>
                {projects.map(p => (
                  <button
                    key={p.id}
                    type="button"
                    className="previous-item"
                    style={{
                      width: "100%",
                      textAlign: "left",
                      cursor: "pointer",
                      borderColor: selectedProject?.id === p.id ? "var(--primary)" : "var(--border-subtle)",
                      background: selectedProject?.id === p.id ? "var(--primary-light)" : "var(--bg-main)"
                    }}
                    onClick={() => openProject(p)}
                  >
                    <div className="previous-item-main">
                      <strong>{p.name}</strong>
                      <span>{p.description || "No description provided"}</span>
                      <small>{new Date(p.created_at).toLocaleDateString()}</small>
                    </div>
                    {selectedProject?.id === p.id && <span className="badge">Active</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {selectedProject && (
          <section style={{ marginTop: "32px" }}>
            <div className="workflow-heading">
              <span>02 • SURVEYS IN {selectedProject.name.toUpperCase()}</span>
              <h2>Survey Workspaces</h2>
              <p>Configure a survey run, upload aerial imagery, and perform AI extraction.</p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "20px" }}>
              <form className="upload-card" onSubmit={createSurvey}>
                <h3><span>➕ New Survey Run</span></h3>
                <div className="file-picker">
                  <span>Survey Name</span>
                  <input required value={surveyName} onChange={e => setSurveyName(e.target.value)} placeholder="e.g. Block A Aerial Orthomosaic 2026" />
                </div>
                <button className="primary-button" style={{ width: "100%", marginTop: "10px" }}>
                  Create Survey Workspace
                </button>
              </form>

              <div className="upload-card">
                <h3><span>📋 Surveys</span> <span className="badge">{surveys.length} Runs</span></h3>
                {surveys.length === 0 ? (
                  <p className="muted" style={{ padding: "20px 0", textAlign: "center" }}>No surveys created for this project yet.</p>
                ) : (
                  <div style={{ maxHeight: "360px", overflowY: "auto", display: "grid", gap: "8px" }}>
                    {surveys.map(s => (
                      <div className="previous-item" key={s.id}>
                        <div className="previous-item-main">
                          <strong>{s.name}</strong>
                          <span>Status: <b style={{ textTransform: "capitalize", color: s.status === "complete" ? "var(--gov-green)" : "var(--text-secondary)" }}>{s.status}</b></span>
                          <small>Created {new Date(s.created_at).toLocaleString()}</small>
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          <button className="primary-button compact" type="button" onClick={() => onStartSurvey(selectedProject, s)}>
                            {s.status === "complete" ? "Re-upload & Reprocess" : "Upload & Process"}
                          </button>
                          {s.status === "complete" && (
                            <button className="secondary-button compact" type="button" onClick={() => openPersistedResults(s)}>
                              View GIS Map
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </section>
    </>
  );
}
