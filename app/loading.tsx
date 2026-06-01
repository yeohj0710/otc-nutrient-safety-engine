export default function Loading() {
  return (
    <main
      aria-busy="true"
      aria-live="polite"
      className="min-h-screen bg-[linear-gradient(180deg,_#f7f4ee_0%,_#f2efe7_100%)] px-4 py-8 md:px-6"
    >
      <div className="page-shell animate-pulse space-y-6">
        <div className="h-16 rounded-full bg-stone-200/70" />
        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="h-[720px] rounded-[2rem] bg-stone-200/70" />
          <div className="space-y-6">
            <div className="h-40 rounded-[2rem] bg-stone-200/70" />
            <div className="h-56 rounded-[2rem] bg-stone-200/70" />
            <div className="h-56 rounded-[2rem] bg-stone-200/70" />
          </div>
        </div>
      </div>
    </main>
  );
}
