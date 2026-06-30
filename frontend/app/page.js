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
  if (label === "Fake" || label === "Likely Fake") {
    return { text: label === "Likely Fake" ? "Likely Fake" : "Deepfake", color: "#c0392b" };
  }
  return { text: label === "Likely Real" ? "Likely Real" : "Real", color: "#27ae60" };
}

export default function Home() {
  const { user, session, loading: authLoading, signOut } = useAuth();
  const [mode, setMode] = useState("image"); // "image" | "video"
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected);
    if (selected && mode === "image") {
      setPreview(URL.createObjectURL(selected));
    } else {
      setPreview(null);
    }
    setResult(null);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !session || loading) return;

    setLoading(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    const endpoint =
      mode === "video"
        ? "http://localhost:8000/detect-video"
        : "http://localhost:8000/detect";

    try {
      const res = await fetch(endpoint, {
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
      setResult({ ...data, _mode: mode });
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

  const isVideoResult = result?._mode === "video";
  const verdict = result
    ? getVerdict(
        isVideoResult ? result.verdict : result.label,
        isVideoResult ? result.average_confidence : result.confidence
      )
    : null;

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      {/* ── Header ── */}
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

      {/* ── Image / Video toggle ── */}
      <div style={{ marginBottom: "1rem", display: "flex", gap: "0" }}>
        <button
          id="mode-image"
          onClick={() => handleModeChange("image")}
          style={{
            padding: "0.5rem 1.5rem",
            border: "1px solid #ccc",
            borderRadius: "6px 0 0 6px",
            backgroundColor: mode === "image" ? "#2563eb" : "#fff",
            color: mode === "image" ? "#fff" : "#333",
            fontWeight: mode === "image" ? "bold" : "normal",
            cursor: "pointer",
          }}
        >
          🖼️ Image
        </button>
        <button
          id="mode-video"
          onClick={() => handleModeChange("video")}
          style={{
            padding: "0.5rem 1.5rem",
            border: "1px solid #ccc",
            borderLeft: "none",
            borderRadius: "0 6px 6px 0",
            backgroundColor: mode === "video" ? "#2563eb" : "#fff",
            color: mode === "video" ? "#fff" : "#333",
            fontWeight: mode === "video" ? "bold" : "normal",
            cursor: "pointer",
          }}
        >
          🎬 Video
        </button>
      </div>

      {/* ── Upload form ── */}
      <form onSubmit={handleSubmit}>
        <input
          id="file-input"
          type="file"
          accept={mode === "video" ? "video/mp4,video/quicktime,video/webm" : "image/*"}
          onChange={handleFileChange}
        />
        <button
          id="check-btn"
          type="submit"
          disabled={!file || loading}
          style={{ marginLeft: "0.5rem" }}
        >
          {loading
            ? mode === "video"
              ? "Analyzing video…"
              : "Analyzing…"
            : "Check"}
        </button>
      </form>

      {/* ── Loading spinner for video ── */}
      {loading && mode === "video" && (
        <div style={{ marginTop: "1rem", color: "#555" }}>
          <p>⏳ Processing video frames… this may take a minute.</p>
        </div>
      )}

      {/* ═══ IMAGE RESULT ═══ */}
      {result && !isVideoResult && (
        <div id="result" style={{ marginTop: "1.5rem" }}>
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

          <div
            style={{
              display: "flex",
              gap: "1.5rem",
              flexWrap: "wrap",
              alignItems: "flex-start",
            }}
          >
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

      {/* ═══ VIDEO RESULT ═══ */}
      {result && isVideoResult && (
        <div id="video-result" style={{ marginTop: "1.5rem" }}>
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
              <strong>Average Confidence:</strong>{" "}
              {result.average_confidence.toFixed(2)}%
            </p>
          </div>

          <table
            style={{
              borderCollapse: "collapse",
              marginTop: "0.5rem",
              maxWidth: "500px",
            }}
          >
            <tbody>
              <tr>
                <td style={statLabelStyle}>Fake Frames</td>
                <td style={statValueStyle}>{result.fake_frame_percentage}%</td>
              </tr>
              <tr>
                <td style={statLabelStyle}>Frames Checked</td>
                <td style={statValueStyle}>{result.total_frames_checked}</td>
              </tr>
              <tr>
                <td style={statLabelStyle}>Frames w/o Face</td>
                <td style={statValueStyle}>{result.frames_with_no_face}</td>
              </tr>
            </tbody>
          </table>
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

const statLabelStyle = {
  padding: "0.4rem 1rem 0.4rem 0",
  fontWeight: "500",
  color: "#555",
  borderBottom: "1px solid #eee",
};

const statValueStyle = {
  padding: "0.4rem 0",
  fontWeight: "bold",
  borderBottom: "1px solid #eee",
};
