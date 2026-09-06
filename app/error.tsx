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
    <main
      id="main-content"
      tabIndex={-1}
      className="app-page min-h-screen px-4 py-16 md:px-6 md:py-24"
    >
      <div className="page-shell-narrow text-center">
        <p className="eyebrow justify-center">오류</p>
        <h1 className="mt-4 text-[clamp(1.5rem,3vw,2.25rem)] font-bold leading-tight tracking-[-0.02em] text-foreground">
          페이지를 불러오지 못했습니다.
        </h1>
        <p className="mx-auto mt-4 max-w-[40rem] text-base leading-7 text-muted">
          예기치 않은 오류가 발생했습니다. 입력한 내용은 브라우저 밖으로 보내지 않았습니다.
          다시 시도하면 일시적인 문제는 풀립니다.
        </p>
        <button
          type="button"
          onClick={() => unstable_retry()}
          className="gov-btn mt-8"
        >
          다시 시도
        </button>
      </div>
    </main>
  );
}
