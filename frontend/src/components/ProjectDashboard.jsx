import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";

function shell(content) {
  return <main className="gov-portal"><div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div><div className="gov-tools"><span>Accessibility</span><span>हिन्दी</span><span>English</span></div></div><header className="gov-header"><div className="gov-brand"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem"/><div><div className="gov-hindi">ग्रामीण विकास मंत्रालय</div><div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div><div className="gov-subtitle">GOVERNMENT OF INDIA</div></div></div><div className="sahinaksha-brand"><strong>SahiNaksha</strong><span>AI-Assisted Cadastral Mapping</span></div></header><div className="gov-notice"><b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.</div>{content}<footer className="gov-footer"><div><b>Government of India</b><br/>Ministry of Rural Development • SahiNaksha Demonstration Portal</div><div>Privacy Policy &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Contact</div></footer></main>;
}

export default function ProjectDashboard({ onStartSurvey }) {
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
    setBusy(true); setError("");
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Authentication session expired. Please sign in again.");
      const { data, error: projectError } = await supabase.from("projects").select("*").order("created_at", { ascending: false });
      if (projectError) throw projectError;
      setProjects(data || []);
    } catch (e) { setError(e.message || "Database unavailable."); }
    finally { setBusy(false); }
  }

  useEffect(() => { load(); }, []);

  async function createProject(e) {
    e.preventDefault(); setError(""); setMessage("");
    try {
      const { data: { user } } = await supabase.auth.getUser();
      const { data, error: insertError } = await supabase.from("projects").insert({ owner_id: user.id, name: projectName.trim(), description: projectDescription.trim() }).select().single();
      if (insertError) throw insertError;
      setProjectName(""); setProjectDescription(""); setMessage("Project created successfully."); await load(); setSelectedProject(data);
    } catch (e) { setError(e.message || "Unable to create project."); }
  }

  async function openProject(project) {
    setSelectedProject(project); setError(""); setMessage("");
    const { data, error: surveyError } = await supabase.from("surveys").select("*").eq("project_id", project.id).order("created_at", { ascending: false });
    if (surveyError) setError(surveyError.message); else setSurveys(data || []);
  }

  async function createSurvey(e) {
    e.preventDefault(); if (!selectedProject) return;
    setError(""); setMessage("");
    try {
      const { data, error: insertError } = await supabase.from("surveys").insert({ project_id: selectedProject.id, name: surveyName.trim(), status: "created" }).select().single();
      if (insertError) throw insertError;
      setSurveyName(""); setSurveys(x => [data, ...x]); setMessage("Survey created. Upload the orthomosaic to begin.");
    } catch (e) { setError(e.message || "Unable to create survey."); }
  }

  if (busy) return shell(<section className="auth-loading"><h1>Loading Sahi<span>Naksha</span>…</h1><p>Loading project workspace.</p></section>);

  return shell(<>
    <nav className="gov-nav"><button type="button">Project Dashboard</button><button type="button" onClick={load}>Refresh</button></nav>
    <section className="gov-content" style={{maxWidth:"1180px",margin:"28px auto",padding:"0 20px"}}>
      <div className="gov-page-title"><span>Digital Land Records &amp; Geospatial Services</span><small>Project &amp; Survey Workspace</small></div>
      <div className="workflow-heading"><span>01 • PROJECTS</span><h2>Project Dashboard</h2><p>Create a project, then create a survey workspace before uploading imagery.</p></div>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <div style={{display:"grid",gridTemplateColumns:"minmax(300px,1fr) minmax(300px,1fr)",gap:"18px"}}>
        <form className="upload-card" onSubmit={createProject}>
          <h3>Create Project</h3>
          <label className="file-picker"><span>Project name</span><input required value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="Village / survey project name"/></label>
          <label className="file-picker"><span>Description</span><textarea value={projectDescription} onChange={e=>setProjectDescription(e.target.value)} placeholder="Purpose, location or survey notes"/></label>
          <button className="primary-button" disabled={!projectName.trim()}>Create Project</button>
        </form>
        <div className="upload-card">
          <h3>Your Projects</h3>
          {projects.length===0?<p className="muted">No projects yet. Create the first survey project.</p>:projects.map(p=><button key={p.id} type="button" className="previous-item" style={{width:"100%",textAlign:"left",marginBottom:"8px"}} onClick={()=>openProject(p)}><strong>{p.name}</strong><span>{p.description||"No description"}</span></button>)}
        </div>
      </div>
      {selectedProject && <section style={{marginTop:"20px"}}><div className="workflow-heading"><span>02 • SURVEY</span><h2>{selectedProject.name}</h2><p>Create or open a survey workspace.</p></div>
        <div style={{display:"grid",gridTemplateColumns:"minmax(280px,360px) 1fr",gap:"18px"}}>
          <form className="upload-card" onSubmit={createSurvey}><h3>Create Survey</h3><label className="file-picker"><span>Survey name</span><input required value={surveyName} onChange={e=>setSurveyName(e.target.value)} placeholder="Orthomosaic survey"/></label><button className="primary-button">Create Survey</button></form>
          <div className="upload-card"><h3>Surveys</h3>{surveys.length===0?<p className="muted">No surveys created for this project.</p>:surveys.map(s=><div className="previous-item" key={s.id}><div className="previous-item-main"><strong>{s.name}</strong><span>Status: {s.status}</span><small>Created {new Date(s.created_at).toLocaleString()}</small></div><button className="primary-button compact" type="button" onClick={()=>onStartSurvey(selectedProject,s)}>Upload &amp; Process</button></div>)}</div>
        </div>
      </section>}
    </section>
  </>);
}
