import React, { useEffect, useMemo, useRef, useState } from "react";

const API = "http://localhost:8000";

function clamp01(x) {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function pct(x) {
  return Math.round(clamp01(x) * 100);
}

function badgeForTrust(trust, verdict) {
  const t = clamp01(trust);

  if (verdict === "not_registered") {
    return { label: "Not Registered", tone: "neutral" };
  }
  if (t >= 0.9 || verdict === "likely_real") {
    return { label: "Likely Real", tone: "good" };
  }
  if (t >= 0.6 || verdict === "uncertain") {
    return { label: "Uncertain", tone: "warn" };
  }
  return { label: "Likely AI / Manipulated", tone: "bad" };
}

function ToneBadge({ tone, children }) {
  const styles = {
    good: {
      background: "rgba(16,185,129,0.12)",
      color: "#065f46",
      border: "1px solid rgba(16,185,129,0.35)"
    },
    warn: {
      background: "rgba(245,158,11,0.14)",
      color: "#7a4b00",
      border: "1px solid rgba(245,158,11,0.35)"
    },
    bad: {
      background: "rgba(239,68,68,0.12)",
      color: "#7f1d1d",
      border: "1px solid rgba(239,68,68,0.32)"
    },
    neutral: {
      background: "rgba(255,255,255,0.55)",
      color: "#111827",
      border: "1px solid rgba(229,231,235,0.9)"
    }
  };

  const s = styles[tone] || styles.neutral;

  return (
    <span
      style={{
        ...s,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 10px",
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 800,
        whiteSpace: "nowrap",
        backdropFilter: "blur(8px)"
      }}
    >
      {children}
    </span>
  );
}

function ProgressRow({ label, value, sublabel }) {
  const p = pct(value);

  return (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 13,
          marginBottom: 6
        }}
      >
        <div style={{ fontWeight: 800 }}>{label}</div>
        <div style={{ opacity: 0.75 }}>{p}%</div>
      </div>

      <div
        style={{
          height: 10,
          background: "rgba(148,163,184,0.22)",
          borderRadius: 999,
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: `${p}%`,
            height: "100%",
            background: "#111827",
            transition: "width 450ms ease"
          }}
        />
      </div>

      {sublabel ? (
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>{sublabel}</div>
      ) : null}
    </div>
  );
}

function Toast({ toast, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 2200);
    return () => clearTimeout(t);
  }, [onClose]);

  const toneStyles = {
    good: {
      border: "1px solid rgba(16,185,129,0.35)",
      background: "rgba(255,255,255,0.9)"
    },
    warn: {
      border: "1px solid rgba(245,158,11,0.35)",
      background: "rgba(255,255,255,0.9)"
    },
    bad: {
      border: "1px solid rgba(239,68,68,0.32)",
      background: "rgba(255,255,255,0.9)"
    },
    neutral: {
      border: "1px solid rgba(229,231,235,0.9)",
      background: "rgba(255,255,255,0.9)"
    }
  };

  return (
    <div
      style={{
        ...toneStyles[toast.tone || "neutral"],
        padding: "10px 12px",
        borderRadius: 14,
        boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
        backdropFilter: "blur(10px)",
        display: "flex",
        gap: 10,
        alignItems: "center",
        animation: "toastIn 220ms ease both"
      }}
    >
      <div style={{ fontWeight: 900, fontSize: 13 }}>{toast.title}</div>
      <div style={{ fontSize: 13, opacity: 0.75 }}>{toast.msg}</div>
      <button
        onClick={onClose}
        style={{
          marginLeft: 8,
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: 16,
          opacity: 0.6
        }}
        aria-label="close toast"
      >
        ×
      </button>
    </div>
  );
}

