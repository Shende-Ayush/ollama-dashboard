import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";

interface AgentConfig {
  id: string;
  name: string;
  agent_type: string;
  description: string;
  system_prompt: string;
  capabilities: string[];
  model_name: string;
  max_iterations: number;
  temperature: number;
  is_active: boolean;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string | null;
}

interface AgentExecution {
  id: string;
  agent_id: string;
  task: string;
  status: string;
  result: string | null;
  error: string | null;
  iterations_used: number;
  tokens_consumed: number;
  duration_ms: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export function AgentsPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<"agents" | "execute" | "orchestrate" | "history">("agents");


  // Agents list
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [agentTypes, setAgentTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Create/Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formModel, setFormModel] = useState("llama3.2");
  const [formMaxIter, setFormMaxIter] = useState(10);
  const [formTemp, setFormTemp] = useState(0.7);
  const [formSaving, setFormSaving] = useState(false);

  // Execute
  const [execAgentId, setExecAgentId] = useState("");
  const [execTask, setExecTask] = useState("");
  const [execResult, setExecResult] = useState<any>(null);
  const [execLoading, setExecLoading] = useState(false);

  // Orchestrate
  const [orchTask, setOrchTask] = useState("");
  const [orchAgentIds, setOrchAgentIds] = useState("");
  const [orchStrategy, setOrchStrategy] = useState("sequential");
  const [orchResult, setOrchResult] = useState<any>(null);
  const [orchLoading, setOrchLoading] = useState(false);

  // History
  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [histLoading, setHistLoading] = useState(false);


  const loadAgents = async () => {
    setLoading(true);
    try {
      const [agentsRes, typesRes] = await Promise.all([
        api.get<any>("/agents?active_only=false"),
        api.get<any>("/agents/types"),
      ]);
      setAgents(agentsRes.items || []);
      setAgentTypes(typesRes.types || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistLoading(true);
    try {
      const res = await api.get<any>("/agents/executions/history?limit=50");
      setExecutions(res.items || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setHistLoading(false);
    }
  };

  useEffect(() => { loadAgents(); }, []);
  useEffect(() => { if (activeTab === "history") loadHistory(); }, [activeTab]);


  const openCreate = () => {
    setEditId(null);
    setFormName(""); setFormType(agentTypes[0] || "backend");
    setFormDesc(""); setFormPrompt(""); setFormModel("llama3.2");
    setFormMaxIter(10); setFormTemp(0.7);
    setShowModal(true);
  };

  const openEdit = (a: AgentConfig) => {
    setEditId(a.id);
    setFormName(a.name); setFormType(a.agent_type);
    setFormDesc(a.description); setFormPrompt(a.system_prompt);
    setFormModel(a.model_name); setFormMaxIter(a.max_iterations);
    setFormTemp(a.temperature);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formPrompt.trim()) {
      toast("Name and system prompt are required", "error"); return;
    }
    setFormSaving(true);
    try {
      const body = {
        name: formName, agent_type: formType, description: formDesc,
        system_prompt: formPrompt, model_name: formModel,
        max_iterations: formMaxIter, temperature: formTemp,
        capabilities: [], metadata: {},
      };
      if (editId) {
        await api.post<any>(`/agents/${editId}`, body);
        toast("Agent updated", "success");
      } else {
        await api.post<any>("/agents", body);
        toast("Agent created", "success");
      }
      setShowModal(false); loadAgents();
    } catch (e: any) {
      toast(e.message, "error");
    } finally { setFormSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this agent?")) return;
    try {
      await api.delete(`/agents/${id}`);
      toast("Deleted", "success"); loadAgents();
    } catch (e: any) { toast(e.message, "error"); }
  };


  const handleExecute = async () => {
    if (!execAgentId || !execTask.trim()) return;
    setExecLoading(true); setExecResult(null);
    try {
      const res = await api.post<any>("/agents/execute", {
        agent_id: execAgentId, task: execTask, context: {},
      });
      setExecResult(res);
    } catch (e: any) { toast(e.message, "error"); }
    finally { setExecLoading(false); }
  };

  const handleOrchestrate = async () => {
    if (!orchTask.trim() || !orchAgentIds.trim()) return;
    setOrchLoading(true); setOrchResult(null);
    try {
      const agent_ids = orchAgentIds.split(",").map(s => s.trim()).filter(Boolean);
      const res = await api.post<any>("/agents/orchestrate", {
        task: orchTask, agent_ids, strategy: orchStrategy, context: {},
      });
      setOrchResult(res);
    } catch (e: any) { toast(e.message, "error"); }
    finally { setOrchLoading(false); }
  };

  const statusColor = (s: string) => {
    if (s === "completed" || s === "done") return "var(--green, #10b981)";
    if (s === "failed" || s === "error") return "var(--red, #ef4444)";
    if (s === "running" || s === "pending") return "var(--amber, #f59e0b)";
    return "var(--text-muted)";
  };

  const typeColor = (t: string) => {
    const colors: Record<string, string> = {
      backend: "#6366f1", frontend: "#10b981", debugger: "#ef4444",
      security: "#f59e0b", devops: "#06b6d4", testing: "#8b5cf6",
      performance: "#ec4899", orchestrator: "#14b8a6",
    };
    return colors[t] || "#6366f1";
  };

  const tabs = [
    { key: "agents" as const, label: "Agents", icon: "@" },
    { key: "execute" as const, label: "Execute", icon: ">" },
    { key: "orchestrate" as const, label: "Orchestrate", icon: ">>" },
    { key: "history" as const, label: "History", icon: "#" },
  ];


  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">@ Agents</div>
          <div className="page-subtitle">Multi-agent orchestration and execution</div>
        </div>
        <div className="page-header-sep" />
        {activeTab === "agents" && (
          <button className="btn btn-primary btn-sm" onClick={openCreate}>+ New Agent</button>
        )}
      </div>

      <div className="page-body">
        <div className="page-inner">
          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-soft)", paddingBottom: 0 }}>
            {tabs.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                style={{
                  padding: "10px 18px", fontSize: 13,
                  fontWeight: activeTab === t.key ? 600 : 400,
                  color: activeTab === t.key ? "var(--accent, #6366f1)" : "var(--text-muted)",
                  background: "transparent", border: "none",
                  borderBottom: activeTab === t.key ? "2px solid var(--accent, #6366f1)" : "2px solid transparent",
                  cursor: "pointer", transition: "all 150ms",
                }}>
                <span style={{ fontFamily: "var(--font-mono)", marginRight: 6 }}>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>


          {/* Agents Tab */}
          {activeTab === "agents" && (
            <div style={{ marginTop: 16 }}>
              {loading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 90, borderRadius: 10 }} />)}
                </div>
              ) : agents.length === 0 ? (
                <div className="card" style={{ padding: 32, textAlign: "center" }}>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No agents configured. Create one to get started.</div>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
                  {agents.map(a => (
                    <div key={a.id} style={{
                      border: "1px solid var(--border-soft)", borderRadius: 12,
                      padding: "14px 18px", background: "var(--bg-elevated)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{a.name}</span>
                            <span style={{
                              fontSize: 10, padding: "2px 8px", borderRadius: 10,
                              background: `${typeColor(a.agent_type)}20`, color: typeColor(a.agent_type),
                              fontWeight: 600,
                            }}>{a.agent_type}</span>
                          </div>
                          {a.description && <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "6px 0 0" }}>{a.description}</p>}
                        </div>
                        <span style={{
                          width: 8, height: 8, borderRadius: "50%",
                          background: a.is_active ? "var(--green, #10b981)" : "var(--text-muted)",
                        }} />
                      </div>
                      <div style={{ display: "flex", gap: 12, marginTop: 10, fontSize: 11, color: "var(--text-muted)" }}>
                        <span>Model: <span style={{ color: "var(--text-secondary)" }}>{a.model_name}</span></span>
                        <span>Iters: {a.max_iterations}</span>
                        <span>Temp: {a.temperature}</span>
                      </div>
                      <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                        <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => openEdit(a)}>Edit</button>
                        <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => { setExecAgentId(a.id); setActiveTab("execute"); }}>Execute</button>
                        <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, color: "var(--red, #ef4444)" }} onClick={() => handleDelete(a.id)}>Delete</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}


