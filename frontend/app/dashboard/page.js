"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import Link from "next/link";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  if (authLoading || loading) {
    return (
      <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Scan History</h1>
        <Link href="/">← Back to Detector</Link>
      </div>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {scans.length === 0 ? (
        <p>No scans yet. <Link href="/">Run your first detection →</Link></p>
      ) : (
        <table id="scans-table" style={{ width: "100%", borderCollapse: "collapse", marginTop: "1rem" }}>
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
                <td style={tdStyle}>{(scan.confidence * 100).toFixed(2)}%</td>
                <td style={tdStyle}>{new Date(scan.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
