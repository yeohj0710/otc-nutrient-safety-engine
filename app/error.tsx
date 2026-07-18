"use client";

import { useEffect } from "react";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error("[app-error]", {
      message: error.message,
      digest: error.digest ?? null,
    });
  }, [error]);

  return (
    <main className="app-page min-h-screen px-4 py-8 md:px-6 md:py-10">
      <div className="page-shell-narrow">
        <section className="surface-card-strong rounded-[2.2rem] px-7 py-9 md:px-10 md:py-12">
          <p className="eyebrow">Error</p>
          <h1 className="mt-5 font-display text-[clamp(1.72rem,3.25vw,2.65rem)] leading-[1.03] tracking-[-0.04em] text-foreground">
            페이지를 불러오지 못했습니다.
          </h1>
          <p className="measure-copy mt-5 text-base leading-7 text-muted">
            예기치 않은 오류가 발생했습니다. 개인 정보는 브라우저에 노출하지
            않으며, 다시 시도하면 일시적인 문제는 복구될 수 있습니다.
          </p>
          <button
            type="button"
            onClick={() => unstable_retry()}
            className="mt-8 inline-flex min-h-12 items-center justify-center rounded-full bg-accent px-6 py-[0.68rem] text-[0.84rem] font-medium text-white transition duration-200 hover:-translate-y-0.5 hover:bg-accent-strong"
          >
            다시 시도
          </button>
        </section>
      </div>
    </main>
  );
}
