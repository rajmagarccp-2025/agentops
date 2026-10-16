"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="loading">
      <h1>Something interrupted this view</h1>
      <p>Retry the request to reconnect to the operations console.</p>
      <button className="primary-button" onClick={reset}>Retry</button>
    </main>
  );
}