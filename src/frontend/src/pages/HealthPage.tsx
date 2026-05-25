import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";

interface ComponentHealth {
  component: string;
  status: string;
  response_time_ms: number;
  details: Record<string, any>;
}

interface SystemHealth {
  overall_status: string;
  components: ComponentHealth[];
  checked_at: string;
}

interface Incident {
  id: string;
  component: string;
  severity: string;
  title: string;
  description: string;
  status: string;
  auto_recovery_attempted: boolean;
  auto_recovery_successful: boolean;
  recovery_action: string | null;
  detected_at: string;
  resolved_at: string | null;
}

interface RecoveryAction {
  id: string;
  incident_id: string | null;
  component: string;
  action_type: string;
  description: string;
  status: string;
  result: string | null;
  executed_at: string;
  duration_ms: number;
}

export function HealthPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<"overview" | "incidents" | "recovery">("overview");


  // System health
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  // Incidents
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentFilter, setIncidentFilter] = useState<string>("");

  // Recovery actions
  const [recoveryActions, setRecoveryActions] = useState<RecoveryAction[]>([]);
  const [recoveryLoading, setRecoveryLoading] = useState(false);

  // Manual recovery
  const [recoverComponent, setRecoverComponent] = useState("");
  const [recoverAction, setRecoverAction] = useState("");
  const [recoverRunning, setRecoverRunning] = useState(false);

  const loadHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await api.get<any>("/health/system");
      setHealth(res);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setHealthLoading(false);
    }
  };

  const loadIncidents = async () => {
    setIncidentsLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (incidentFilter) params.set("status", incidentFilter);
      const res = await api.get<any>(`/health/incidents?${params}`);
      setIncidents(res.items || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setIncidentsLoading(false);
    }
  };

  const loadRecoveryActions = async () => {
    setRecoveryLoading(true);
    try {
      const res = await api.get<any>("/health/recovery-actions?limit=50");
      setRecoveryActions(res.items || []);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setRecoveryLoading(false);
    }
  };

  useEffect(() => { loadHealth(); }, []);
  useEffect(() => { if (activeTab === "incidents") loadIncidents(); }, [activeTab, incidentFilter]);
  useEffect(() => { if (activeTab === "recovery") loadRecoveryActions(); }, [activeTab]);


  const handleResolve = async (incidentId: string) => {
    try {
      await api.post(`/health/incidents/${incidentId}/resolve`);
      toast("Incident resolved", "success");
      loadIncidents();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const handleRecover = async () => {
    if (!recoverComponent.trim() || !recoverAction.trim()) return;
    setRecoverRunning(true);
    try {
      await api.post<any>("/health/recover", {
        component: recoverComponent,
        action_type: recoverAction,
      });
      toast("Recovery triggered", "success");
      loadRecoveryActions();
      loadHealth();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setRecoverRunning(false);
    }
  };

  const statusColor = (s: string) => {
    if (s === "healthy" || s === "resolved" || s === "success") return "var(--green, #10b981)";
    if (s === "degraded" || s === "warning" || s === "acknowledged") return "var(--amber, #f59e0b)";
    if (s === "unhealthy" || s === "critical" || s === "open" || s === "failed") return "var(--red, #ef4444)";
    return "var(--text-muted)";
  };

  const severityIcon = (s: string) => {
    if (s === "critical") return "!!!";
    if (s === "high" || s === "warning") return "!!";
    return "!";
  };

  const componentIcons: Record<string, string> = {
    ollama: "O", postgresql: "P", gpu: "G", disk: "D",
  };

  const tabs = [
    { key: "overview" as const, label: "System Health", icon: "+" },
    { key: "incidents" as const, label: "Incidents", icon: "!" },
    { key: "recovery" as const, label: "Recovery", icon: "R" },
  ];


  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">+ Health Monitor</div>
          <div className="page-subtitle">System health, incidents, and auto-recovery</div>
        </div>
        <div className="page-header-sep" />
        <button className="btn btn-secondary btn-sm" onClick={loadHealth} disabled={healthLoading}>
          {healthLoading ? "Checking..." : "Refresh"}
        </button>
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


          {/* Overview Tab */}
          {activeTab === "overview" && (
            <div style={{ marginTop: 16 }}>
              {healthLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="skeleton" style={{ height: 60, borderRadius: 14 }} />
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                    {[1, 2, 3, 4].map(i => <div key={i} className="skeleton" style={{ height: 120, borderRadius: 12 }} />)}
                  </div>
                </div>
              ) : health ? (
                <>
                  {/* Overall status banner */}
                  <div style={{
                    padding: "14px 20px", borderRadius: 12, marginBottom: 16,
                    background: health.overall_status === "healthy" ? "rgba(16,185,129,0.08)" : health.overall_status === "degraded" ? "rgba(245,158,11,0.08)" : "rgba(239,68,68,0.08)",
                    border: `1px solid ${statusColor(health.overall_status)}30`,
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ width: 12, height: 12, borderRadius: "50%", background: statusColor(health.overall_status) }} />
                      <span style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>
                        System {health.overall_status}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      Last check: {new Date(health.checked_at).toLocaleString()}
                    </span>
                  </div>

                  {/* Component cards */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
                    {health.components.map(c => (
                      <div key={c.component} style={{
                        border: "1px solid var(--border-soft)", borderRadius: 12,
                        padding: "16px", background: "var(--bg-elevated)",
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{
                              width: 28, height: 28, borderRadius: 8, display: "flex",
                              alignItems: "center", justifyContent: "center",
                              background: `${statusColor(c.status)}15`, color: statusColor(c.status),
                              fontSize: 12, fontWeight: 700, fontFamily: "var(--font-mono)",
                            }}>
                              {componentIcons[c.component.toLowerCase()] || c.component[0].toUpperCase()}
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", textTransform: "capitalize" }}>
                              {c.component}
                            </span>
                          </div>
                          <span style={{
                            width: 8, height: 8, borderRadius: "50%",
                            background: statusColor(c.status),
                          }} />
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: 12, color: statusColor(c.status), fontWeight: 600, textTransform: "capitalize" }}>
                            {c.status}
                          </span>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            {c.response_time_ms}ms
                          </span>
                        </div>
                        {c.details && Object.keys(c.details).length > 0 && (
                          <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-muted)" }}>
                            {Object.entries(c.details).slice(0, 3).map(([k, v]) => (
                              <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                                <span>{k}:</span>
                                <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="card" style={{ padding: 32, textAlign: "center" }}>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Unable to load health data. Click Refresh to try again.</div>
                </div>
              )}
            </div>
          )}


          {/* Incidents Tab */}
          {activeTab === "incidents" && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                {["", "open", "acknowledged", "resolved"].map(f => (
                  <button key={f} className={`btn btn-sm ${incidentFilter === f ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setIncidentFilter(f)}>
                    {f || "All"}
                  </button>
                ))}
              </div>

              {incidentsLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 70, borderRadius: 10 }} />)}
                </div>
              ) : incidents.length === 0 ? (
                <div className="card" style={{ padding: 32, textAlign: "center" }}>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No incidents found.</div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {incidents.map(inc => (
                    <div key={inc.id} style={{
                      border: "1px solid var(--border-soft)", borderRadius: 10,
                      padding: "14px 18px", background: "var(--bg-elevated)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: statusColor(inc.severity), fontFamily: "var(--font-mono)" }}>
                              {severityIcon(inc.severity)}
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{inc.title}</span>
                          </div>
                          {inc.description && <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 8px" }}>{inc.description}</p>}
                          <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-muted)" }}>
                            <span>Component: <span style={{ color: "var(--text-secondary)" }}>{inc.component}</span></span>
                            <span>Severity: <span style={{ color: statusColor(inc.severity) }}>{inc.severity}</span></span>
                            <span>Status: <span style={{ color: statusColor(inc.status) }}>{inc.status}</span></span>
                            {inc.auto_recovery_attempted && (
                              <span>Auto-recovery: <span style={{ color: inc.auto_recovery_successful ? "var(--green, #10b981)" : "var(--red, #ef4444)" }}>
                                {inc.auto_recovery_successful ? "Success" : "Failed"}
                              </span></span>
                            )}
                          </div>
                          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>
                            Detected: {new Date(inc.detected_at).toLocaleString()}
                            {inc.resolved_at && ` | Resolved: ${new Date(inc.resolved_at).toLocaleString()}`}
                          </div>
                        </div>
                        {inc.status !== "resolved" && (
                          <button className="btn btn-sm btn-secondary" onClick={() => handleResolve(inc.id)} style={{ flexShrink: 0 }}>
                            Resolve
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}


          {/* Recovery Tab */}
          {activeTab === "recovery" && (
            <div style={{ marginTop: 16 }}>
              {/* Manual recovery trigger */}
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="card-header"><span className="card-title">Trigger Manual Recovery</span></div>
                <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                    Manually trigger a recovery action for a specific component.
                  </p>
                  <div style={{ display: "flex", gap: 8 }}>
                    <select
                      value={recoverComponent}
                      onChange={e => setRecoverComponent(e.target.value)}
                      style={{
                        flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                        border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                        color: "var(--text-primary)", outline: "none",
                      }}
                    >
                      <option value="">Select component...</option>
                      <option value="ollama">Ollama</option>
                      <option value="postgresql">PostgreSQL</option>
                      <option value="gpu">GPU</option>
                      <option value="disk">Disk</option>
                    </select>
                    <select
                      value={recoverAction}
                      onChange={e => setRecoverAction(e.target.value)}
                      style={{
                        flex: 1, padding: "10px 14px", fontSize: 13, borderRadius: 8,
                        border: "1px solid var(--border-soft)", background: "var(--bg-elevated)",
                        color: "var(--text-primary)", outline: "none",
                      }}
                    >
                      <option value="">Select action...</option>
                      <option value="restart">Restart</option>
                      <option value="reconnect">Reconnect</option>
                      <option value="clear_cache">Clear Cache</option>
                      <option value="release_memory">Release Memory</option>
                    </select>
                    <button className="btn btn-primary" onClick={handleRecover}
                      disabled={recoverRunning || !recoverComponent || !recoverAction}>
                      {recoverRunning ? "Running..." : "Trigger"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Recovery history */}
              {recoveryLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 60, borderRadius: 10 }} />)}
                </div>
              ) : recoveryActions.length === 0 ? (
                <div className="card" style={{ padding: 32, textAlign: "center" }}>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>No recovery actions recorded.</div>
                </div>
              ) : (
                <div className="card">
                  <div className="card-header"><span className="card-title">Recovery Actions History</span></div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border-soft)" }}>
                          {["Component", "Action", "Status", "Result", "Duration", "Executed"].map(h => (
                            <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {recoveryActions.map(a => (
                          <tr key={a.id} style={{ borderBottom: "1px solid var(--border-soft)" }}>
                            <td style={{ padding: "10px 14px", textTransform: "capitalize" }}>{a.component}</td>
                            <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)" }}>{a.action_type}</td>
                            <td style={{ padding: "10px 14px" }}>
                              <span style={{ color: statusColor(a.status), fontWeight: 600 }}>{a.status}</span>
                            </td>
                            <td style={{ padding: "10px 14px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {a.result || "-"}
                            </td>
                            <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)" }}>{a.duration_ms}ms</td>
                            <td style={{ padding: "10px 14px", fontSize: 11, color: "var(--text-muted)" }}>
                              {new Date(a.executed_at).toLocaleString()}
                            </td>
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
    </div>
  );
}
