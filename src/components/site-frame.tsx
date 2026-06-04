import Image from "next/image";
import Link from "next/link";

import {
  projectAffiliation,
  projectAuthor,
  projectSignature,
} from "@/src/lib/project-identity";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col bg-slate-50">
      <header className="border-b border-slate-800 bg-slate-950 px-4 py-3 text-white sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Link
            href="/"
            className="flex min-w-0 items-center gap-3 text-sm font-medium text-white transition duration-200 hover:text-amber-100"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-none border border-white/20 bg-white">
              <Image
                src="/yonsei-logo.svg"
                alt="연세대학교 로고"
                width={40}
                height={40}
                className="h-9 w-9 object-contain"
                priority
              />
            </span>
            <span className="min-w-0">
              <span className="block text-[0.66rem] font-bold uppercase tracking-[0.2em] text-amber-200">
                성분 함량 판정표
              </span>
              <span className="mt-0.5 block truncate">{projectSignature}</span>
            </span>
          </Link>

          <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 border-l border-white/20 pl-4 text-sm md:min-w-[24rem]">
            <span className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-slate-400">
              소속
            </span>
            <span className="truncate text-slate-100">{projectAffiliation}</span>
            <span className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-slate-400">
              작성자
            </span>
            <span className="truncate font-semibold text-white">
              {projectAuthor}
            </span>
          </div>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="border-t border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
        <div className="mx-auto grid w-full max-w-7xl gap-1 text-xs text-slate-500 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
          <p className="truncate">{projectSignature}</p>
          <p className="truncate md:text-right">
            {projectAffiliation} / {projectAuthor}
          </p>
        </div>
      </footer>
    </div>
  );
}
