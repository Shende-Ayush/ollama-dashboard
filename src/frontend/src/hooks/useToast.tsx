import React, { createContext, useCallback, useContext, useState, ReactNode } from "react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void;
}

const ToastCtx = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 3500);
  }, []);

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="toast-container">
        {toasts.map((toastItem) => (
          <div key={toastItem.id} className={`toast ${toastItem.type}`}>
            <span>{toastItem.type === "success" ? "✓" : toastItem.type === "error" ? "✕" : "ℹ"}</span>
            <span>{toastItem.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