          {/* Execute Tab */}
          {activeTab === "execute" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header"><span className="card-title">Execute Agent</span></div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Run a single agent on a task with step-by-step reasoning.
                </p>
                <select
                  value={execAgentId}
                  onChange={e => setExecAgentId(e.target.value)}
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none",
                  }}
                >
                  <option value="">Select an agent...</option>
                  {agents.filter(a => a.is_active).map(a => (
                    <option key={a.id} value={a.id}>{a.name} ({a.agent_type})</option>
                  ))}
                </select>
                <textarea
                  value={execTask}
                  onChange={e => setExecTask(e.target.value)}
                  placeholder="Describe the task for the agent..."
                  rows={4}
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none", resize: "vertical",
                  }}
                />
                <button className="btn btn-primary" onClick={handleExecute} disabled={execLoading || !execAgentId || !execTask.trim()}>
                  {execLoading ? "Executing..." : "Execute"}
                </button>

                {execResult && (
                  <div style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "16px", background: "var(--bg-elevated)" }}>
                    <div style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 12 }}>
                      <span>Status: <span style={{ fontWeight: 600, color: statusColor(execResult.status) }}>{execResult.status}</span></span>
                      <span>Iterations: {execResult.iterations_used}</span>
                      <span>Tokens: {execResult.tokens_consumed}</span>
                      <span>Duration: {execResult.duration_ms}ms</span>
                    </div>
                    {execResult.result && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 6 }}>Result</div>
                        <pre style={{
                          fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-primary)",
                          background: "var(--bg-surface)", padding: "12px", borderRadius: 8,
                          whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 300, overflowY: "auto",
                        }}>{execResult.result}</pre>
                      </div>
                    )}
                    {execResult.error && (
                      <div style={{ marginTop: 10 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--red, #ef4444)", marginBottom: 6 }}>Error</div>
                        <pre style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--red, #ef4444)", background: "var(--bg-surface)", padding: "12px", borderRadius: 8, whiteSpace: "pre-wrap" }}>{execResult.error}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}


          {/* Orchestrate Tab */}
          {activeTab === "orchestrate" && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header"><span className="card-title">Multi-Agent Orchestration</span></div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                  Coordinate multiple agents to solve a complex task using different strategies.
                </p>
                <textarea
                  value={orchTask}
                  onChange={e => setOrchTask(e.target.value)}
                  placeholder="Describe the task for orchestration..."
                  rows={3}
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", outline: "none", resize: "vertical",
                  }}
                />
                <input
                  value={orchAgentIds}
                  onChange={e => setOrchAgentIds(e.target.value)}
                  placeholder="Agent IDs (comma-separated) or leave empty for auto-selection"
                  style={{
                    padding: "10px 14px", fontSize: 13, borderRadius: 8,
                    border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                    color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none",
                  }}
                />
                {agents.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    Available: {agents.filter(a => a.is_active).map(a => `${a.name} (${a.id.slice(0, 8)})`).join(", ")}
                  </div>
                )}
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Strategy:</span>
                  {["sequential", "parallel", "pipeline"].map(s => (
                    <button key={s} className={`btn btn-sm ${orchStrategy === s ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setOrchStrategy(s)}>{s}</button>
                  ))}
                </div>
                <button className="btn btn-primary" onClick={handleOrchestrate} disabled={orchLoading || !orchTask.trim()}>
                  {orchLoading ? "Orchestrating..." : "Run Orchestration"}
                </button>

                {orchResult && (
                  <div style={{ border: "1px solid var(--border-soft)", borderRadius: 10, padding: "16px", background: "var(--bg-elevated)" }}>
                    <div style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 12 }}>
                      <span>Status: <span style={{ fontWeight: 600, color: statusColor(orchResult.status) }}>{orchResult.status}</span></span>
                      <span>Strategy: {orchResult.strategy}</span>
                      <span>Duration: {orchResult.total_duration_ms}ms</span>
                    </div>
                    {orchResult.results && orchResult.results.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {orchResult.results.map((r: any, i: number) => (
                          <div key={i} style={{ border: "1px solid var(--border-soft)", borderRadius: 8, padding: "10px 14px", background: "var(--bg-surface)" }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent, #6366f1)", marginBottom: 4 }}>Agent: {r.agent_name || r.agent_id?.slice(0, 8)}</div>
                            <pre style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-primary)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{r.result || r.error || "No output"}</pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}


          {/* History Tab */}
          {activeTab === "history" && (
            <div style={{ marginTop: 16 }}>
              {histLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 60, borderRadius: 10 }} />)}
                </div>
              ) : executions.length === 0 ? (
                <div className="card" style={{ padding: 32, textAlign: "center" }}>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No execution history yet.</div>
                </div>
              ) : (
                <div className="card">
                  <div className="card-header"><span className="card-title">Execution History</span></div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border-soft)" }}>
                          {["Task", "Status", "Iterations", "Tokens", "Duration", "Date"].map(h => (
                            <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {executions.map(e => (
                          <tr key={e.id} style={{ borderBottom: "1px solid var(--border-soft)" }}>
                            <td style={{ padding: "10px 14px", maxWidth: 250, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.task}</td>
                            <td style={{ padding: "10px 14px" }}>
                              <span style={{ color: statusColor(e.status), fontWeight: 600 }}>{e.status}</span>
                            </td>
                            <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)" }}>{e.iterations_used}</td>
                            <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)" }}>{e.tokens_consumed}</td>
                            <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)" }}>{e.duration_ms}ms</td>
                            <td style={{ padding: "10px 14px", fontSize: 11, color: "var(--text-muted)" }}>{new Date(e.created_at).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
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
              {editId ? "Edit Agent" : "New Agent"}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <input value={formName} onChange={e => setFormName(e.target.value)} placeholder="Agent name"
                style={{ padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }} />
              <select value={formType} onChange={e => setFormType(e.target.value)}
                style={{ padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }}>
                {agentTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input value={formDesc} onChange={e => setFormDesc(e.target.value)} placeholder="Description"
                style={{ padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }} />
              <textarea value={formPrompt} onChange={e => setFormPrompt(e.target.value)} placeholder="System prompt" rows={5}
                style={{ padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", fontFamily: "var(--font-mono)", outline: "none", resize: "vertical" }} />
              <div style={{ display: "flex", gap: 8 }}>
                <input value={formModel} onChange={e => setFormModel(e.target.value)} placeholder="Model"
                  style={{ flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }} />
                <input type="number" value={formMaxIter} onChange={e => setFormMaxIter(Number(e.target.value))} min={1} max={50}
                  style={{ width: 80, padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }} />
                <input type="number" value={formTemp} onChange={e => setFormTemp(Number(e.target.value))} min={0} max={2} step={0.1}
                  style={{ width: 80, padding: "10px 14px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border-soft)", background: "var(--bg-elevated)", color: "var(--text-primary)", outline: "none" }} />
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Model | Max Iterations | Temperature</div>
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
