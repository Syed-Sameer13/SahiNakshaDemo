import { useEffect, useState } from "react";
import { supabase, supabaseConfigured } from "../lib/supabase";

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result = mode === "login"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });

      if (result.error) throw result.error;
      if (mode === "signup" && !result.data.session) {
        setMessage("Account created. Check your email if email confirmation is enabled.");
      } else {
        onAuthenticated(result.data.session);
      }
    } catch (error) {
      setMessage(error.message || "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="gov-portal auth-portal">
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
      <section className="auth-card-wrap">
        <div className="auth-card">
          <span className="badge">SECURE WORKSPACE</span>
          <h1>Sahi<span>Naksha</span></h1>
          <p>{mode === "login" ? "Sign in to access your digital cadastral workspace." : "Create a new surveyor account."}</p>
          <form className="auth-form" onSubmit={submit}>
            <div className="file-picker">
              <span>Email Address</span>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@domain.gov.in" required />
            </div>
            <div className="file-picker">
              <span>Password</span>
              <input type="password" minLength="6" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
            </div>
            {message && <p className="error">{message}</p>}
            <button className="primary-button" disabled={busy}>
              {busy ? "Authenticating…" : mode === "login" ? "Sign In to Workspace" : "Create Surveyor Account"}
            </button>
            <button type="button" className="secondary-button auth-switch" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setMessage(""); }}>
              {mode === "login" ? "New user? Create an account" : "Already have an account? Sign in"}
            </button>
          </form>
          <small className="auth-disclaimer">Access is restricted to authorized GIS surveyors and land administration personnel.</small>
        </div>
      </section>
      <footer className="gov-footer">
        <div><b>Government of India</b><br />Ministry of Rural Development • SahiNaksha Demonstration Portal</div>
        <div>Privacy Policy &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Help &amp; Support</div>
      </footer>
    </main>
  );
}

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(supabaseConfigured);

  useEffect(() => {
    if (!supabaseConfigured) return;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSession(data.session);
        setLoading(false);
      }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  if (!supabaseConfigured) {
    return (
      <main className="gov-portal auth-portal">
        <div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div></div>
        <section className="auth-loading">
          <div className="badge">CONFIGURATION REQUIRED</div>
          <h1>Sahi<span>Naksha</span> setup needed</h1>
          <p>Please configure <code>VITE_SUPABASE_URL</code>, <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> and <code>VITE_API_URL</code>.</p>
        </section>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="gov-portal auth-portal">
        <div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div></div>
        <section className="auth-loading">
          <h1>Loading Sahi<span>Naksha</span>…</h1>
          <p>Initializing secure GIS environment.</p>
        </section>
      </main>
    );
  }

  if (!session) return <AuthScreen onAuthenticated={setSession} />;

  return (
    <>
      <div className="user-pill">
        <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>
          {session.user?.email || "Surveyor"}
        </span>
        <button className="secondary-button compact" onClick={() => supabase.auth.signOut()}>
          Sign Out
        </button>
      </div>
      {children}
    </>
  );
}
