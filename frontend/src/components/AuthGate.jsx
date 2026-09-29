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
    <main className="app-shell">
      <section className="hero">
        <div className="badge">SAHINAKSHA • SECURE WORKSPACE</div>
        <h1>Sahi<span>Naksha</span></h1>
        <p>{mode === "login" ? "Sign in to continue to the GIS workspace." : "Create an account for the GIS workspace."}</p>
        <form className="upload-card" onSubmit={submit}>
          <label className="file-picker"><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label>
          <label className="file-picker"><span>Password</span><input type="password" minLength="6" value={password} onChange={e=>setPassword(e.target.value)} required /></label>
          {message && <p className="error">{message}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}</button>
          <button type="button" className="secondary-button" onClick={()=>{setMode(mode==="login"?"signup":"login");setMessage("")}}>
            {mode === "login" ? "Create account" : "Back to sign in"}
          </button>
        </form>
      </section>
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

  if (!supabaseConfigured) return children;
  if (loading) return <main className="app-shell"><section className="hero"><h1>Loading Sahi<span>Naksha</span>…</h1></section></main>;
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
