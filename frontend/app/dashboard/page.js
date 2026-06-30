"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import Link from "next/link";

export default function DashboardPage() {
  const { user, session, loading: authLoading } = useAuth();
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // API key state
  const [apiKeys, setApiKeys] = useState([]);
  const [newKey, setNewKey] = useState(null); // raw key shown once
  const [keyLoading, setKeyLoading] = useState(false);
  const [keyError, setKeyError] = useState(null);
  const [keyCopied, setKeyCopied] = useState(false);

  // Fetch scan history
  useEffect(() => {
    if (!user) return;

    const fetchScans = async () => {
      setLoading(true);
      const { data, error } = await supabase
        .from("scans")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false });

      if (error) {
        setError(error.message);
      } else {
        setScans(data);
      }
      setLoading(false);
    };

    fetchScans();
  }, [user]);

  // Fetch API keys
  useEffect(() => {
    if (!session) return;

    const fetchKeys = async () => {
      try {
        const res = await fetch("http://localhost:8000/api-keys", {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setApiKeys(data.keys || []);
        }
      } catch (e) {
        console.error("Failed to fetch API keys:", e);
      }
    };

    fetchKeys();
  }, [session]);

  // Generate new API key
  const handleGenerateKey = async () => {
    if (!session || keyLoading) return;
    setKeyLoading(true);
    setKeyError(null);
    setNewKey(null);
    setKeyCopied(false);

    try {
      const res = await fetch("http://localhost:8000/api-keys/generate", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to generate key");
      }

      const data = await res.json();
      setNewKey(data.raw_key);

      // Add to list with prefix
      setApiKeys((prev) => [
        {
          id: data.id,
          key_prefix: data.key_prefix,
          created_at: data.created_at,
          last_used_at: null,
          is_active: true,
        },
        ...prev,
      ]);
    } catch (e) {
      setKeyError(e.message);
    } finally {
      setKeyLoading(false);
    }
  };

  // Copy key to clipboard
  const handleCopyKey = async () => {
    if (newKey) {
      await navigator.clipboard.writeText(newKey);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 3000);
    }
  };

  // Revoke key
  const handleRevokeKey = async (keyId) => {
    if (!session) return;
    try {
      const res = await fetch(
        `http://localhost:8000/api-keys/revoke?key_id=${keyId}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        }
      );
      if (res.ok) {
        setApiKeys((prev) =>
          prev.map((k) => (k.id === keyId ? { ...k, is_active: false } : k))
        );
      }
    } catch (e) {
      console.error("Failed to revoke key:", e);
    }
  };

  if (authLoading || loading) {
    return (
      <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Dashboard</h1>
        <Link href="/">← Back to Detector</Link>
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* API KEYS SECTION                                          */}
      {/* ═══════════════════════════════════════════════════════════ */}
      <section style={{ marginTop: "2rem", marginBottom: "2.5rem" }}>
        <h2>API Keys</h2>
        <p style={{ color: "#666", fontSize: "0.9rem", marginBottom: "1rem" }}>
          Use API keys to access detection via <code>POST /api/detect</code>{" "}
          with header <code>X-API-Key</code>.
        </p>

        <button
          id="generate-key-btn"
          onClick={handleGenerateKey}
          disabled={keyLoading}
          style={{
            padding: "0.5rem 1rem",
            backgroundColor: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            cursor: keyLoading ? "not-allowed" : "pointer",
            marginBottom: "1rem",
          }}
        >
          {keyLoading ? "Generating…" : "Generate API Key"}
        </button>

        {keyError && (
          <p style={{ color: "red", marginBottom: "0.5rem" }}>
            Error: {keyError}
          </p>
        )}

        {/* New key display (shown once) */}
        {newKey && (
          <div
            id="new-key-display"
            style={{
              padding: "1rem",
              marginBottom: "1rem",
              backgroundColor: "#f0fdf4",
              border: "2px solid #22c55e",
              borderRadius: "8px",
            }}
          >
            <p style={{ fontWeight: "bold", marginBottom: "0.5rem", color: "#166534" }}>
              ✅ API Key Generated
            </p>
            <p style={{ fontSize: "0.85rem", color: "#dc2626", marginBottom: "0.5rem" }}>
              ⚠️ Save this now — you won&apos;t see it again!
            </p>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                id="raw-key-input"
                type="text"
                readOnly
                value={newKey}
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.85rem",
                  padding: "0.4rem 0.6rem",
                  border: "1px solid #ccc",
                  borderRadius: "4px",
                  width: "100%",
                  maxWidth: "500px",
                  backgroundColor: "#fff",
                }}
                onClick={(e) => e.target.select()}
              />
              <button
                onClick={handleCopyKey}
                style={{
                  padding: "0.4rem 0.8rem",
                  border: "1px solid #ccc",
                  borderRadius: "4px",
                  cursor: "pointer",
                  backgroundColor: keyCopied ? "#22c55e" : "#fff",
                  color: keyCopied ? "#fff" : "#333",
                  whiteSpace: "nowrap",
                }}
              >
                {keyCopied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>
        )}

        {/* Existing keys table */}
        {apiKeys.length > 0 && (
          <table
            id="api-keys-table"
            style={{
              width: "100%",
              maxWidth: "700px",
              borderCollapse: "collapse",
            }}
          >
            <thead>
              <tr>
                <th style={thStyle}>Key</th>
                <th style={thStyle}>Created</th>
                <th style={thStyle}>Last Used</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Action</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((k) => (
                <tr key={k.id}>
                  <td style={tdStyle}>
                    <code>{k.key_prefix}</code>
                  </td>
                  <td style={tdStyle}>
                    {new Date(k.created_at).toLocaleDateString()}
                  </td>
                  <td style={tdStyle}>
                    {k.last_used_at
                      ? new Date(k.last_used_at).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        color: k.is_active ? "#22c55e" : "#ef4444",
                        fontWeight: "bold",
                      }}
                    >
                      {k.is_active ? "Active" : "Revoked"}
                    </span>
                  </td>
                  <td style={tdStyle}>
                    {k.is_active && (
                      <button
                        onClick={() => handleRevokeKey(k.id)}
                        style={{
                          padding: "0.2rem 0.6rem",
                          fontSize: "0.8rem",
                          border: "1px solid #ef4444",
                          borderRadius: "4px",
                          color: "#ef4444",
                          backgroundColor: "#fff",
                          cursor: "pointer",
                        }}
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* SCAN HISTORY SECTION                                       */}
      {/* ═══════════════════════════════════════════════════════════ */}
      <section>
        <h2>Scan History</h2>

        {error && <p style={{ color: "red" }}>Error: {error}</p>}

        {scans.length === 0 ? (
          <p>
            No scans yet.{" "}
            <Link href="/">Run your first detection →</Link>
          </p>
        ) : (
          <table
            id="scans-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              marginTop: "1rem",
            }}
          >
            <thead>
              <tr>
                <th style={thStyle}>Filename</th>
                <th style={thStyle}>Label</th>
                <th style={thStyle}>Confidence</th>
                <th style={thStyle}>Date</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((scan) => (
                <tr key={scan.id}>
                  <td style={tdStyle}>{scan.filename}</td>
                  <td style={tdStyle}>{scan.label}</td>
                  <td style={tdStyle}>
                    {(scan.confidence * 100).toFixed(2)}%
                  </td>
                  <td style={tdStyle}>
                    {new Date(scan.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

const thStyle = {
  textAlign: "left",
  borderBottom: "2px solid #ccc",
  padding: "0.5rem",
};

const tdStyle = {
  borderBottom: "1px solid #eee",
  padding: "0.5rem",
};
