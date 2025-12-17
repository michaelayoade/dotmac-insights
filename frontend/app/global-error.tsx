'use client';

import { useEffect } from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

/**
 * Global error boundary for the root layout.
 * This catches errors that occur in the root layout itself.
 * Must include its own <html> and <body> tags.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error reporting service
    console.error('Global error:', error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0 }}>
        <div
          style={{
            minHeight: '100vh',
            backgroundColor: '#0f1419',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            fontFamily:
              'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          <div
            style={{
              maxWidth: '400px',
              width: '100%',
              backgroundColor: '#1a2332',
              border: '1px solid #2d3a4f',
              borderRadius: '12px',
              padding: '32px',
              textAlign: 'center',
            }}
          >
            {/* Icon */}
            <div
              style={{
                width: '64px',
                height: '64px',
                margin: '0 auto 24px',
                borderRadius: '50%',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <AlertOctagon
                style={{ width: '32px', height: '32px', color: '#ef4444' }}
              />
            </div>

            {/* Title */}
            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#f1f5f9',
                margin: '0 0 8px',
              }}
            >
              Critical Error
            </h1>

            {/* Description */}
            <p
              style={{
                fontSize: '14px',
                color: '#64748b',
                margin: '0 0 24px',
                lineHeight: 1.5,
              }}
            >
              A critical error occurred in the application. Please try refreshing
              the page. If the problem persists, contact support.
            </p>

            {/* Error details in development */}
            {process.env.NODE_ENV === 'development' && error.message && (
              <div
                style={{
                  marginBottom: '24px',
                  padding: '12px',
                  backgroundColor: '#243042',
                  borderRadius: '8px',
                  textAlign: 'left',
                }}
              >
                <p
                  style={{
                    fontSize: '11px',
                    color: '#64748b',
                    margin: '0 0 4px',
                  }}
                >
                  Error details:
                </p>
                <p
                  style={{
                    fontSize: '12px',
                    color: '#ef4444',
                    margin: 0,
                    fontFamily: 'monospace',
                    wordBreak: 'break-all',
                  }}
                >
                  {error.message}
                </p>
                {error.digest && (
                  <p
                    style={{
                      fontSize: '11px',
                      color: '#64748b',
                      margin: '8px 0 0',
                    }}
                  >
                    Digest: {error.digest}
                  </p>
                )}
              </div>
            )}

            {/* Actions */}
            <div
              style={{
                display: 'flex',
                gap: '12px',
                justifyContent: 'center',
              }}
            >
              <button
                onClick={reset}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: '#0d9488',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <RefreshCw style={{ width: '16px', height: '16px' }} />
                Try again
              </button>
              <button
                onClick={() => (window.location.href = '/')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: '#243042',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
