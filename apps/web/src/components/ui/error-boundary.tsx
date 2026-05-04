"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onRetry?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-16 text-center">
          <AlertTriangle className="mb-4 h-10 w-10 text-destructive" />
          <h3 className="text-lg font-semibold">Une erreur est survenue</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            {this.state.error?.message ?? "Erreur inattendue"}
          </p>
          <Button variant="outline" className="mt-6 gap-2" onClick={this.handleRetry}>
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
