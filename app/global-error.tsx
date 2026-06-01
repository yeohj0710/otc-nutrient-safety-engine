"use client";

import "./globals.css";

export default function GlobalError({
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-[linear-gradient(180deg,_#f7f4ee_0%,_#f2efe7_100%)] px-4 py-8 md:px-6">
        <main className="mx-auto max-w-3xl rounded-[2rem] border border-red-200 bg-white p-8 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-red-700">
            Global Error
          </p>
          <h1 className="mt-2 text-[1.55rem] font-semibold text-stone-950">
            앱을 정상적으로 렌더링하지 못했습니다.
          </h1>
          <p className="mt-3 text-sm leading-6 text-stone-700">
            루트 수준에서 오류가 발생했습니다. 다시 시도해도 문제가 계속되면
            배포 환경과 빌드 로그를 확인해 주세요.
          </p>
          <button
            type="button"
            onClick={() => unstable_retry()}
            className="mt-6 rounded-full bg-stone-950 px-5 py-[0.62rem] text-[0.84rem] font-medium text-white"
          >
            다시 시도
          </button>
        </main>
      </body>
    </html>
  );
}
