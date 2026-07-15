import Image from "next/image";
import Link from "next/link";

import {
  projectAffiliation,
  projectAuthor,
} from "@/src/lib/project-identity";
import { siteName } from "@/src/lib/site";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col bg-[#f3f5f7] text-[#17223b]">
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-50 -translate-y-20 rounded-lg bg-[#17223b] px-4 py-2 text-sm font-bold text-white transition-transform focus:translate-y-0"
      >
        본문 바로가기
      </a>
      <header className="border-b border-[#e1e5ea] bg-white px-4 sm:px-6">
        <div className="mx-auto flex min-h-16 w-full max-w-[1320px] items-center justify-between gap-4">
          <Link href="/" className="flex min-w-0 items-center gap-2.5" aria-label={`${siteName} 홈`}>
            <Image
              src="/yonsei-logo.svg"
              alt="연세대학교 로고"
              width={30}
              height={30}
              className="h-[30px] w-[30px] shrink-0 object-contain"
            />
            <span className="min-w-0">
              <strong className="block truncate text-[13px] font-extrabold tracking-[-0.02em]">OTC 함께복용 점검</strong>
              <small className="hidden text-[9px] font-semibold text-[#7b8493] sm:block">{projectAffiliation}</small>
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-[11px] font-bold text-[#667085]" aria-label="주요 메뉴">
            <Link href="/#checker" className="rounded-lg px-3 py-2 hover:bg-[#f3f5f7] hover:text-[#17223b]">약 점검</Link>
            <Link href="/research-v3" className="rounded-lg px-3 py-2 hover:bg-[#f3f5f7] hover:text-[#17223b]">연구 정보</Link>
          </nav>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="border-t border-[#e1e5ea] bg-white px-4 py-6 sm:px-6">
        <div className="mx-auto flex w-full max-w-[1320px] flex-col justify-between gap-2 text-[10px] font-medium leading-5 text-[#7b8493] sm:flex-row">
          <span>연구용 시스템 · 의료적 진단이나 처방을 대신하지 않습니다.</span>
          <span>{projectAuthor} · {projectAffiliation}</span>
        </div>
      </footer>
    </div>
  );
}