function CopyLine({ label, value, pushToast }) {
  const canCopy = value && typeof value === "string" && value.length > 0;

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(value);
      pushToast({ tone: "good", title: "Copied", msg: label });
    } catch {
      pushToast({
        tone: "bad",
        title: "Copy failed",
        msg: "Browser permission blocked it."
      });
    }
  }

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10 }}>
      <div style={{ width: 150, fontSize: 13, opacity: 0.75 }}>{label}</div>
      <code
        style={{
          flex: 1,
          fontSize: 12,
          background: "rgba(255,255,255,0.7)",
          border: "1px solid rgba(229,231,235,0.9)",
          padding: "6px 8px",
          borderRadius: 10,
          overflowX: "auto",
          backdropFilter: "blur(10px)"
        }}
      >
        {value || "-"}
      </code>
      <button
        onClick={onCopy}
        disabled={!canCopy}
        style={{
          padding: "8px 10px",
          borderRadius: 10,
          border: "1px solid rgba(229,231,235,0.9)",
          background: canCopy ? "rgba(255,255,255,0.9)" : "rgba(243,244,246,0.9)",
          cursor: canCopy ? "pointer" : "not-allowed",
          fontWeight: 800
        }}
      >
        Copy
      </button>
    </div>
  );
}

export default function App() {
  const inputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const [toast, setToast] = useState(null);
  function pushToast(t) {
    setToast({ ...t, id: Date.now() });
  }

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyTab, setHistoryTab] = useState("analyses");
  const [analyses, setAnalyses] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  async function refreshHistory() {
    setHistoryLoading(true);
    try {
      const [aRes, rRes] = await Promise.all([
        fetch(`${API}/history/analyses?limit=50`),
        fetch(`${API}/history/registrations?limit=50`)
      ]);

      const aJson = await aRes.json();
      const rJson = await rRes.json();

      setAnalyses(aJson.items || []);
      setRegistrations(rJson.items || []);
    } catch {
      pushToast({ tone: "bad", title: "History error", msg: "Could not load history" });
    } finally {
      setHistoryLoading(false);
    }
  }

  function setPickedFile(f) {
    setFile(f);
    setResult(null);
    setError("");

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    if (f) {
      setPreviewUrl(URL.createObjectURL(f));
    } else {
      setPreviewUrl("");
    }
  }

  useEffect(() => {
    function onPaste(e) {
      const items = e.clipboardData?.items || [];
      for (const it of items) {
        if (it.type.startsWith("image/")) {
          const blob = it.getAsFile();
          if (blob) {
            const pasted = new File([blob], `pasted-${Date.now()}.png`, {
              type: blob.type
            });
            setPickedFile(pasted);
            pushToast({ tone: "good", title: "Pasted", msg: "Image from clipboard" });
          }
        }
      }
    }

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [previewUrl]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const metrics = useMemo(() => {
    if (!result) return null;

    const trust = result?.result?.trust ?? 0;
    const verdict = result?.result?.verdict ?? "unknown";
    const phSim = result?.best_match?.phash_similarity ?? 0;

    return {
      trust: clamp01(trust),
      verdict,
      phSim: clamp01(phSim),
      sha: result?.content_sha256 || "",
      phash: result?.phash || "",
      bestShaPhash: result?.best_match?.content_sha256 || "",
      tags: result?.tags || []
    };
  }, [result]);

  const badge = metrics
    ? badgeForTrust(metrics.trust, metrics.verdict)
    : { label: "No result yet", tone: "neutral" };

  async function callApi(path) {
    if (!file) return;

    setBusy(true);
    setError("");

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${API}${path}`, { method: "POST", body: fd });
      const data = await res.json();

      if (!res.ok) {
        setError(data?.detail || "Request failed");
        setResult(null);
        pushToast({
          tone: "bad",
          title: "Request failed",
          msg: data?.detail || "Try again"
        });
      } else {
        setResult(data);
        pushToast({
          tone: "good",
          title: path === "/register" ? "Registered" : "Analyzed",
          msg: "Result updated"
        });

        if (historyOpen) {
          refreshHistory();
        }
      }
    } catch {
      setError("Network error (backend not reachable)");
      setResult(null);
      pushToast({
        tone: "bad",
        title: "Network error",
        msg: "Backend not reachable"
      });
    } finally {
      setBusy(false);
    }
  }

  function onDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function onDragLeave(e) {
    e.preventDefault();
    setIsDragging(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) {
      setPickedFile(f);
      pushToast({ tone: "good", title: "Selected", msg: f.name });
    }
  }

  return (
    <div
      style={{
        fontFamily: "system-ui",
        minHeight: "100vh",
        padding: 24,
        background:
          "radial-gradient(1200px 600px at 10% 0%, rgba(59,130,246,0.22), transparent 60%)," +
          "radial-gradient(1000px 600px at 90% 10%, rgba(236,72,153,0.20), transparent 55%)," +
          "radial-gradient(1000px 700px at 50% 100%, rgba(34,197,94,0.18), transparent 60%)," +
          "linear-gradient(180deg, #fbfbfc, #f3f5f9)"
      }}
    >
      <style>{`
        @keyframes toastIn {
          from { transform: translateY(-6px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>

      <div style={{ position: "fixed", top: 18, right: 18, zIndex: 60 }}>
        {toast ? <Toast toast={toast} onClose={() => setToast(null)} /> : null}
      </div>

      <div style={{ maxWidth: 1150, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 16
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: 44, letterSpacing: "-0.03em" }}>TrueSight</h1>
            <div style={{ marginTop: 6, opacity: 0.75 }}>
              Sprint 2 MVP • Hybrid Image Verification • <b>pHash + CLIP + History</b>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              flexWrap: "wrap",
              justifyContent: "flex-end"
            }}
          >
            <ToneBadge tone={badge.tone}>{badge.label}</ToneBadge>

            <button
              onClick={() => {
                const next = !historyOpen;
                setHistoryOpen(next);
                if (next) refreshHistory();
              }}
              style={{
                border: "1px solid rgba(229,231,235,0.9)",
                background: "rgba(255,255,255,0.75)",
                borderRadius: 999,
                padding: "7px 12px",
                cursor: "pointer",
                fontWeight: 900,
                backdropFilter: "blur(10px)"
              }}
            >
              {historyOpen ? "Hide history" : "History"}
            </button>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1.35fr",
            gap: 16,
            marginTop: 18
          }}
        >
          <div
            style={{
              background: "rgba(255,255,255,0.78)",
              border: "1px solid rgba(229,231,235,0.9)",
              borderRadius: 18,
              padding: 16,
              backdropFilter: "blur(14px)",
              boxShadow: "0 20px 50px rgba(0,0,0,0.06)"
            }}
          >
            <div style={{ fontWeight: 900, marginBottom: 10 }}>Upload</div>

            <div
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => inputRef.current?.click()}
              style={{
                borderRadius: 18,
                padding: 14,
                border: isDragging
                  ? "2px solid #111827"
                  : "2px dashed rgba(209,213,219,0.95)",
                background: isDragging
                  ? "rgba(241,245,255,0.75)"
                  : "rgba(247,248,251,0.7)",
                cursor: "pointer",
                transition: "all 150ms ease"
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 12
                }}
              >
                <div style={{ fontWeight: 900 }}>Drag & Drop</div>
                <div style={{ fontSize: 12, opacity: 0.75 }}>
                  or click to browse • supports Ctrl/Cmd+V paste
                </div>
              </div>

              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => setPickedFile(e.target.files?.[0] || null)}
              />

              {previewUrl ? (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Preview</div>
                  <img
                    src={previewUrl}
                    alt="preview"
                    style={{
                      width: "100%",
                      maxHeight: 340,
                      objectFit: "contain",
                      borderRadius: 14,
                      border: "1px solid rgba(238,242,247,0.9)",
                      background: "rgba(255,255,255,0.9)"
                    }}
                  />
                </div>
              ) : (
                <div style={{ marginTop: 12, fontSize: 13, opacity: 0.75 }}>
                  Drop a JPG/PNG here, or paste an image from clipboard.
                </div>
              )}
            </div>

            <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
              <button
                disabled={!file || busy}
                onClick={() => callApi("/register")}
                style={{
                  flex: 1,
                  padding: "12px 14px",
                  borderRadius: 14,
                  border: "1px solid rgba(229,231,235,0.9)",
                  background: !file || busy
                    ? "rgba(243,244,246,0.9)"
                    : "rgba(255,255,255,0.9)",
                  cursor: !file || busy ? "not-allowed" : "pointer",
                  fontWeight: 900
                }}
              >
                {busy ? "Working..." : "Register"}
              </button>

              <button
                disabled={!file || busy}
                onClick={() => callApi("/analyze")}
                style={{
                  flex: 1,
                  padding: "12px 14px",
                  borderRadius: 14,
                  border: "1px solid rgba(229,231,235,0.9)",
                  background: !file || busy ? "rgba(243,244,246,0.9)" : "#111827",
                  color: !file || busy ? "#6b7280" : "white",
                  cursor: !file || busy ? "not-allowed" : "pointer",
                  fontWeight: 900
                }}
              >
                {busy ? "Working..." : "Analyze"}
              </button>
            </div>

            {error ? (
              <div
                style={{
                  marginTop: 12,
                  padding: 12,
                  borderRadius: 14,
                  border: "1px solid rgba(239,68,68,0.35)",
                  background: "rgba(255,236,236,0.8)",
                  color: "#7f1d1d"
                }}
              >
                <b>Error:</b> {error}
              </div>
            ) : null}
          </div>

          <div
            style={{
              background: "rgba(255,255,255,0.78)",
              border: "1px solid rgba(229,231,235,0.9)",
              borderRadius: 18,
              padding: 16,
              backdropFilter: "blur(14px)",
              boxShadow: "0 20px 50px rgba(0,0,0,0.06)"
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 10
              }}
            >
              <div style={{ fontWeight: 900 }}>Result</div>
              {metrics ? (
                <ToneBadge tone={badge.tone}>
                  Trust: {pct(metrics.trust)}% • {badge.label}
                </ToneBadge>
              ) : (
                <ToneBadge tone="neutral">Waiting for output…</ToneBadge>
              )}
            </div>

            {!metrics ? (
              <div
                style={{
                  marginTop: 12,
                  padding: 14,
                  borderRadius: 14,
                  background: "rgba(246,247,249,0.75)",
                  border: "1px dashed rgba(209,213,219,0.95)",
                  opacity: 0.92
                }}
              >
                Upload an image and run <b>Register</b> or <b>Analyze</b>.
              </div>
            ) : (
              <div style={{ marginTop: 14 }}>
                <ProgressRow
                  label="pHash similarity"
                  value={metrics.phSim}
                  sublabel="Similarity based on perceptual hashing."
                />
                <ProgressRow
                  label="Trust score"
                  value={metrics.trust}
                  sublabel="Basic Sprint 1 trust result using pHash verification."
                />

                <div style={{ marginTop: 16, fontWeight: 900, marginBottom: 10 }}>
                  Tags
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                  {(metrics.tags || []).map((tag) => {
                    const b = badgeForTrust(metrics.trust, tag);
                    return (
                      <ToneBadge key={tag} tone={b.tone}>
                        {tag}
                      </ToneBadge>
                    );
                  })}
                </div>

                <div style={{ marginTop: 16, fontWeight: 900, marginBottom: 10 }}>
                  Identifiers (copy)
                </div>
                <CopyLine label="Content SHA-256" value={metrics.sha} pushToast={pushToast} />
                <CopyLine label="pHash" value={metrics.phash} pushToast={pushToast} />
                <CopyLine
                  label="Best match (pHash)"
                  value={metrics.bestShaPhash}
                  pushToast={pushToast}
                />
              </div>
            )}

            {historyOpen ? (
              <div
                style={{
                  marginTop: 18,
                  paddingTop: 14,
                  borderTop: "1px solid rgba(229,231,235,0.9)"
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10
                  }}
                >
                  <div style={{ fontWeight: 900 }}>History</div>

                  <button
                    onClick={refreshHistory}
                    disabled={historyLoading}
                    style={{
                      border: "1px solid rgba(229,231,235,0.9)",
                      background: "rgba(255,255,255,0.9)",
                      borderRadius: 10,
                      padding: "6px 10px",
                      cursor: historyLoading ? "not-allowed" : "pointer",
                      fontWeight: 800,
                      opacity: historyLoading ? 0.6 : 1
                    }}
                  >
                    {historyLoading ? "Refreshing..." : "Refresh"}
                  </button>
                </div>

                <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
                  <button
                    onClick={() => setHistoryTab("analyses")}
                    style={{
                      border: "1px solid rgba(229,231,235,0.9)",
                      background: historyTab === "analyses" ? "#111827" : "rgba(255,255,255,0.85)",
                      color: historyTab === "analyses" ? "white" : "#111827",
                      borderRadius: 999,
                      padding: "7px 12px",
                      cursor: "pointer",
                      fontWeight: 900
                    }}
                  >
                    Analyses
                  </button>

                  <button
                    onClick={() => setHistoryTab("registrations")}
                    style={{
                      border: "1px solid rgba(229,231,235,0.9)",
                      background: historyTab === "registrations" ? "#111827" : "rgba(255,255,255,0.85)",
                      color: historyTab === "registrations" ? "white" : "#111827",
                      borderRadius: 999,
                      padding: "7px 12px",
                      cursor: "pointer",
                      fontWeight: 900
                    }}
                  >
                    Registrations
                  </button>
                </div>

                {historyTab === "analyses" ? (
                  <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
                    {(analyses || []).map((x) => {
                      const b = badgeForTrust(x.trust, x.verdict);

                      return (
                        <div
                          key={x.id}
                          style={{
                            padding: 12,
                            borderRadius: 14,
                            border: "1px solid rgba(229,231,235,0.9)",
                            background: "rgba(255,255,255,0.75)"
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              gap: 10
                            }}
                          >
                            <div style={{ fontWeight: 900, fontSize: 13 }}>{x.created_at}</div>
                            <ToneBadge tone={b.tone}>
                              {b.label} • {pct(x.trust)}%
                            </ToneBadge>
                          </div>

                          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
                            Verdict: <b>{x.verdict}</b>
                          </div>

                          <div style={{ marginTop: 10 }}>
                            <CopyLine label="SHA-256" value={x.content_sha256} pushToast={pushToast} />
                            <CopyLine label="pHash" value={x.phash} pushToast={pushToast} />
                          </div>
                        </div>
                      );
                    })}

                    {(!analyses || analyses.length === 0) ? (
                      <div style={{ marginTop: 6, fontSize: 13, opacity: 0.75 }}>
                        No analyses yet.
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
                    {(registrations || []).map((x) => (
                      <div
                        key={x.content_sha256}
                        style={{
                          padding: 12,
                          borderRadius: 14,
                          border: "1px solid rgba(229,231,235,0.9)",
                          background: "rgba(255,255,255,0.75)"
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: 10
                          }}
                        >
                          <div style={{ fontWeight: 900, fontSize: 13 }}>{x.created_at}</div>
                          <ToneBadge tone="good">Registered</ToneBadge>
                        </div>

                        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
                          Label: <b>{x.label || "-"}</b>
                        </div>

                        <div style={{ marginTop: 10 }}>
                          <CopyLine label="SHA-256" value={x.content_sha256} pushToast={pushToast} />
                          <CopyLine label="pHash" value={x.phash} pushToast={pushToast} />
                        </div>
                      </div>
                    ))}

                    {(!registrations || registrations.length === 0) ? (
                      <div style={{ marginTop: 6, fontSize: 13, opacity: 0.75 }}>
                        No registrations yet.
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>

        <div style={{ marginTop: 16, fontSize: 12, opacity: 0.75 }}>
          Backend: <code>{API}</code> • OpenAPI: <code>{API}/docs</code>
        </div>
      </div>
    </div>
  );
}