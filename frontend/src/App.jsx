import { useEffect, useState } from "react";
import UploadPanel from "./components/UploadPanel";
import Dashboard from "./components/Dashboard";
import AuthGate from "./components/AuthGate";
import ProjectDashboard from "./components/ProjectDashboard";

const HISTORY_KEY = "sahinaksha:analysis-history";

function readHistory() {
  try { const raw = localStorage.getItem(HISTORY_KEY); return raw ? JSON.parse(raw) : []; } catch { return []; }
}

function saveHistory(items) {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(items)); } catch {}
}

export default function App() {
  const [view, setView] = useState("projects");
  const [project, setProject] = useState(null);
  const [survey, setSurvey] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(() => readHistory());

  useEffect(() => { saveHistory(history); }, [history]);

  const startSurvey = (selectedProject, selectedSurvey) => {
    setProject(selectedProject);
    setSurvey(selectedSurvey);
    setResult(null);
    setView("upload");
  };

  const completeAnalysis = (analysis) => {
    setResult(analysis);
    setHistory(current => [{
      ...analysis,
      project_id: project?.id,
      survey_id: survey?.id,
      saved_at: new Date().toISOString(),
    }, ...current.filter(x => x.analysis_id !== analysis.analysis_id)].slice(0, 20));
    setView("map");
  };

  const openPrevious = (analysis) => {
    setProject({ id: analysis.project_id, name: analysis.project_name || "Previous Project" });
    setSurvey({ id: analysis.survey_id, name: analysis.survey_name || "Previous Survey" });
    setResult(analysis);
    setView("map");
  };

  const resetToProjects = () => {
    setResult(null);
    setSurvey(null);
    setProject(null);
    setView("projects");
  };

  return (
    <AuthGate>
      {view === "projects" && (
        <ProjectDashboard
          onStartSurvey={startSurvey}
          onSignOut={resetToProjects}
        />
      )}
      {view === "upload" && (
        <UploadPanel
          project={project}
          survey={survey}
          onComplete={completeAnalysis}
          history={history}
          onOpenPrevious={openPrevious}
          onRemovePrevious={id => setHistory(items => items.filter(x => x.analysis_id !== id))}
          onBack={resetToProjects}
        />
      )}
      {view === "map" && result && (
        <Dashboard
          result={result}
          project={project}
          survey={survey}
          onBack={() => setView("upload")}
          onReset={resetToProjects}
        />
      )}
    </AuthGate>
  );
}
