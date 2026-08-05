export default function Loading() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      aria-busy="true"
      className="route-loading"
    >
      <p className="sr-only" role="status" aria-live="polite">
        화면을 불러오는 중…
      </p>
      <div className="route-loading-shell" aria-hidden="true">
        <div className="loading-skeleton route-loading-bar" />
        <div className="route-loading-grid">
          <div className="route-loading-column">
            <div className="loading-skeleton route-loading-card route-loading-card-large" />
            <div className="loading-skeleton route-loading-card route-loading-card-small" />
          </div>
          <div className="loading-skeleton route-loading-card route-loading-result" />
        </div>
      </div>
    </main>
  );
}
