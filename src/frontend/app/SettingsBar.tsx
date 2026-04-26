import React, { useState } from "react";
import { getApiKey, setApiKey } from "../common/auth";
import { useToast } from "../hooks/useToast";
export function SettingsBar() {
  const [key, setKey] = useState(getApiKey);
  const [saved, setSaved] = useState(false);
  const { toast } = useToast();
  const save = () => {
    setApiKey(key);
    setSaved(true);
    toast("API key saved", "success");
    setTimeout(() => setSaved(false), 2000);
  };
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 20px", borderBottom:"1px solid var(--border-soft)", background:"var(--bg-surface)", flexShrink:0 }}>
      <span style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--text-muted)" }}>API KEY</span>
      <input
        type="password"
        value={key}
        onChange={e => setKey(e.target.value)}
        onKeyDown={e => e.key === "Enter" && save()}
        placeholder="Paste your Ollama API key…"
        className="input"
        style={{ maxWidth:260, padding:"4px 10px", fontSize:12, fontFamily:"var(--font-mono)" }}
      />
      <button className={`btn btn-sm ${saved ? "btn-success" : "btn-secondary"}`} onClick={save}>
        {saved ? "✓ Saved" : "Save"}
      </button>
      <div style={{ flex:1 }} />
      <span style={{ fontSize:11, color:"var(--text-muted)" }}>Ollama Dashboard v2</span>
    </div>
  );
}
