"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import styles from "./page.module.css";


/* ─────────────────────────────────────────────────────── */
/*  VERDICT HELPER                                        */
/* ─────────────────────────────────────────────────────── */
function getVerdict(label, confidence) {
  if (confidence < 45) return { text: "Inconclusive", tone: "inconclusive" };
  if (confidence < 65) return { text: "Uncertain", tone: "uncertain" };
  if (label === "Fake" || label === "Likely Fake")
    return { text: "MANIPULATED", tone: "fake" };
  return { text: "AUTHENTIC", tone: "real" };
}

/* ─────────────────────────────────────────────────────── */
/*  SCROLL REVEAL WRAPPER                                 */
/* ─────────────────────────────────────────────────────── */
function Reveal({ children, className = "", visibleClass, as: Tag = "div", ...opts }) {
  const { ref, isVisible } = useScrollReveal(opts);
  return (
    <Tag ref={ref} className={`${className} ${isVisible ? visibleClass : ""}`}>
      {children}
    </Tag>
  );
}

/* ═════════════════════════════════════════════════════════ */
/*  MAIN PAGE                                              */
/* ═════════════════════════════════════════════════════════ */
export default function Home() {
  const { user, session, loading: authLoading, signOut } = useAuth();

  /* Detection state */
  const [mode, setMode] = useState("image");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  /* API key state */
  const [newKey, setNewKey] = useState(null);
  const [keyLoading, setKeyLoading] = useState(false);
  const [keyError, setKeyError] = useState(null);
  const [keyCopied, setKeyCopied] = useState(false);

  /* Architecture SVG connections dynamic mapping */
  const containerRef = useRef(null);
  const node1Ref = useRef(null);
  const node2Ref = useRef(null);
  const node3Ref = useRef(null);
  const [coords, setCoords] = useState({ x1: 0, y1: 0, x2: 0, y2: 0, x3: 0, y3: 0 });

  useEffect(() => {
    const updateCoords = () => {
      if (
        containerRef.current &&
        node1Ref.current &&
        node2Ref.current &&
        node3Ref.current
      ) {
        const containerRect = containerRef.current.getBoundingClientRect();
        const rect1 = node1Ref.current.getBoundingClientRect();
        const rect2 = node2Ref.current.getBoundingClientRect();
        const rect3 = node3Ref.current.getBoundingClientRect();

        setCoords({
          x1: rect1.left - containerRect.left + rect1.width / 2,
          y1: rect1.top - containerRect.top + rect1.height / 2,
          x2: rect2.left - containerRect.left + rect2.width / 2,
          y2: rect2.top - containerRect.top + rect2.height / 2,
          x3: rect3.left - containerRect.left + rect3.width / 2,
          y3: rect3.top - containerRect.top + rect3.height / 2,
        });
      }
    };

    updateCoords();
    window.addEventListener("resize", updateCoords);
    const timer = setTimeout(updateCoords, 500);

    return () => {
      window.removeEventListener("resize", updateCoords);
      clearTimeout(timer);
    };
  }, []);

  const getPath1 = () => {
    const n1 = { x: coords.x1, y: coords.y1 };
    const n2 = { x: coords.x2, y: coords.y2 };
    const isVertical = Math.abs(n1.x - n2.x) < 50;
    const midX = (n1.x + n2.x) / 2;
    const midY = (n1.y + n2.y) / 2;
    return isVertical
      ? `M ${n1.x} ${n1.y} Q ${midX - 40} ${midY} ${n2.x} ${n2.y}`
      : `M ${n1.x} ${n1.y} Q ${midX} ${midY - 40} ${n2.x} ${n2.y}`;
  };

  const getPath2 = () => {
    const n1 = { x: coords.x1, y: coords.y1 };
    const n2 = { x: coords.x2, y: coords.y2 };
    const isVertical = Math.abs(n1.x - n2.x) < 50;
    const midX = (n1.x + n2.x) / 2;
    const midY = (n1.y + n2.y) / 2;
    return isVertical
      ? `M ${n1.x} ${n1.y} Q ${midX + 40} ${midY} ${n2.x} ${n2.y}`
      : `M ${n1.x} ${n1.y} Q ${midX} ${midY + 40} ${n2.x} ${n2.y}`;
  };

  const getPath3 = () => {
    return `M ${coords.x2} ${coords.y2} L ${coords.x3} ${coords.y3}`;
  };


  /* ── Handlers ── */
  const handleModeChange = (newMode) => {
    setMode(newMode);
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  const processFile = (selected) => {
    setFile(selected);
    if (selected && mode === "image") {
      setPreview(URL.createObjectURL(selected));
    } else {
      setPreview(null);
    }
    setResult(null);
    setError(null);
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) processFile(selected);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) processFile(dropped);
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
        headers: { Authorization: `Bearer ${session.access_token}` },
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

  const handleGenerateKey = async () => {
    if (!session || keyLoading) return;
    setKeyLoading(true);
    setKeyError(null);
    setNewKey(null);
    setKeyCopied(false);

    try {
      const res = await fetch("http://localhost:8000/api-keys/generate", {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to generate key");
      }

      const data = await res.json();
      setNewKey(data.raw_key);
    } catch (e) {
      setKeyError(e.message);
    } finally {
      setKeyLoading(false);
    }
  };

  const handleCopyKey = async () => {
    if (newKey) {
      await navigator.clipboard.writeText(newKey);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 3000);
    }
  };

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  /* Loading state */
  if (authLoading) {
    return (
      <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyCenter: "center", background: "#050508" }}>
        <div className={styles.spinner} />
      </main>
    );
  }

  /* Compute verdict */
  const isVideoResult = result?._mode === "video";
  const verdict = result
    ? getVerdict(
        isVideoResult ? result.verdict : result.label,
        isVideoResult ? result.average_confidence : result.confidence
      )
    : null;

  const verdictClass =
    verdict?.tone === "fake" ? styles.verdictFake
    : verdict?.tone === "real" ? styles.verdictReal
    : verdict?.tone === "uncertain" ? styles.verdictUncertain
    : styles.verdictInconclusive;

  const barClass =
    verdict?.tone === "fake" ? styles.confidenceBarDanger
    : verdict?.tone === "real" ? styles.confidenceBarSafe
    : "";

  const confidence = result
    ? isVideoResult ? result.average_confidence : result.confidence
    : 0;

  return (
    <>
      {/* ═══════════════════════════════════════════════════ */}
      {/*  NAVBAR                                            */}
      {/* ═══════════════════════════════════════════════════ */}
      <nav className={styles.navbar}>
        <span className={styles.navBrand}>VERITAS</span>
        <div className={styles.navLinks}>
          <button className={styles.navLink} onClick={() => scrollTo("pipeline")}>
            Analysis
          </button>
          <button className={styles.navLink} onClick={() => scrollTo("architecture")}>
            Architecture
          </button>
          <button className={styles.navLink} onClick={() => scrollTo("api")}>
            API
          </button>
          {user && (
            <>
              <span className={styles.navUser}>{user.email}</span>
              <Link href="/dashboard" className={styles.navBtnGhost}>
                Dashboard
              </Link>
              <button id="logout-btn" className={styles.navBtnGhost} onClick={signOut}>
                Log Out
              </button>
            </>
          )}
        </div>
      </nav>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 1 — HERO                                  */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.hero}>
        <div className={styles.heroBackground}>
          <div className={styles.heroOrb1} />
          <div className={styles.heroOrb2} />
          <div className="grid-dots absolute inset-0 opacity-20" />
        </div>

        <div className={styles.heroContent}>
          <h1 className={`${styles.heroTitle} text-gradient`}>
            See Through
            <br />
            The Lie
          </h1>

          <p className={styles.heroSubtitle}>
            Advanced digital forensics powered by deep ensemble networks. Detect
            synthetic manipulation with clinical precision and sub-second inference.
          </p>

          <div className={styles.heroCtas}>
            <button className={styles.btnPrimary} onClick={() => scrollTo("detect")}>
              Start Detecting
            </button>
            <button className={styles.btnSecondary} onClick={() => scrollTo("api")}>
              View API Docs
            </button>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 2 — STATS RIBBON                          */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.stats}>
        <Reveal className={styles.statsGrid} visibleClass="">
          {[
            { number: "99.97%", label: "Accuracy Rate" },
            { number: "<1s", label: "Inference Time" },
            { number: "12 Fr", label: "Window Analysis" },
            { number: "4+1", label: "Inference Regions" },
          ].map((stat, i) => (
            <Reveal
              key={i}
              className={`${styles.statCard} ${styles.glass} ${styles.glassHover}`}
              visibleClass={styles.statCardVisible}
              threshold={0.1}
            >
              <div className={styles.statNumber}>{stat.number}</div>
              <div className={styles.statLabel}>{stat.label}</div>
            </Reveal>
          ))}
        </Reveal>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 3 — PIPELINE OF TRUTH (BENTO)              */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.pipeline} id="pipeline">
        <h2 className={styles.sectionTitle}>Pipeline of Truth</h2>
        <p className={styles.sectionSubtitle}>
          Every frame is subjected to a five-stage verification protocol to ensure maximum reliability.
        </p>

        <div className={styles.pipelineGrid}>
          {/* Card 1 */}
          <Reveal
            className={`${styles.pipelineCard} ${styles.glass} ${styles.glassHover} ${styles.colSpan2}`}
            visibleClass={styles.pipelineCardVisible}
            threshold={0.1}
          >
            <span className={styles.pipelineStep}>01</span>
            <span className="material-symbols-outlined text-4xl mb-6 text-[#c6bfff] block">upload_file</span>
            <h3 className={styles.pipelineCardTitle}>Secure Upload</h3>
            <p className={styles.pipelineCardDesc}>Encrypted transmission of video assets with automatic metadata extraction.</p>
          </Reveal>

          {/* Card 2 */}
          <Reveal
            className={`${styles.pipelineCard} ${styles.glass} ${styles.glassHover} ${styles.colSpan2}`}
            visibleClass={styles.pipelineCardVisible}
            threshold={0.1}
          >
            <span className={styles.pipelineStep}>02</span>
            <span className="material-symbols-outlined text-4xl mb-6 text-[#c6bfff] block">face</span>
            <h3 className={styles.pipelineCardTitle}>Face Extraction</h3>
            <p className={styles.pipelineCardDesc}>Multi-frame alignment and tracking across varying lighting conditions.</p>
          </Reveal>

          {/* Card 3 (spans 2 rows) */}
          <Reveal
            className={`${styles.pipelineCard} ${styles.glass} ${styles.glassHover} ${styles.colSpan2} ${styles.rowSpan2}`}
            visibleClass={styles.pipelineCardVisible}
            threshold={0.1}
          >
            <div className={styles.ensembleGrad} />
            <div className={styles.pipelineInner}>
              <span className={styles.pipelineStep} style={{ top: "0" }}>03</span>
              <span className="material-symbols-outlined text-4xl mb-6 text-[#c6bfff] block">hub</span>
              <h3 className={styles.pipelineCardTitle} style={{ fontSize: "1.5rem" }}>Ensemble Voting</h3>
              <p className={styles.pipelineCardDesc}>6 disparate deep learning models cross-verify findings to eliminate false positives.</p>
            </div>
          </Reveal>

          {/* Card 4 */}
          <Reveal
            className={`${styles.pipelineCard} ${styles.glass} ${styles.glassHover} ${styles.colSpan2}`}
            visibleClass={styles.pipelineCardVisible}
            threshold={0.1}
          >
            <span className={styles.pipelineStep}>04</span>
            <span className="material-symbols-outlined text-4xl mb-6 text-[#c6bfff] block">query_stats</span>
            <h3 className={styles.pipelineCardTitle}>Deep Analysis</h3>
            <p className={styles.pipelineCardDesc}>Frequency domain inspection and pixel-level noise analysis.</p>
          </Reveal>

          {/* Card 5 */}
          <Reveal
            className={`${styles.pipelineCard} ${styles.glass} ${styles.glassHover} ${styles.colSpan2}`}
            visibleClass={styles.pipelineCardVisible}
            threshold={0.1}
          >
            <span className={styles.pipelineStep}>05</span>
            <span className="material-symbols-outlined text-4xl mb-6 text-[#c6bfff] block">visibility</span>
            <h3 className={styles.pipelineCardTitle}>Heatmap Export</h3>
            <p className={styles.pipelineCardDesc}>Visual evidence provided through Grad-CAM localization maps.</p>
          </Reveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 4 — INTERPRET THE VERDICT                  */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.explainability}>
        <div className={styles.explainGrid}>
          <Reveal className={styles.explainText} visibleClass={styles.explainTextVisible} threshold={0.1}>
            <h2 className={styles.explainTitle}>Interpret the Verdict</h2>
            <p className={styles.explainDesc}>
              Our system doesn't just say &quot;Fake.&quot; It shows you where. Using proprietary Grad-CAM integration, we highlight the specific facial landmarks—eyes, mouth, and skin texture—that exhibit synthetic signatures.
            </p>
            <ul className={styles.featureList}>
              {[
                "Mouth-sync frequency dissonance detection",
                "Corneal reflection anomaly mapping",
                "Blood flow (rPPG) verification",
              ].map((feature, i) => (
                <li key={i} className={styles.featureItem}>
                  <span className={`material-symbols-outlined ${styles.featureCheck}`}>check_circle</span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal className={styles.explainVisual} visibleClass={styles.explainVisualVisible} threshold={0.1}>
            <div className={styles.explainVisualGlow} />
            <div className={styles.glass} style={{ padding: "1rem", borderRadius: "32px" }}>
              <img
                className={styles.heatmapImage}
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuANwJ1CIcGXGdWlic7w80bmzbA6e8iKlog5VM55RNZecY3K0paoPXy0svY0lF2zpAQlySD8U-nH2qHvrSMXTP2JB5QrsKPcMguxjf2dWTY8BTOA0JLy9ccVxnFNGnqxX4wiAzIF_mDJr0gy0zayicn4QFIooK6vNcNdX14OwHb7zXjifgo6yYzPOLzHXXu9-KNil2n56NynEMFpba04q2av7L3lyEFE3vOt5wSXUhjwArFtLgxcU_l5"
                alt="Grad-CAM analysis overview face scan"
              />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 5 — LIVE DETECTOR                         */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.detector} id="detect">
        <div className={styles.detectorHeader}>
          <h2 className={styles.sectionTitle}>Try It Yourself</h2>
          <p className={styles.sectionSubtitle} style={{ margin: "0.25rem auto 1.5rem" }}>
            Experience the sub-second speed of the Veritas core engine.
          </p>
          <div className={styles.modeToggle}>
            <button
              id="mode-image"
              className={`${styles.modeBtn} ${mode === "image" ? styles.modeBtnActive : ""}`}
              onClick={() => handleModeChange("image")}
            >
              🖼️ Image
            </button>
            <button
              id="mode-video"
              className={`${styles.modeBtn} ${mode === "video" ? styles.modeBtnActive : ""}`}
              onClick={() => handleModeChange("video")}
            >
              🎬 Video
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div
            className={`${styles.dropZone} ${styles.dashedBorder} ${styles.glass} ${dragOver ? styles.dropZoneDragOver : ""} ${file ? styles.dropZoneHasFile : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              id="file-input"
              ref={fileInputRef}
              type="file"
              accept={mode === "video" ? "video/mp4,video/quicktime,video/webm" : "image/*"}
              onChange={handleFileChange}
              className={styles.fileInput}
              style={{ display: "none" }}
            />

            {loading && (
              <div className={styles.analyzingOverlay}>
                <div className={styles.scanLine} />
                <div className={styles.spinner} />
                <span className={styles.analyzingText}>
                  {mode === "video" ? "Analyzing neural patterns..." : "Analyzing image..."}
                </span>
              </div>
            )}

            {!file ? (
              <>
                <span className={`material-symbols-outlined ${styles.dropIcon}`}>upload</span>
                <p className={styles.dropText}>Drop a video or image here</p>
                <p className={styles.dropSubtext}>
                  Supported formats: {mode === "video" ? "MP4, MOV, WEBM" : "JPG, PNG, WEBP"}
                </p>
              </>
            ) : (
              <div className={styles.previewContainer}>
                {preview && (
                  <img className={styles.previewImage} src={preview} alt="Preview" />
                )}
                <span className={styles.fileName}>{file.name}</span>
              </div>
            )}
          </div>

          <button
            id="check-btn"
            type="submit"
            disabled={!file || loading}
            className={styles.analyzeBtn}
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {/* ── Result Card ── */}
        {result && !isVideoResult && (
          <div id="result" className={`${styles.resultCard} ${styles.glass}`}>
            {result.warning && (
              <div className={styles.warningBanner}>
                <span className="material-symbols-outlined styles.warningIcon">warning</span>
                <span>{result.warning}</span>
              </div>
            )}

            {result.low_agreement && (
              <div className={styles.warningBanner}>
                <span className="material-symbols-outlined styles.warningIcon">warning</span>
                <span>Models disagree across face regions — upload a clearer image</span>
              </div>
            )}

            <div className={styles.verdictRow}>
              <span className={styles.verdictLabel}>Engine Verdict</span>
              <span className={`${styles.verdictBadge} ${verdictClass}`}>
                {verdict.text}
              </span>
            </div>

            <div className={styles.confidenceSection}>
              <div className={styles.confidenceLabel}>
                <span>Confidence Score</span>
                <span style={{ fontWeight: "bold" }}>{confidence.toFixed(1)}%</span>
              </div>
              <div className={styles.confidenceBarTrack}>
                <div
                  className={`${styles.confidenceBarFill} ${barClass}`}
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>

            <div className={styles.resultImages}>
              {preview && (
                <div className={styles.resultImageCard}>
                  <p className={styles.resultImageLabel}>Original</p>
                  <img id="original-image" className={styles.resultImg} src={preview} alt="Uploaded" />
                </div>
              )}
              {result.heatmap && (
                <div className={styles.resultImageCard}>
                  <p className={styles.resultImageLabel}>Grad-CAM Heatmap</p>
                  <img
                    id="heatmap-image"
                    className={styles.resultImg}
                    src={`data:image/png;base64,${result.heatmap}`}
                    alt="Grad-CAM overlay"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Video Result ── */}
        {result && isVideoResult && (
          <div id="video-result" className={`${styles.resultCard} ${styles.glass}`}>
            <div className={styles.verdictRow}>
              <span className={styles.verdictLabel}>Engine Verdict</span>
              <span className={`${styles.verdictBadge} ${verdictClass}`}>
                {verdict.text}
              </span>
            </div>

            <div className={styles.confidenceSection}>
              <div className={styles.confidenceLabel}>
                <span>Average Confidence Score</span>
                <span style={{ fontWeight: "bold" }}>{confidence.toFixed(1)}%</span>
              </div>
              <div className={styles.confidenceBarTrack}>
                <div
                  className={`${styles.confidenceBarFill} ${barClass}`}
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>

            <div className={styles.videoStats}>
              <div className={styles.videoStatCard}>
                <div className={styles.videoStatValue}>{result.fake_frame_percentage}%</div>
                <div className={styles.videoStatLabel}>Fake Frames</div>
              </div>
              <div className={styles.videoStatCard}>
                <div className={styles.videoStatValue}>{result.total_frames_checked}</div>
                <div className={styles.videoStatLabel}>Frames Checked</div>
              </div>
              <div className={styles.videoStatCard}>
                <div className={styles.videoStatValue}>{result.frames_with_no_face}</div>
                <div className={styles.videoStatLabel}>No Face Detected</div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className={styles.errorBanner}>
            <span className="material-symbols-outlined">error</span>
            <span>Error: {error}</span>
          </div>
        )}
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 6 — HARDENED INFRASTRUCTURE (ARCHITECTURE) */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.architecture} id="architecture">
        <div className={styles.archContainer}>
          <h2 className={styles.sectionTitle} style={{ textAlign: "center", marginBottom: "5rem" }}>
            Hardened Infrastructure
          </h2>

          <div ref={containerRef} className={styles.archGrid}>
            {/* SVG Connections */}
            <svg className={styles.svgConnections} preserveAspectRatio="none">
              <path d={getPath1()} fill="none" stroke="#c6bfff" strokeDasharray="8 8" strokeWidth="2"></path>
              <path d={getPath2()} fill="none" stroke="#c6bfff" strokeDasharray="8 8" strokeWidth="2"></path>
              <path d={getPath3()} fill="none" stroke="#c6bfff" strokeDasharray="8 8" strokeWidth="2"></path>
            </svg>

            {/* Front End */}
            <Reveal
              className={styles.archCard}
              visibleClass={styles.archCardVisible}
              threshold={0.1}
            >
              <div ref={node1Ref} className={`${styles.archIconWrapper} ${styles.glass} ${styles.nodePulse}`} style={{ borderColor: "rgba(198, 191, 255, 0.3)" }}>
                <span className={styles.archIconText}>Next.js</span>
              </div>
              <h4 className={styles.archName}>Edge Delivery</h4>
              <p className={styles.archRole}>Vercel Global Edge</p>
            </Reveal>

            {/* API / Core */}
            <Reveal
              className={styles.archCard}
              visibleClass={styles.archCardVisible}
              threshold={0.1}
            >
              <div ref={node2Ref} className={`${styles.archIconWrapper} ${styles.archIconWrapperCenter} ${styles.glass}`}>
                <span className={styles.archIconTextCenter}>EfficientNet</span>
              </div>
              <h4 className={styles.archName}>Inference Engine</h4>
              <p className={styles.archRole}>FastAPI + Torch</p>
            </Reveal>

            {/* Data */}
            <Reveal
              className={styles.archCard}
              visibleClass={styles.archCardVisible}
              threshold={0.1}
            >
              <div ref={node3Ref} className={`${styles.archIconWrapper} ${styles.glass} ${styles.nodePulse}`} style={{ borderColor: "rgba(198, 191, 255, 0.3)" }}>
                <span className={styles.archIconText}>Supabase</span>
              </div>
              <h4 className={styles.archName}>State Layer</h4>
              <p className={styles.archRole}>PostgreSQL Realtime</p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 7 — DEVELOPER API                         */}
      {/* ═══════════════════════════════════════════════════ */}
      <section className={styles.api} id="api">
        <div className={styles.apiGrid}>
          {/* Info */}
          <Reveal className={styles.apiInfo} visibleClass="" threshold={0.1}>
            <h2 className={styles.sectionTitle}>Build on Truth</h2>
            <p className={styles.sectionSubtitle} style={{ marginBottom: "3rem" }}>
              Integrate forensic-grade detection directly into your UGC platform, content moderation tool, or security suite.
            </p>

            {/* Key Generation */}
            <div className={`${styles.apiKeySection} ${styles.glass}`}>
              <h4 className={styles.apiKeyTitle}>Generate API Key</h4>
              <div className={styles.apiKeyRow}>
                <div className={styles.apiKeyBox}>
                  {newKey ? newKey : "sk_veritas_prod_••••••••••••"}
                </div>
                <button
                  id="generate-key-btn"
                  className={`${styles.apiKeyBtn} ${keyCopied ? styles.copyBtnCopied : ""}`}
                  onClick={newKey ? handleCopyKey : handleGenerateKey}
                  disabled={keyLoading}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>
                    {keyCopied ? "check" : newKey ? "content_copy" : "vpn_key"}
                  </span>
                  {keyCopied ? "Copied" : newKey ? "Copy" : keyLoading ? "Creating…" : "Generate"}
                </button>
              </div>

              {keyError && (
                <div className={styles.errorBanner} style={{ marginTop: "0.5rem" }}>
                  <span>⚠️</span> {keyError}
                </div>
              )}

              {newKey && (
                <p className={styles.saveWarning}>⚠️ Save this now — you won&apos;t see it again!</p>
              )}
              <p className={styles.apiKeyLimits}>Don&apos;t share this key. API limits: 5 scans/day on Free Tier.</p>
            </div>
          </Reveal>

          {/* Code block */}
          <Reveal className={styles.codeBlock} visibleClass="" threshold={0.1}>
            <div className={styles.codeHeader}>
              <span className={`${styles.codeDot} ${styles.codeDotRed}`} />
              <span className={`${styles.codeDot} ${styles.codeDotYellow}`} />
              <span className={`${styles.codeDot} ${styles.codeDotGreen}`} />
              <span className={styles.codeTitle}>curl_detect.sh</span>
            </div>
            <div className={styles.codeBody}>
              <pre>
                <span className={styles.codeComment}># Analyze remote media asset</span>{"\n"}
                <span className={styles.codeKeyword}>curl</span> -X POST <span className={styles.codeString}>&quot;http://localhost:8000/api/detect&quot;</span> \{"\n"}
                {"  "}-H <span className={styles.codeString}>&quot;X-API-Key: $VERITAS_KEY&quot;</span> \{"\n"}
                {"  "}-F <span className={styles.codeString}>&quot;file=@suspect_photo.jpg&quot;</span>{"\n"}
                {"\n"}
                <span className={styles.codeComment}># Result Response</span>{"\n"}
                {"{"}{"\n"}
                {"  "}<span className={styles.codeKeyword}>&quot;label&quot;</span>: <span className={styles.codeString}>&quot;Fake&quot;</span>,{"\n"}
                {"  "}<span className={styles.codeKeyword}>&quot;confidence&quot;</span>: 99.97,{"\n"}
                {"  "}<span className={styles.codeKeyword}>&quot;low_agreement&quot;</span>: <span className={styles.codeKeyword}>false</span>,{"\n"}
                {"  "}<span className={styles.codeKeyword}>&quot;regions&quot;</span>: [<span className={styles.codeString}>&quot;periorbital&quot;</span>, <span className={styles.codeString}>&quot;nasolabial&quot;</span>]{"\n"}
                {"}"}{"\n"}
              </pre>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════ */}
      {/*  SECTION 8 — FOOTER                                */}
      {/* ═══════════════════════════════════════════════════ */}
      <footer className={styles.footer}>
        <div className={styles.footerContent}>
          <div className={styles.footerTop}>
            <div className={styles.footerBrandSection}>
              <div className={styles.footerBrand}>VERITAS</div>
              <p className={styles.footerDesc}>
                Precision in Truth. Global standard for synthetic media detection and forensics.
              </p>
              <div className={styles.socialRow}>
                <a className={`${styles.socialIcon} ${styles.glass}`} href="#">
                  <svg className={styles.socialIconSvg} viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.041-1.416-4.041-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"></path></svg>
                </a>
              </div>
            </div>

            <div className={styles.footerLinksGrid}>
              <div className={styles.footerLinksColumn}>
                <h5 className={styles.footerColumnTitle}>Platform</h5>
                <a className={styles.footerLink} href="#">Pricing</a>
                <a className={styles.footerLink} href="#">Enterprise</a>
                <a className={styles.footerLink} href="#">Infrastructure</a>
              </div>
              <div className={styles.footerLinksColumn}>
                <h5 className={styles.footerColumnTitle}>Company</h5>
                <a className={styles.footerLink} href="#">About</a>
                <a className={styles.footerLink} href="#">Security</a>
                <a className={styles.footerLink} href="#">Contact</a>
              </div>
              <div className={styles.footerLinksColumn}>
                <h5 className={styles.footerColumnTitle}>Legal</h5>
                <a className={styles.footerLink} href="#">Privacy Policy</a>
                <a className={styles.footerLink} href="#">Terms of Service</a>
              </div>
            </div>
          </div>

          <div className={styles.footerBottom}>
            <div>© {new Date().getFullYear()} Veritas Forensics. All rights reserved. Precision in Truth.</div>
            <div className={styles.footerBadges}>
              <span>SOC2 Compliant</span>
              <span>GDPR Ready</span>
              <span>HIPAA Secure</span>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
