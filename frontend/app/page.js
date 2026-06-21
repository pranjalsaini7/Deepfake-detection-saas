"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";

export default function Home() {
  const { user, session, loading: authLoading, signOut } = useAuth();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !session) return;

    setLoading(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/detect", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Detection failed");
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Deepfake Detector</h1>
        <div>
          <span style={{ marginRight: "1rem" }}>{user?.email}</span>
          <Link href="/dashboard" style={{ marginRight: "1rem" }}>Dashboard</Link>
          <button id="logout-btn" onClick={signOut}>Log Out</button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <input
          id="file-input"
          type="file"
          accept="image/*"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button id="check-btn" type="submit" disabled={!file || loading}>
          {loading ? "Checking…" : "Check"}
        </button>
      </form>

      {result && (
        <div id="result" style={{ marginTop: "1rem" }}>
          <p>
            <strong>Label:</strong> {result.label}
          </p>
          <p>
            <strong>Confidence:</strong> {(result.confidence * 100).toFixed(2)}%
          </p>
        </div>
      )}

      {error && (
        <p id="error" style={{ color: "red", marginTop: "1rem" }}>
          Error: {error}
        </p>
      )}
    </main>
  );
}
