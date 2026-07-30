"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setError(error.message);
    }

    setLoading(false);
  };

  return (
    <main style={pageStyle}>
      {/* Background orb */}
      <div style={orbStyle} />

      <div style={cardStyle}>
        {/* Brand */}
        <div style={brandStyle}>
          <span style={brandTextStyle}>VERITAS</span>
        </div>

        <h1 style={titleStyle}>Welcome back</h1>
        <p style={subtitleStyle}>Sign in to your account to continue</p>

        <form onSubmit={handleLogin} style={formStyle}>
          <div style={fieldStyle}>
            <label htmlFor="email" style={labelStyle}>
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              style={inputStyle}
              onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
              onBlur={(e) => Object.assign(e.target.style, { borderColor: 'rgba(255,255,255,0.08)', boxShadow: 'none' })}
            />
          </div>

          <div style={fieldStyle}>
            <label htmlFor="password" style={labelStyle}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={inputStyle}
              onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
              onBlur={(e) => Object.assign(e.target.style, { borderColor: 'rgba(255,255,255,0.08)', boxShadow: 'none' })}
            />
          </div>

          <button
            id="login-btn"
            type="submit"
            disabled={loading}
            style={{
              ...btnStyle,
              opacity: loading ? 0.6 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        {error && (
          <div id="login-error" style={errorStyle}>
            <span>⚠️</span> {error}
          </div>
        )}

        <p style={footerTextStyle}>
          Don&apos;t have an account?{" "}
          <Link href="/signup" style={linkStyle}>
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}

/* ── Styles ── */
const pageStyle = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "2rem",
  position: "relative",
  overflow: "hidden",
};

const orbStyle = {
  position: "absolute",
  width: "500px",
  height: "500px",
  borderRadius: "50%",
  background: "radial-gradient(circle, rgba(108,92,231,0.2) 0%, transparent 70%)",
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  filter: "blur(60px)",
  pointerEvents: "none",
};

const cardStyle = {
  position: "relative",
  width: "100%",
  maxWidth: "420px",
  padding: "2.5rem",
  background: "rgba(255, 255, 255, 0.03)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  borderRadius: "20px",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
};

const brandStyle = {
  textAlign: "center",
  marginBottom: "2rem",
};

const brandTextStyle = {
  fontSize: "1.3rem",
  fontWeight: "800",
  letterSpacing: "-0.5px",
  background: "linear-gradient(135deg, #A78BFA, #6C5CE7)",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
  backgroundClip: "text",
};

const titleStyle = {
  fontSize: "1.8rem",
  fontWeight: "800",
  letterSpacing: "-0.03em",
  marginBottom: "0.4rem",
  color: "#FFFFFF",
};

const subtitleStyle = {
  fontSize: "0.95rem",
  color: "#94A3B8",
  marginBottom: "2rem",
};

const formStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "1.25rem",
};

const fieldStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "0.4rem",
};

const labelStyle = {
  fontSize: "0.85rem",
  fontWeight: "600",
  color: "#94A3B8",
  letterSpacing: "0.02em",
};

const inputStyle = {
  width: "100%",
  padding: "0.75rem 1rem",
  fontSize: "0.95rem",
  background: "rgba(255, 255, 255, 0.04)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  borderRadius: "10px",
  color: "#FFFFFF",
  outline: "none",
  transition: "border-color 0.2s, box-shadow 0.2s",
  boxSizing: "border-box",
  fontFamily: "inherit",
};

const inputFocusStyle = {
  borderColor: "#6C5CE7",
  boxShadow: "0 0 0 3px rgba(108, 92, 231, 0.15)",
};

const btnStyle = {
  width: "100%",
  padding: "0.85rem",
  fontSize: "1rem",
  fontWeight: "700",
  background: "linear-gradient(135deg, #6C5CE7, #A78BFA)",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "10px",
  cursor: "pointer",
  transition: "transform 0.2s, box-shadow 0.2s",
  marginTop: "0.5rem",
  fontFamily: "inherit",
  letterSpacing: "0.01em",
};

const errorStyle = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  padding: "0.75rem 1rem",
  marginTop: "1.25rem",
  background: "rgba(255, 107, 107, 0.1)",
  border: "1px solid rgba(255, 107, 107, 0.25)",
  borderRadius: "10px",
  fontSize: "0.9rem",
  color: "#FF6B6B",
};

const footerTextStyle = {
  textAlign: "center",
  marginTop: "1.5rem",
  fontSize: "0.9rem",
  color: "#64748B",
};

const linkStyle = {
  color: "#A78BFA",
  fontWeight: "600",
  textDecoration: "none",
};
