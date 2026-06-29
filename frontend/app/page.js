"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";

/**
 * Determine verdict label and color based on confidence + model label.
 */
function getVerdict(label, confidence) {
  if (confidence < 45) {
    return { text: "Inconclusive", color: "#95a5a6" };
  }
  if (confidence < 65) {
    return { text: "Uncertain", color: "#e67e22" };
  }
  if (label === "Fake") {
    return { text: "Deepfake", color: "#c0392b" };
  }
  return { text: "Real", color: "#27ae60" };
}

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

  const verdict = result ? getVerdict(result.label, result.confidence) : null;

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Deepfake Detector</h1>
        <div>
          <span style={{ marginRight: "1rem" }}>{user?.email}</span>
          <Link href="/dashboard" style={{ marginRight: "1rem" }}>
            Dashboard
          </Link>
          <button id="logout-btn" onClick={signOut}>
            Log Out
          </button>
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
          {/* ── Warning banner (no face detected) ── */}
          {result.warning && (
            <div
              id="warning-banner"
              style={{
                padding: "0.75rem 1rem",
                marginBottom: "1rem",
                backgroundColor: "#fff3cd",
                border: "1px solid #ffc107",
                borderRadius: "8px",
                color: "#856404",
                fontWeight: "500",
              }}
            >
              ⚠️ {result.warning}
            </div>
          )}

          {/* ── Low agreement banner ── */}
          {result.low_agreement && (
            <div
              id="agreement-banner"
              style={{
                padding: "0.75rem 1rem",
                marginBottom: "1rem",
                backgroundColor: "#fff8e1",
                border: "1px solid #ffca28",
                borderRadius: "8px",
                color: "#6d4c00",
                fontWeight: "500",
              }}
            >
              ⚠️ Models disagree across face regions — upload a clearer image
            </div>
          )}

          {/* ── Verdict + confidence ── */}
          <div style={{ marginBottom: "1rem" }}>
            <p>
              <strong>Verdict:</strong>{" "}
              <span
                style={{
                  color: verdict.color,
                  fontWeight: "bold",
                  fontSize: "1.4rem",
                }}
              >
                {verdict.text}
              </span>
            </p>
            <p>
              <strong>Confidence:</strong> {result.confidence.toFixed(2)}%
            </p>
          </div>

          {/* ── Side-by-side: Original + Heatmap ── */}
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
                <h3 style={{ marginBottom: "0.5rem" }}>Grad-CAM Heatmap</h3>
                <img
                  id="heatmap-image"
                  src={`data:image/png;base64,${result.heatmap}`}
                  alt="Grad-CAM heatmap overlay"
                  style={{
                    maxWidth: "400px",
                    maxHeight: "400px",
                    border: result.warning
                      ? "3px solid #e67e22"
                      : "2px solid #ddd",
                    borderRadius: "8px",
                  }}
                />
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "#666",
                    marginTop: "0.25rem",
                    maxWidth: "400px",
                  }}
                >
                  Red/yellow = regions that influenced the verdict most
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
