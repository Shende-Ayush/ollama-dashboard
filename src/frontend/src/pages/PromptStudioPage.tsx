import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";

interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  template: string;
  variables: string[];
  tags: string[];
  model_name: string | null;
  is_public: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string | null;
}

interface PromptVersion {
  id: string;
  template_id: string;
  version_number: number;
  template_content: string;
  variables: string[];
  change_notes: string;
  created_at: string;
}

interface TestResult {
  model_name: string;
  response: string;
  tokens_input: number;
  tokens_output: number;
  latency_ms: number;
}

interface TokenAnalysis {
  total_tokens: number;
  breakdown: { type: string; count: number; percentage: number }[];
  context_window_usage: { model: string; percentage: number }[];
}

export function PromptStudioPage() {
  const { toast } = useToast();

  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Create/Edit Modal
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formTemplate, setFormTemplate] = useState("");
  const [formTags, setFormTags] = useState("");
  const [formModel, setFormModel] = useState("");
  const [formSaving, setFormSaving] = useState(false);

  // Detail/Versions view
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null);
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  // Test prompt
  const [testPrompt, setTestPrompt] = useState("");
  const [testModels, setTestModels] = useState("llama3.2");
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [testLoading, setTestLoading] = useState(false);

  // Token analysis
  const [analyzeText, setAnalyzeText] = useState("");
  const [tokenAnalysis, setTokenAnalysis] = useState<TokenAnalysis | null>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);

  const [activeTab, setActiveTab] = useState<"templates" | "test" | "tokens">("templates");

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ pg_no: String(page), pg_size: "20" });
      if (search) params.set("search", search);
      const res = await api.get<any>(`/prompt-studio/templates?${params}`);
      setTemplates(res.items || []);
      setTotalPages(res.total_pages || 1);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTemplates(); }, [page, search]);

  const openCreate = () => {
    setEditId(null);
    setFormName("");
    setFormDesc("");
    setFormTemplate("");
    setFormTags("");
    setFormModel("");
    setShowModal(true);
  };

  const openEdit = (t: PromptTemplate) => {
    setEditId(t.id);
    setFormName(t.name);
    setFormDesc(t.description);
    setFormTemplate(t.template);
    setFormTags((t.tags || []).join(", "));
    setFormModel(t.model_name || "");
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formTemplate.trim()) {
      toast("Name and template are required", "error");
      return;
    }
    setFormSaving(true);
    try {
      const body = {
        name: formName,
        description: formDesc,
        template: formTemplate,
        tags: formTags.split(",").map(t => t.trim()).filter(Boolean),
        model_name: formModel || null,
      };
      if (editId) {
        await api.post<any>(`/prompt-studio/templates/${editId}`, body);
        toast("Template updated", "success");
      } else {
        await api.post<any>("/prompt-studio/templates", body);
        toast("Template created", "success");
      }
      setShowModal(false);
      loadTemplates();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setFormSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this template?")) return;
    try {
      await api.delete(`/prompt-studio/templates/${id}`);
      toast("Deleted", "success");
      loadTemplates();
      if (selectedTemplate?.id === id) setSelectedTemplate(null);
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const loadVersions = async (templateId: string) => {
    setVersionsLoading(true);
    try {
      const res = await api.get<any>(`/prompt-studio/templates/${templateId}/versions`);
      setVersions(res.items || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRestore = async (templateId: string, versionNumber: number) => {
    try {
      await api.post(`/prompt-studio/templates/${templateId}/restore/${versionNumber}`);
      toast(`Restored to version ${versionNumber}`, "success");
      loadTemplates();
      loadVersions(templateId);
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const selectTemplate = (t: PromptTemplate) => {
    setSelectedTemplate(t);
    loadVersions(t.id);
  };

  const handleTest = async () => {
    if (!testPrompt.trim() || !testModels.trim()) return;
    setTestLoading(true);
    setTestResults([]);
    try {
      const models = testModels.split(",").map(m => m.trim()).filter(Boolean);
      const res = await api.post<any>("/prompt-studio/test", {
        prompt: testPrompt,
        models,
        template_id: selectedTemplate?.id || null,
        variables: {},
      });
      setTestResults(res.results || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setTestLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!analyzeText.trim()) return;
    setAnalyzeLoading(true);
    setTokenAnalysis(null);
    try {
      const res = await api.post<any>("/prompt-studio/analyze-tokens", { text: analyzeText });
      setTokenAnalysis(res);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const tabs = [
    { key: "templates" as const, label: "Templates", icon: "[]" },
    { key: "test" as const, label: "Test Prompt", icon: ">" },
    { key: "tokens" as const, label: "Token Analysis", icon: "#" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">Prompt Studio</div>
          <div className="page-subtitle">Design, version, test, and analyze prompts</div>
        </div>
        <div className="page-header-sep" />
        {activeTab === "templates" && (
          <button className="btn btn-primary btn-sm" onClick={openCreate}>+ New Template</button>
        )}
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
                  padding: "10px 18px", fontSize: 13,
                  fontWeight: activeTab === t.key ? 600 : 400,
                  color: activeTab === t.key ? "var(--accent, #6366f1)" : "var(--text-muted)",
                  background: "transparent", border: "none",
                  borderBottom: activeTab === t.key ? "2px solid var(--accent, #6366f1)" : "2px solid transparent",
                  cursor: "pointer", transition: "all 150ms",
                }}
              >
                <span style={{ fontFamily: "var(--font-mono)", marginRight: 6 }}>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>

          {/* Templates Tab */}
          {activeTab === "templates" && (
            <div style={{ marginTop: 16 }}>
              {/* Search */}
              <div style={{ marginBottom: 14 }}>
                <input
                  value={search}
                  onChange={e => { setSearch(e.target.value); setPage(1); }}
                  placeholder="Search templates..."
                  style={{
                    width: "100%", maxWidth: 400, padding: "8px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none",
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: 16 }}>
                {/* Template list */}
                <div style={{ flex: 1 }}>
                  {loading ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 80, borderRadius: 10 }} />)}
                    </div>
                  ) : templates.length === 0 ? (
                    <div className="card" style={{ padding: 32, textAlign: "center" }}>
                      <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No templates yet. Create one to get started.</div>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {templates.map(t => (
                        <div
                          key={t.id}
                          onClick={() => selectTemplate(t)}
                          style={{
                            border: `1px solid ${selectedTemplate?.id === t.id ? "var(--accent, #6366f1)" : "var(--border-soft)"}`,
                            borderRadius: 10, padding: "12px 16px", background: "var(--bg-elevated)",
                            cursor: "pointer", transition: "border-color 150ms",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{t.name}</span>
                            <div style={{ display: "flex", gap: 4 }}>
                              <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); openEdit(t); }} style={{ fontSize: 11 }}>Edit</button>
                              <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); handleDelete(t.id); }} style={{ fontSize: 11, color: "var(--red, #ef4444)" }}>Del</button>
                            </div>
                          </div>
                          {t.description && <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 0" }}>{t.description}</p>}
                          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                            {(t.tags || []).map(tag => (
                              <span key={tag} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(99,102,241,0.12)", color: "var(--accent, #6366f1)" }}>{tag}</span>
                            ))}
                            {t.model_name && (
                              <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(16,185,129,0.12)", color: "var(--green, #10b981)" }}>{t.model_name}</span>
                            )}
                            <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: "auto" }}>Used {t.usage_count}x</span>
                          </div>
                        </div>
                      ))}

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 12, marginTop: 12 }}>
                          <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
                          <span style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{page}/{totalPages}</span>
                          <button className="btn btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Detail / Versions panel */}
                {selectedTemplate && (
                  <div style={{ width: 360, flexShrink: 0 }}>
                    <div className="card">
                      <div className="card-header">
                        <span className="card-title">Version History</span>
                      </div>
                      <div className="card-body">
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em", marginBottom: 6 }}>Current Template</div>
                          <pre style={{
                            fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-secondary)",
                            background: "var(--bg-surface)", padding: "10px 12px", borderRadius: 8,
                            whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 120, overflowY: "auto",
                          }}>
                            {selectedTemplate.template}
                          </pre>
                        </div>

                        {versionsLoading ? (
                          <div className="skeleton" style={{ height: 60, borderRadius: 8 }} />
                        ) : versions.length === 0 ? (
                          <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic" }}>No version history</div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 300, overflowY: "auto" }}>
                            {versions.map(v => (
                              <div key={v.id} style={{
                                border: "1px solid var(--border-soft)", borderRadius: 8,
                                padding: "8px 12px", background: "var(--bg-surface)",
                              }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>v{v.version_number}</span>
                                  <button
                                    className="btn btn-ghost btn-sm"
                                    style={{ fontSize: 10 }}
                                    onClick={() => handleRestore(selectedTemplate.id, v.version_number)}
                                  >
                                    Restore
                                  </button>
                                </div>
                                {v.change_notes && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{v.change_notes}</div>}
                                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>
                                  {new Date(v.created_at).toLocaleString()}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Test Prompt Tab */}
          {activeTab === "test" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Multi-Model Prompt Testing</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Test a prompt across multiple models and compare results side-by-side.
                </p>
                <textarea
                  value={testPrompt}
                  onChange={e => setTestPrompt(e.target.value)}
                  placeholder="Enter your prompt here..."
                  rows={4}
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none", resize: "vertical",
                  }}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    value={testModels}
                    onChange={e => setTestModels(e.target.value)}
                    placeholder="Models (comma-separated, e.g., llama3.2, codellama)"
                    style={{
                      flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                      border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                      color: "var(--text-primary)", outline: "none",
                    }}
                  />
                  <button className="btn btn-primary" onClick={handleTest} disabled={testLoading || !testPrompt.trim()}>
                    {testLoading ? "Running..." : "Run Test"}
                  </button>
                </div>

                {testResults.length > 0 && (
                  <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(testResults.length, 3)}, 1fr)`, gap: 12 }}>
                    {testResults.map((r, i) => (
                      <div key={i} style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "14px", background: "var(--bg-elevated)" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--accent, #6366f1)" }}>{r.model_name}</span>
                          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{r.latency_ms}ms</span>
                        </div>
                        <pre style={{
                          fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-primary)",
                          background: "var(--bg-surface)", padding: "10px 12px", borderRadius: 8,
                          whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 200, overflowY: "auto",
                          margin: "0 0 10px",
                        }}>
                          {r.response}
                        </pre>
                        <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-muted)" }}>
                          <span>In: {r.tokens_input}</span>
                          <span>Out: {r.tokens_output}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Token Analysis Tab */}
          {activeTab === "tokens" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <span className="card-title">Token Analysis</span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Analyze token count, context window usage, and content breakdown for any prompt text.
                </p>
                <textarea
                  value={analyzeText}
                  onChange={e => setAnalyzeText(e.target.value)}
                  placeholder="Paste prompt text to analyze..."
                  rows={5}
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none", resize: "vertical",
                  }}
                />
                <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzeLoading || !analyzeText.trim()} style={{ alignSelf: "flex-start" }}>
                  {analyzeLoading ? "Analyzing..." : "Analyze Tokens"}
                </button>

                {tokenAnalysis && (
                  <div style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "16px", background: "var(--bg-elevated)" }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent, #6366f1)", marginBottom: 16 }}>
                      {tokenAnalysis.total_tokens} <span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-muted)" }}>tokens</span>
                    </div>

                    {tokenAnalysis.breakdown && tokenAnalysis.breakdown.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8, letterSpacing: "0.05em" }}>Breakdown</div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          {tokenAnalysis.breakdown.map((b, i) => (
                            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <span style={{ fontSize: 12, color: "var(--text-secondary)", width: 100 }}>{b.type}</span>
                              <div style={{ flex: 1, height: 8, borderRadius: 4, background: "var(--bg-surface)", overflow: "hidden" }}>
                                <div style={{ width: `${b.percentage}%`, height: "100%", borderRadius: 4, background: "var(--accent, #6366f1)" }} />
                              </div>
                              <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)", width: 50, textAlign: "right" }}>{b.count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {tokenAnalysis.context_window_usage && tokenAnalysis.context_window_usage.length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8, letterSpacing: "0.05em" }}>Context Window Usage</div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
                          {tokenAnalysis.context_window_usage.map((c, i) => (
                            <div key={i} style={{ border: "1px solid var(--border-soft)", borderRadius: 8, padding: "10px 12px" }}>
                              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{c.model}</div>
                              <div style={{ fontSize: 18, fontWeight: 700, color: c.percentage > 80 ? "var(--red, #ef4444)" : c.percentage > 50 ? "var(--amber, #f59e0b)" : "var(--green, #10b981)" }}>
                                {c.percentage}%
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
        }} onClick={() => setShowModal(false)}>
          <div style={{
            background: "var(--bg-surface)", borderRadius: 14, padding: "24px",
            width: "100%", maxWidth: 520, maxHeight: "80vh", overflowY: "auto",
            border: "1px solid var(--border-soft)",
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, color: "var(--text-primary)" }}>
              {editId ? "Edit Template" : "New Template"}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <input
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="Template name"
                style={{
                  padding: "10px 14px", fontSize: 13, borderRadius: 8,
                  border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                  color: "var(--text-primary)", outline: "none",
                }}
              />
              <input
                value={formDesc}
                onChange={e => setFormDesc(e.target.value)}
                placeholder="Description (optional)"
                style={{
                  padding: "10px 14px", fontSize: 13, borderRadius: 8,
                  border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                  color: "var(--text-primary)", outline: "none",
                }}
              />
              <textarea
                value={formTemplate}
                onChange={e => setFormTemplate(e.target.value)}
                placeholder="Template content (use {{variable}} for variables)"
                rows={6}
                style={{
                  padding: "10px 14px", fontSize: 13, borderRadius: 8,
                  border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                  color: "var(--text-primary)", fontFamily: "var(--font-mono)",
                  outline: "none", resize: "vertical",
                }}
              />
              <input
                value={formTags}
                onChange={e => setFormTags(e.target.value)}
                placeholder="Tags (comma-separated)"
                style={{
                  padding: "10px 14px", fontSize: 13, borderRadius: 8,
                  border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                  color: "var(--text-primary)", outline: "none",
                }}
              />
              <input
                value={formModel}
                onChange={e => setFormModel(e.target.value)}
                placeholder="Preferred model (optional)"
                style={{
                  padding: "10px 14px", fontSize: 13, borderRadius: 8,
                  border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                  color: "var(--text-primary)", outline: "none",
                }}
              />

              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}>
                <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSave} disabled={formSaving}>
                  {formSaving ? "Saving..." : editId ? "Update" : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
