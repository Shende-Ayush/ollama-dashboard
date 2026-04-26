const KEY = "ollama_api_key";
export const getApiKey = (): string => localStorage.getItem(KEY) || "";
export const setApiKey = (v: string): void => localStorage.setItem(KEY, v);
export const getAuthHeaders = (): Record<string, string> => {
  const k = getApiKey(); return k ? { Authorization: `Bearer ${k}` } : {};
};
