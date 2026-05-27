"use client";

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary for catching runtime errors in component trees.
 * Wrap dashboard views or data-heavy components to prevent full-page crashes.
 *
 * Usage:
 *   <ErrorBoundary fallback={<p>Something went wrong.</p>}>
 *     <DashboardView />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
          <div className="text-red-500 text-4xl mb-4" aria-hidden="true">
            ⚠
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
            حدث خطأ غير متوقع
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 max-w-md">
            {this.state.error?.message || "حدث خطأ أثناء تحميل البيانات. يرجى المحاولة مرة أخرى."}
          </p>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            إعادة المحاولة
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
