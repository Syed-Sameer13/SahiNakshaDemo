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
    <main className="gov-portal auth-portal"><div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div><div className="gov-tools"><span>Accessibility</span><span>हिन्दी</span><span>English</span><span>A−</span><span>A</span><span>A+</span></div></div><header className="gov-header"><div className="gov-brand"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem" /><div><div className="gov-hindi">ग्रामीण विकास मंत्रालय</div><div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div><div className="gov-subtitle">GOVERNMENT OF INDIA</div></div></div><div className="sahinaksha-brand"><strong>SahiNaksha</strong><span>AI-Assisted Cadastral Mapping</span></div></header><div className="gov-notice"><b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.</div><section className="auth-card-wrap"><div className="auth-card"><span className="badge">SECURE WORKSPACE</span><h1>Sahi<span>Naksha</span></h1><p>{mode === "login" ? "Sign in to continue to the GIS workspace." : "Create an account for the GIS workspace."}</p>
        <form className="upload-card auth-form" onSubmit={submit}>
          <label className="file-picker"><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label>
          <label className="file-picker"><span>Password</span><input type="password" minLength="6" value={password} onChange={e=>setPassword(e.target.value)} required /></label>
          {message && <p className="error">{message}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}</button>
          <button type="button" className="secondary-button auth-switch" onClick={()=>{setMode(mode==="login"?"signup":"login");setMessage("")}}>
            {mode === "login" ? "Create account" : "Back to sign in"}
          </button>
        </form><small className="auth-disclaimer">Access is provided only when Supabase authentication is configured for this prototype.</small></div></section><footer className="gov-footer"><div><b>Government of India</b><br/>Ministry of Rural Development • SahiNaksha Demonstration Portal</div><div>Privacy Policy &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Contact</div></footer></main>
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

  if (!supabaseConfigured) return children;
  if (loading) return <main className="gov-portal auth-portal"><div className="gov-top-strip"><div>भारत सरकार &nbsp;|&nbsp; Government of India</div></div><section className="auth-loading"><div className="service-seal">GIS<br/><small>e-Governance</small></div><h1>Loading Sahi<span>Naksha</span>…</h1><p>Preparing secure workspace.</p></section></main>;
  if (!session) return <AuthScreen onAuthenticated={setSession} />;

  return (
    <>
      <div style={{position:"fixed",right:18,top:14,zIndex:2000}}>
        <button className="secondary-button" onClick={()=>supabase.auth.signOut()}>Sign out</button>
      </div>
      {children}
    </>
  );
}
