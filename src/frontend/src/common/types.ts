export type Role = "user" | "assistant";
export interface ChatMessage { id: string; role: Role; content: string; token_count?: number; model_name?: string; created_at?: string; }
export interface Conversation { id: string; title: string; model_name: string; context_window: number; total_tokens: number; message_count?: number; created_at: string; updated_at: string; is_archived: boolean; messages?: ChatMessage[]; }
export interface InstalledModel { name: string; model_id?: string; size: number; size_gb: number; quantization?: string; family?: string; parameter_size?: string; modified_at?: string; downloaded?: boolean; pulled_at?: string|null; download?: PullProgress|null; }
export interface RunningModel { name: string; size_vram?: string; processor?: string; details?: { quantization_level?: string }; }
export interface PopularModel { id: string; family: string; size_gb: number; params: string; description: string; tags: string[]; recommended: boolean; installed: boolean; }
export interface SystemStats { cpu_percent: number|null; ram_used_mb: number|null; ram_total_mb: number|null; gpu_utilization: number|null; vram_used_mb: number|null; vram_total_mb: number|null; }
export interface AnalyticsOverview { total_requests: number; tokens_input: number; tokens_output: number; total_tokens: number; total_conversations: number; avg_latency_ms: number; error_rate_percent: number; }
export interface PaginatedResponse<T> { page: { pg_no: number; pg_size: number; total_records: number; total_pg: number }; items: T[]; }
export interface PullProgress { request_id?: string; model?: string; model_name?: string; status: string; completed: number; total: number; percent: number; speed_mbps: number; eta_seconds: number|null; size_gb: number|null; error?: string|null; }
