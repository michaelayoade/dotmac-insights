'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button, LinkButton } from '@/components/ui';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  showDetails?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * React Error Boundary component for catching render errors.
 * Use this to wrap components that might throw during rendering.
 *
 * @example
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * <ErrorBoundary fallback={<CustomError />}>
 *   <MyComponent />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error);
      console.error('Component stack:', errorInfo.componentStack);
    }

    // Call optional error handler
    this.props.onError?.(error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-[300px] flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-slate-card border border-slate-border rounded-xl p-6 text-center">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-coral-alert/10 border border-coral-alert/30 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-coral-alert" />
            </div>

            <h2 className="text-lg font-semibold text-foreground mb-2">Something went wrong</h2>
            <p className="text-slate-muted text-sm mb-4">
              An error occurred while rendering this component.
            </p>

            {(this.props.showDetails || process.env.NODE_ENV === 'development') &&
              this.state.error && (
                <div className="mb-4 p-3 bg-slate-elevated rounded-lg text-left overflow-auto max-h-32">
                  <p className="text-xs text-coral-alert font-mono break-all">
                    {this.state.error.message}
                  </p>
                </div>
              )}

            <div className="flex gap-2 justify-center">
              <Button size="sm" icon={RefreshCw} onClick={this.handleReset}>
                Try again
              </Button>
              <LinkButton href="/" variant="secondary" size="sm" icon={Home} className="text-sm">
                Home
              </LinkButton>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * HOC to wrap a component with an error boundary
 *
 * @example
 * const SafeComponent = withErrorBoundary(MyComponent);
 */
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
): React.FC<P> {
  const displayName = WrappedComponent.displayName || WrappedComponent.name || 'Component';

  const ComponentWithErrorBoundary: React.FC<P> = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  );

  ComponentWithErrorBoundary.displayName = `withErrorBoundary(${displayName})`;

  return ComponentWithErrorBoundary;
}

/**
 * Hook to programmatically trigger error boundary.
 * Useful for handling async errors in event handlers.
 *
 * @example
 * function MyComponent() {
 *   const throwError = useErrorHandler();
 *
 *   const handleClick = async () => {
 *     try {
 *       await riskyOperation();
 *     } catch (err) {
 *       throwError(err);
 *     }
 *   };
 * }
 */
export function useErrorHandler(): (error: unknown) => void {
  const [, setError] = React.useState<Error | null>(null);

  return React.useCallback((error: unknown) => {
    setError(() => {
      // This will trigger the error boundary
      throw error instanceof Error ? error : new Error(String(error));
    });
  }, []);
}

export default ErrorBoundary;
