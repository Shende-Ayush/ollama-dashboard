import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";
import type { PopularModel } from "../common/types";

const TAGS_FILTER = ["tools", "thinking", "vision", "audio"];
const PAGE_SIZE = 20;

type ModelTag = {
  tag: string;
  size: string;
  context: string;
  input: string;
};

type RawModel = {
  name: string;
  description?: string;
  capabilities?: string[];
  sizes?: string[];
  pulls?: string;
  tag_count?: string;
  updated?: string;
};

type RichModel = PopularModel & {
  pulls?: string;
  tag_count?: string;
  updated?: string;
};

function normalizePopularModels(data: any[]): RichModel[] {
  if (!Array.isArray(data)) return [];
  return data.map((meta: RawModel) => ({
    id: meta.name,
    description: meta.description || "No description",
    params: meta.sizes?.length ? meta.sizes.join(", ") : "–",
    size_gb: null,
    tags: meta.capabilities || [],
    installed: false,
    recommended: meta.capabilities?.includes("thinking") || false,
    pulls: meta.pulls,
    tag_count: meta.tag_count,
    updated: meta.updated,
  }));
}

const CAP_COLORS: Record<string, string> = {
  tools:   "var(--badge-tools)",
  thinking:"var(--badge-thinking)",
  vision:  "var(--badge-vision)",
  audio:   "var(--badge-audio)",
};
const CAP_ICONS: Record<string, string> = {
  tools:   "⚙",
  thinking:"◈",
  vision:  "◉",
  audio:   "◎",
};

