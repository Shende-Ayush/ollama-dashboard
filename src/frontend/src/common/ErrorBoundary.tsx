import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const retriesExhausted = this.state.retryCount >= 2;

      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          padding: 40,
          gap: 16,
          color: "var(--text-secondary)",
        }}>
          <div style={{ fontSize: 48 }}>&#9888;</div>
          <h2 style={{ margin: 0, color: "var(--text-primary)" }}>
            {retriesExhausted ? "This page keeps crashing" : "Something went wrong"}
          </h2>
          <p style={{ margin: 0, fontSize: 14, textAlign: "center", maxWidth: 400 }}>
            {retriesExhausted
              ? "This page keeps crashing. Please go back to the home page."
              : (this.state.error?.message || "An unexpected error occurred")}
          </p>
          {retriesExhausted ? (
            <a href="/" className="btn btn-primary">Go Home</a>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() => this.setState(prev => ({ hasError: false, error: null, retryCount: prev.retryCount + 1 }))}
            >
              Try Again
            </button>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
