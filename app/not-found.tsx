import Link from "next/link";

export default function NotFound() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="app-page min-h-screen px-4 py-16 md:px-6 md:py-24"
    >
      <div className="page-shell-narrow text-center">
        <p className="eyebrow justify-center">페이지 없음</p>
        <h1 className="mt-4 text-[clamp(1.5rem,3vw,2.25rem)] font-bold leading-tight tracking-[-0.02em] text-foreground">
          요청하신 페이지를 찾을 수 없습니다.
        </h1>
        <p className="mx-auto mt-4 max-w-[40rem] text-base leading-7 text-muted">
          주소가 바뀌었거나 현재 인덱스에 포함되지 않은 항목입니다.
          점검 화면이나 연구 정보에서 다시 찾을 수 있습니다.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/research" className="gov-btn-secondary">
            연구 정보
          </Link>
          <Link href="/" className="gov-btn">
            점검 화면으로
          </Link>
        </div>
      </div>
    </main>
  );
}
