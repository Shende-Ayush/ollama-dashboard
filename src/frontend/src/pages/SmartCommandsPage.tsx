import React, { useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";

interface Suggestion {
  command: string;
  explanation: string;
  confidence: number;
}

interface Explanation {
  command: string;
  description: string;
  parameters: { name: string; description: string }[];
  side_effects: string[];
  safety_level: string;
}

interface ErrorAnalysis {
  root_cause: string;
  suggested_fix: string;
  fix_command: string | null;
  severity: string;
  auto_fixable: boolean;
}

interface AutocompleteItem {
  text: string;
  type: string;
  description?: string;
}

export function SmartCommandsPage() {
  const { toast } = useToast();

  // Natural Language tab
  const [nlInput, setNlInput] = useState("");
  const [nlResult, setNlResult] = useState<Suggestion[] | null>(null);
  const [nlLoading, setNlLoading] = useState(false);

  // Explain tab
  const [explainInput, setExplainInput] = useState("");
  const [explainResult, setExplainResult] = useState<Explanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);

  // Error Analysis tab
  const [errorCmd, setErrorCmd] = useState("");
  const [errorOutput, setErrorOutput] = useState("");
  const [errorResult, setErrorResult] = useState<ErrorAnalysis | null>(null);
  const [errorLoading, setErrorLoading] = useState(false);

  // Autocomplete
  const [acInput, setAcInput] = useState("");
  const [acResults, setAcResults] = useState<AutocompleteItem[]>([]);
  const [acLoading, setAcLoading] = useState(false);

  const [activeTab, setActiveTab] = useState<"nl" | "explain" | "error" | "autocomplete">("nl");

  const handleNl = async () => {
    if (!nlInput.trim()) return;
    setNlLoading(true);
    setNlResult(null);
    try {
      const res = await api.post<any>("/smart-commands/natural-language", { intent: nlInput, context: {} });
      setNlResult(res.suggestions || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setNlLoading(false);
    }
  };

  const handleExplain = async () => {
    if (!explainInput.trim()) return;
    setExplainLoading(true);
    setExplainResult(null);
    try {
      const res = await api.post<any>("/smart-commands/explain", { command: explainInput });
      setExplainResult(res);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setExplainLoading(false);
    }
  };

  const handleError = async () => {
    if (!errorCmd.trim() || !errorOutput.trim()) return;
    setErrorLoading(true);
    setErrorResult(null);
    try {
      const res = await api.post<any>("/smart-commands/analyze-error", {
        command: errorCmd,
        error_output: errorOutput,
        system_context: {},
      });
      setErrorResult(res);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setErrorLoading(false);
    }
  };

  const handleAutocomplete = async () => {
    if (!acInput.trim()) return;
    setAcLoading(true);
    setAcResults([]);
    try {
      const res = await api.get<any>(`/smart-commands/autocomplete?q=${encodeURIComponent(acInput)}`);
      setAcResults(res.suggestions || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setAcLoading(false);
    }
  };

  const tabs = [
    { key: "nl" as const, label: "Natural Language", icon: "~" },
    { key: "explain" as const, label: "Explain", icon: "?" },
    { key: "error" as const, label: "Error Analysis", icon: "!" },
    { key: "autocomplete" as const, label: "Autocomplete", icon: ">" },
  ];

  const severityColor = (s: string) => {
    if (s === "critical" || s === "high") return "var(--red, #ef4444)";
    if (s === "medium") return "var(--amber, #f59e0b)";
    return "var(--green, #10b981)";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">~ Smart Commands</div>
          <div className="page-subtitle">AI-powered command generation, explanation, and error analysis</div>
        </div>
      </div>

      <div className="page-body">
        <div className="page-inner">
          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-soft)", paddingBottom: 0 }}>
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                style={{
                  padding: "10px 18px",
                  fontSize: 13,
                  fontWeight: activeTab === t.key ? 600 : 400,
                  color: activeTab === t.key ? "var(--accent, #6366f1)" : "var(--text-muted)",
                  background: "transparent",
                  border: "none",
                  borderBottom: activeTab === t.key ? "2px solid var(--accent, #6366f1)" : "2px solid transparent",
                  cursor: "pointer",
                  transition: "all 150ms",
                }}
              >
                <span style={{ fontFamily: "var(--font-mono)", marginRight: 6 }}>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>

          {/* Natural Language Tab */}
          {activeTab === "nl" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Natural Language to Command</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Describe what you want to do in plain English, and get Ollama commands.
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    value={nlInput}
                    onChange={e => setNlInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleNl()}
                    placeholder="e.g., Install a coding model optimized for TypeScript"
                    style={{
                      flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                      border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                      color: "var(--text-primary)", outline: "none",
                    }}
                  />
                  <button className="btn btn-primary" onClick={handleNl} disabled={nlLoading || !nlInput.trim()}>
                    {nlLoading ? "Thinking..." : "Generate"}
                  </button>
                </div>

                {nlResult && nlResult.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {nlResult.map((s, i) => (
                      <div key={i} style={{
                        border: "1px solid var(--border-soft)", borderRadius: 10,
                        padding: "12px 16px", background: "var(--bg-elevated)",
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <code style={{ fontSize: 13, color: "var(--accent, #6366f1)", fontFamily: "var(--font-mono)" }}>
                            {s.command}
                          </code>
                          <span style={{
                            fontSize: 11, padding: "2px 8px", borderRadius: 12,
                            background: `rgba(99,102,241,${s.confidence})`,
                            color: "#fff", fontWeight: 600,
                          }}>
                            {Math.round(s.confidence * 100)}%
                          </span>
                        </div>
                        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "6px 0 0" }}>{s.explanation}</p>
                      </div>
                    ))}
                  </div>
                )}

                {nlResult && nlResult.length === 0 && (
                  <div style={{ fontSize: 13, color: "var(--text-muted)", fontStyle: "italic" }}>
                    No suggestions found. Try rephrasing your intent.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Explain Tab */}
          {activeTab === "explain" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Command Explainer</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Paste an Ollama command to get a detailed explanation.
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    value={explainInput}
                    onChange={e => setExplainInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleExplain()}
                    placeholder="e.g., ollama run llama3.2 --format json"
                    style={{
                      flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                      border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                      color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none",
                    }}
                  />
                  <button className="btn btn-primary" onClick={handleExplain} disabled={explainLoading || !explainInput.trim()}>
                    {explainLoading ? "Analyzing..." : "Explain"}
                  </button>
                </div>

                {explainResult && (
                  <div style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "16px", background: "var(--bg-elevated)" }}>
                    <div style={{ marginBottom: 12 }}>
                      <code style={{ fontSize: 14, color: "var(--accent, #6366f1)", fontFamily: "var(--font-mono)" }}>
                        {explainResult.command}
                      </code>
                    </div>
                    <p style={{ fontSize: 13, color: "var(--text-primary)", margin: "0 0 12px" }}>{explainResult.description}</p>

                    {explainResult.parameters && explainResult.parameters.length > 0 && (
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.05em" }}>Parameters</div>
                        {explainResult.parameters.map((p, i) => (
                          <div key={i} style={{ fontSize: 12, marginBottom: 4, display: "flex", gap: 8 }}>
                            <code style={{ color: "var(--cyan, #06b6d4)", fontFamily: "var(--font-mono)" }}>{p.name}</code>
                            <span style={{ color: "var(--text-muted)" }}>{p.description}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {explainResult.side_effects && explainResult.side_effects.length > 0 && (
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.05em" }}>Side Effects</div>
                        {explainResult.side_effects.map((s, i) => (
                          <div key={i} style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 2 }}>- {s}</div>
                        ))}
                      </div>
                    )}

                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)" }}>Safety:</span>
                      <span className={`badge badge-${explainResult.safety_level === "safe" ? "green" : explainResult.safety_level === "caution" ? "amber" : "red"}`}>
                        {explainResult.safety_level}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error Analysis Tab */}
          {activeTab === "error" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Error Analysis</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Paste a failed command and its error output to get AI-powered root cause analysis.
                </p>
                <input
                  value={errorCmd}
                  onChange={e => setErrorCmd(e.target.value)}
                  placeholder="Command that failed (e.g., ollama pull nonexistent:model)"
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none",
                  }}
                />
                <textarea
                  value={errorOutput}
                  onChange={e => setErrorOutput(e.target.value)}
                  placeholder="Paste the error output here..."
                  rows={5}
                  style={{
                    padding: "10px 14px", fontSize: 12, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none",
                    resize: "vertical",
                  }}
                />
                <button className="btn btn-primary" onClick={handleError} disabled={errorLoading || !errorCmd.trim() || !errorOutput.trim()}>
                  {errorLoading ? "Analyzing..." : "Analyze Error"}
                </button>

                {errorResult && (
                  <div style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "16px", background: "var(--bg-elevated)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)" }}>Severity:</span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: severityColor(errorResult.severity) }}>
                        {errorResult.severity}
                      </span>
                      {errorResult.auto_fixable && (
                        <span className="badge badge-green" style={{ marginLeft: 8 }}>Auto-fixable</span>
                      )}
                    </div>

                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.05em" }}>Root Cause</div>
                      <p style={{ fontSize: 13, color: "var(--text-primary)", margin: 0 }}>{errorResult.root_cause}</p>
                    </div>

                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.05em" }}>Suggested Fix</div>
                      <p style={{ fontSize: 13, color: "var(--text-primary)", margin: 0 }}>{errorResult.suggested_fix}</p>
                    </div>

                    {errorResult.fix_command && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.05em" }}>Fix Command</div>
                        <code style={{
                          display: "block", padding: "10px 14px", borderRadius: 8,
                          background: "var(--bg-surface)", fontSize: 13,
                          color: "var(--accent, #6366f1)", fontFamily: "var(--font-mono)",
                        }}>
                          {errorResult.fix_command}
                        </code>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Autocomplete Tab */}
          {activeTab === "autocomplete" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Smart Autocomplete</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Type a partial command to get context-aware completions.
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    value={acInput}
                    onChange={e => setAcInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleAutocomplete()}
                    placeholder="e.g., ollama pu"
                    style={{
                      flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                      border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                      color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none",
                    }}
                  />
                  <button className="btn btn-primary" onClick={handleAutocomplete} disabled={acLoading || !acInput.trim()}>
                    {acLoading ? "..." : "Complete"}
                  </button>
                </div>

                {acResults.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {acResults.map((item, i) => (
                      <div key={i} style={{
                        border: "1px solid var(--border-soft)", borderRadius: 8,
                        padding: "8px 14px", background: "var(--bg-elevated)",
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                      }}>
                        <div>
                          <code style={{ fontSize: 13, color: "var(--accent, #6366f1)", fontFamily: "var(--font-mono)" }}>
                            {item.text}
                          </code>
                          {item.description && (
                            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{item.description}</div>
                          )}
                        </div>
                        <span className="badge badge-blue" style={{ fontSize: 10 }}>{item.type}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
