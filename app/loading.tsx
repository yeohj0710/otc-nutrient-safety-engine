export default function Loading() {
  return (
    <main
      aria-busy="true"
      aria-live="polite"
      className="min-h-screen bg-[#f3f5f7] px-4 py-8 md:px-6"
    >
      <div className="mx-auto max-w-[1080px] animate-pulse space-y-6">
        <div className="h-14 rounded-[18px] bg-slate-200/80" />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.95fr)]">
          <div className="space-y-6">
            <div className="h-64 rounded-[18px] bg-slate-200/80" />
            <div className="h-48 rounded-[18px] bg-slate-200/70" />
          </div>
          <div className="h-[520px] rounded-[18px] bg-slate-200/70" />
        </div>
      </div>
    </main>
  );
}
