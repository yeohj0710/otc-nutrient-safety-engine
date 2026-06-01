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
    <main className="min-h-screen bg-[linear-gradient(180deg,_#f7f4ee_0%,_#f2efe7_100%)] px-4 py-8 md:px-6">
      <div className="mx-auto max-w-3xl rounded-[2rem] border border-red-200 bg-white p-8 shadow-sm">
        <p className="text-xs uppercase tracking-[0.24em] text-red-700">
          Error
        </p>
        <h1 className="mt-2 text-[1.55rem] font-semibold text-stone-950">
          페이지를 불러오지 못했습니다.
        </h1>
        <p className="mt-3 text-sm leading-6 text-stone-700">
          예기치 않은 오류가 발생했습니다. 개인 정보는 브라우저에 노출하지
          않으며, 다시 시도하면 일시적인 문제는 복구될 수 있습니다.
        </p>
        <button
          type="button"
          onClick={() => unstable_retry()}
          className="mt-6 rounded-full bg-stone-950 px-5 py-[0.62rem] text-[0.84rem] font-medium text-white"
        >
          다시 시도
        </button>
      </div>
    </main>
  );
}