export function DiscoverPage() {
  const [models, setModels]           = useState<RichModel[]>([]);
  const [search, setSearch]           = useState("");
  const [capability, setCapability]   = useState("");
  const [loading, setLoading]         = useState(true);
  const [page, setPage]               = useState(1);
  const [hasMore, setHasMore]         = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const [selectedModel, setSelectedModel] = useState<RichModel | null>(null);
  const [tags, setTags]               = useState<ModelTag[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);

  const tagsCache   = useRef<Record<string, ModelTag[]>>({});
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const filtersRef  = useRef({ search: "", capability: "" });

  const [pulling, setPulling] = useState<string | null>(null);
  const { toast } = useToast();

  // ── Fetch models ────────────────────────────────────────────────────────────
  const fetchModels = useCallback(async (
    pageNum: number,
    currentSearch: string,
    currentCapability: string,
    append: boolean
  ) => {
    try {
      if (pageNum === 1) setLoading(true);
      else setLoadingMore(true);

      const params = new URLSearchParams();
      if (currentSearch)     params.set("search",     currentSearch);
      if (currentCapability) params.set("capability", currentCapability);
      params.set("page",      String(pageNum));
      params.set("page_size", String(PAGE_SIZE));

      const r     = await api.get<any>(`/models/popular?${params}`);
      const raw   = r.data || r;
      const items = normalizePopularModels(raw.items ?? []);

      setHasMore(items.length >= PAGE_SIZE);
      setModels(prev => append ? [...prev, ...items] : items);
    } catch (e: any) {
      console.error(e);
      toast(e.message || "Failed to load models", "error");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  // ── Debounced filter effect → resets to page 1 ─────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => {
      filtersRef.current = { search, capability };
      setPage(1);
      setHasMore(true);
      fetchModels(1, search, capability, false);
    }, 300);
    return () => clearTimeout(t);
  }, [search, capability]);

  // ── Load next page when page increments ────────────────────────────────────
  useEffect(() => {
    if (page === 1) return;
    fetchModels(page, filtersRef.current.search, filtersRef.current.capability, true);
  }, [page]);

  // ── IntersectionObserver: sentinel triggers next page ──────────────────────
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !loadingMore && !loading) {
          setPage(prev => prev + 1);
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loading]);

  // ── Fetch tags with in-memory cache ────────────────────────────────────────
  const fetchTags = async (modelId: string) => {
    const baseId = modelId.split(":")[0];

    if (tagsCache.current[baseId]) {
      setTags(tagsCache.current[baseId]);
      setTagsLoading(false);
      return;
    }

    try {
      const res    = await api.get(`/models/tags?model=${baseId}`);
      const raw    = res?.data ?? res;
      const parsed: ModelTag[] =
        Array.isArray(raw)        ? raw :
        Array.isArray(raw?.items) ? raw.items :
        Array.isArray(raw?.tags)  ? raw.tags  : [];

      tagsCache.current[baseId] = parsed;
      setTags(parsed);
    } catch (e: any) {
      console.error(e);
      toast(e.message || "Failed to load tags", "error");
      setTags([]);
    } finally {
      setTagsLoading(false);
    }
  };

  const handleCardClick = (m: RichModel) => {
    const baseId = m.id.split(":")[0];
    const cached = tagsCache.current[baseId];
    if (cached) { setTags(cached); setTagsLoading(false); }
    else         { setTags([]);    setTagsLoading(true);  }
    setSelectedModel(m);
    fetchTags(m.id);
  };

  const pullModel = async (model: string) => {
    try {
      setPulling(model);
      toast(`Pulling ${model}...`, "info");
      await api.post("/models/pull", { model });
      toast(`Started pulling ${model}`, "success");
    } catch (e: any) {
      console.error(e);
      toast(e.message || "Failed to pull model", "error");
    } finally {
      setPulling(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">◎ Discover Models</div>
          <div className="page-subtitle">
            Model catalog · {models.length} loaded{hasMore ? "+" : ""}
          </div>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="page-body" style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
        <div className="page-inner">

          {/* Filters */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              className="input"
              placeholder="Search models…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width: 240 }}
            />
            <select
              className="select"
              value={capability}
              onChange={e => setCapability(e.target.value)}
            >
              <option value="">All Capabilities</option>
              {TAGS_FILTER.map(c => (
                <option key={c} value={c}>{CAP_ICONS[c]} {c}</option>
              ))}
            </select>
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid-3">
              {[1,2,3,4,5,6].map(i => (
                <div key={i} className="skeleton" style={{ height: 200, borderRadius: 14 }} />
              ))}
            </div>
          ) : models.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">◎</div>
              <div className="empty-state-title">No matches</div>
              <div className="empty-state-subtitle">Try a different search or capability filter</div>
            </div>
          ) : (
            <>
              <div className="grid-3">
                {models.map(m => (
                  <ModelCard key={m.id} model={m} onClick={() => handleCardClick(m)} />
                ))}
              </div>

              {/* Sentinel — IntersectionObserver watches this */}
              <div ref={sentinelRef} style={{ height: 1 }} />

              {loadingMore && (
                <div style={{ display: "flex", justifyContent: "center", padding: "24px 0",
                  gap: 8, color: "var(--text-secondary)", fontSize: 13 }}>
                  <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>◎</span>
                  Loading more…
                </div>
              )}

              {!hasMore && models.length > 0 && (
                <div style={{ textAlign: "center", padding: "24px 0",
                  color: "var(--text-secondary)", fontSize: 12, opacity: 0.5 }}>
                  — {models.length} models loaded —
                </div>
              )}
            </>
          )}

        </div>
      </div>

      {/* MODAL */}
      {selectedModel && (
        <div
          onClick={() => setSelectedModel(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 99999 }}
        >
          <div
            key={selectedModel.id}
            onClick={e => e.stopPropagation()}
            style={{ background: "#111", padding: 24, borderRadius: 14, width: 720,
              maxHeight: "85vh", display: "flex", flexDirection: "column", color: "#fff", gap: 16 }}
          >
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 6 }}>
                  <h2 style={{ margin: 0, fontSize: 18, fontFamily: "var(--font-mono)" }}>{selectedModel.id}</h2>
                  {selectedModel.recommended && <span className="badge badge-accent">★ Recommended</span>}
                </div>
                <p style={{ margin: 0, opacity: 0.65, fontSize: 13, lineHeight: 1.6 }}>
                  {selectedModel.description}
                </p>
              </div>
              <button
                onClick={() => setSelectedModel(null)}
                style={{ background: "none", border: "none", color: "#666", fontSize: 22,
                  cursor: "pointer", padding: "0 0 0 16px", lineHeight: 1 }}
              >×</button>
            </div>

            {/* Meta row */}
            <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--text-secondary)", flexWrap: "wrap" }}>
              {selectedModel.params && selectedModel.params !== "–" && (
                <span>📦 <strong style={{ color: "#e5e5e5" }}>{selectedModel.params}</strong> sizes</span>
              )}
              {selectedModel.pulls && (
                <span>⬇ <strong style={{ color: "#e5e5e5" }}>{selectedModel.pulls}</strong> pulls</span>
              )}
              {selectedModel.tag_count && (
                <span>🏷 <strong style={{ color: "#e5e5e5" }}>{selectedModel.tag_count}</strong> variants</span>
              )}
              {selectedModel.updated && (
                <span>🕐 Updated <strong style={{ color: "#e5e5e5" }}>{selectedModel.updated}</strong></span>
              )}
            </div>

            {/* Capability pills */}
            {(selectedModel.tags || []).length > 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(selectedModel.tags || []).map(tag => (
                  <span key={tag} style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20,
                    background: CAP_COLORS[tag] || "var(--bg-muted)", color: "#fff", fontWeight: 500 }}>
                    {CAP_ICONS[tag]} {tag}
                  </span>
                ))}
              </div>
            )}

            <div style={{ height: 1, background: "#222" }} />

            {/* Tags table */}
            {tagsLoading ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center", color: "var(--text-secondary)", fontSize: 13 }}>
                <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>◎</span>
                Loading variants…
              </div>
            ) : !tags || tags.length === 0 ? (
              <div style={{ opacity: 0.5, fontSize: 13 }}>No variants available</div>
            ) : (
              <div style={{ border: "1px solid #222", borderRadius: 10, fontSize: 13,
                display: "flex", flexDirection: "column", flex: 1, minHeight: 0,
                background: "#0d0d0d", color: "#e5e5e5", overflow: "hidden" }}>
                <div style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr 1.5fr auto",
                  padding: "10px 14px", background: "#161616", fontSize: 11,
                  opacity: 0.6, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                  <div>Variant</div>
                  <div style={{ textAlign: "center" }}>Size</div>
                  <div style={{ textAlign: "center" }}>Context</div>
                  <div style={{ textAlign: "center" }}>Input</div>
                  <div />
                </div>
                <div style={{ overflowY: "auto", maxHeight: "42vh" }}>
                  {tags.map((t, i) => (
                    <div key={t.tag || i} style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr 1.5fr auto",
                      padding: "11px 14px", borderTop: "1px solid #1a1a1a", alignItems: "center",
                      background: i % 2 === 0 ? "#0d0d0d" : "#0f0f0f" }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{t.tag}</div>
                      <div style={{ textAlign: "center", color: "var(--text-secondary)" }}>{t.size || "–"}</div>
                      <div style={{ textAlign: "center", color: "var(--text-secondary)" }}>{t.context || "–"}</div>
                      <div style={{ textAlign: "center", color: "var(--text-secondary)" }}>{t.input || "–"}</div>
                      <div style={{ display: "flex", justifyContent: "flex-end" }}>
                        <button className="btn btn-primary btn-sm"
                          disabled={pulling === t.tag} onClick={() => pullModel(t.tag)}>
                          {pulling === t.tag ? "Pulling…" : "⬇ Pull"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        :root {
          --badge-tools:    #1d6045;
          --badge-thinking: #4a3070;
          --badge-vision:   #1a4a6e;
          --badge-audio:    #6e3a1a;
        }
      `}</style>
    </div>
  );
}

function ModelCard({ model, onClick }: { model: RichModel; onClick: () => void }) {
  return (
    <div className="card" onClick={onClick}
      style={{ cursor: "pointer", display: "flex", flexDirection: "column",
        borderColor: model.recommended ? "var(--border-accent)" : "var(--border-soft)",
        transition: "all 0.15s ease" }}>
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>

        {/* Top row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          {model.recommended ? <span className="badge badge-accent">★ Recommended</span> : <span />}
          {model.updated && (
            <span style={{ fontSize: 10, color: "var(--text-secondary)", opacity: 0.6, whiteSpace: "nowrap" }}>
              {model.updated}
            </span>
          )}
        </div>

        {/* Name */}
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, lineHeight: 1.3 }}>
          {model.id}
        </div>

        {/* Description — clamped to 3 lines */}
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6, flex: 1,
          display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {model.description}
        </div>

        {/* Capability badges */}
        {(model.tags || []).length > 0 && (
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
            {(model.tags || []).map(tag => (
              <span key={tag} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 20,
                background: CAP_COLORS[tag] || "var(--bg-muted)", color: "#ccc", fontWeight: 500 }}>
                {CAP_ICONS[tag]} {tag}
              </span>
            ))}
          </div>
        )}

        {/* Footer meta */}
        <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-secondary)", opacity: 0.7, flexWrap: "wrap", marginTop: 2 }}>
          {model.params && model.params !== "–" && <span title="Available sizes">📦 {model.params}</span>}
          {model.pulls    && <span title="Total pulls">⬇ {model.pulls}</span>}
          {model.tag_count && <span title="Tag variants">🏷 {model.tag_count} variants</span>}
        </div>

      </div>
    </div>
  );
}