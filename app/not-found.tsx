import Link from "next/link";

export default function NotFound() {
  return (
    <main className="app-page min-h-screen px-4 py-8 md:px-6 md:py-10">
      <div className="page-shell-narrow">
        <section className="surface-card-strong rounded-[2.2rem] px-7 py-9 md:px-10 md:py-12">
          <p className="eyebrow">Not Found</p>
          <h1 className="mt-5 font-display text-[clamp(1.72rem,3.25vw,2.65rem)] leading-[1.03] tracking-[-0.04em] text-foreground">
            요청하신 규칙 또는 출처를 찾을 수 없습니다.
          </h1>
          <p className="measure-copy mt-5 text-base leading-7 text-muted">
            링크가 바뀌었거나 현재 인덱스에 포함되지 않은 항목일 수 있습니다.
            메인 탐색 화면이나 출처 브라우저에서 다시 찾는 편이 가장 빠릅니다.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/"
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-accent px-6 py-[0.68rem] text-[0.84rem] font-medium text-white transition duration-200 hover:-translate-y-0.5 hover:bg-accent-strong"
            >
              메인 탐색으로 이동
            </Link>
            <Link
              href="/sources"
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-border-subtle bg-white/76 px-6 py-[0.68rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:bg-white"
            >
              출처 브라우저 열기
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
