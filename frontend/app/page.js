"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";

export default function Home() {
  const { user, session, loading: authLoading, signOut } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected);
    if (selected) {
      setPreview(URL.createObjectURL(selected));
    } else {
      setPreview(null);
    }
    setResult(null);
    setError(null);
  };

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
          onChange={handleFileChange}
        />
        <button id="check-btn" type="submit" disabled={!file || loading}>
          {loading ? "Analyzing…" : "Check"}
        </button>
      </form>

      {result && (
        <div id="result" style={{ marginTop: "1.5rem" }}>
          <div style={{ marginBottom: "1rem" }}>
            <p>
              <strong>Verdict:</strong>{" "}
              <span
                style={{
                  color: result.label === "Deepfake" ? "#c0392b" : "#27ae60",
                  fontWeight: "bold",
                  fontSize: "1.2rem",
                }}
              >
                {result.label}
              </span>
            </p>
            <p>
              <strong>Confidence:</strong> {(result.confidence * 100).toFixed(2)}%
            </p>
          </div>

          <div
            style={{
              display: "flex",
              gap: "1.5rem",
              flexWrap: "wrap",
              alignItems: "flex-start",
            }}
          >
            {/* Original image */}
            {preview && (
              <div>
                <h3 style={{ marginBottom: "0.5rem" }}>Original</h3>
                <img
                  id="original-image"
                  src={preview}
                  alt="Uploaded image"
                  style={{
                    maxWidth: "400px",
                    maxHeight: "400px",
                    border: "2px solid #ddd",
                    borderRadius: "8px",
                  }}
                />
              </div>
            )}

            {/* Heatmap overlay */}
            {result.heatmap && (
              <div>
                <h3 style={{ marginBottom: "0.5rem" }}>Attention Heatmap</h3>
                <img
                  id="heatmap-image"
                  src={`data:image/jpeg;base64,${result.heatmap}`}
                  alt="Attention heatmap overlay"
                  style={{
                    maxWidth: "400px",
                    maxHeight: "400px",
                    border: "2px solid #ddd",
                    borderRadius: "8px",
                  }}
                />
                <p style={{ fontSize: "0.85rem", color: "#666", marginTop: "0.25rem" }}>
                  Warm areas = regions the model focused on
                </p>
              </div>
            )}
          </div>
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
