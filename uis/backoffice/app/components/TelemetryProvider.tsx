"use client";

import React, { useEffect, useRef, Component } from "react";
import type { ErrorInfo, ReactNode, ReactElement } from "react";
import { usePathname } from "next/navigation";
import { track } from "../services/telemetry";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * React Error Boundary capturing uncaught render errors into telemetry.
 */
class TelemetryErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  public state: ErrorBoundaryState = {
    hasError: false,
  };

  public static getDerivedStateFromError(_error: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    track("frontend_error_captured", {
      errorName: error.name || "ReactRenderError",
      errorMessage: error.message || "Unknown rendering exception",
      stackTraceSnippet: (errorInfo.componentStack || error.stack || "").slice(
        0,
        1000
      ),
      url: typeof window !== "undefined" ? window.location.pathname : "",
      componentName: "TelemetryErrorBoundary",
    });
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="p-6 m-4 bg-red-950 border border-red-800 text-red-100 rounded-lg">
          <h2 className="text-xl font-bold mb-2">Something went wrong</h2>
          <p className="text-sm text-red-300 mb-4">
            An unexpected error occurred. The incident has been recorded for our
            engineering team.
          </p>
          <button
            type="button"
            onClick={(): void => this.setState({ hasError: false })}
            className="px-4 py-2 bg-red-800 hover:bg-red-700 text-white rounded font-medium transition"
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * Inner component observing route changes and global unhandled rejections/errors.
 */
function TelemetryListener({ children }: { children: ReactNode }): ReactElement {
  const pathname = usePathname();
  const prevPathRef = useRef<string | null>(null);
  const navStartRef = useRef<number>(
    typeof performance !== "undefined" ? performance.now() : Date.now()
  );

  useEffect(() => {
    const handleGlobalError = (event: ErrorEvent): void => {
      track("frontend_error_captured", {
        errorName: event.error?.name || "WindowError",
        errorMessage: event.message || "Uncaught window error",
        stackTraceSnippet: (event.error?.stack || `${event.filename}:${event.lineno}`).slice(
          0,
          1000
        ),
        url: typeof window !== "undefined" ? window.location.pathname : "",
        componentName: "WindowGlobal",
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent): void => {
      const reason = event.reason;
      const message =
        typeof reason === "string"
          ? reason
          : reason?.message || "Unhandled promise rejection";
      const stack = reason?.stack || "";

      track("frontend_error_captured", {
        errorName: reason?.name || "UnhandledPromiseRejection",
        errorMessage: message,
        stackTraceSnippet: stack.slice(0, 1000),
        url: typeof window !== "undefined" ? window.location.pathname : "",
        componentName: "PromiseGlobal",
      });
    };

    window.addEventListener("error", handleGlobalError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleGlobalError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  useEffect(() => {
    if (prevPathRef.current !== null && prevPathRef.current !== pathname) {
      const now =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const durationMs = Math.round(now - navStartRef.current);

      track("section_navigation_tracked", {
        sourceSection: prevPathRef.current,
        destinationSection: pathname,
        navigationDurationMs: durationMs,
      });
    }

    prevPathRef.current = pathname;
    navStartRef.current =
      typeof performance !== "undefined" ? performance.now() : Date.now();
  }, [pathname]);

  return <>{children}</>;
}

/**
 * Global Telemetry Provider wrapping the application root.
 * @param props Root provider properties.
 * @returns React element with telemetry boundaries and lifecycle listeners.
 */
export default function TelemetryProvider({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  return (
    <TelemetryErrorBoundary>
      <TelemetryListener>{children}</TelemetryListener>
    </TelemetryErrorBoundary>
  );
}
