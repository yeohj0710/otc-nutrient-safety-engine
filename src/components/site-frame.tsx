import Image from "next/image";
import Link from "next/link";

import {
  projectAffiliation,
  projectAuthor,
  projectSignature,
} from "@/src/lib/project-identity";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col bg-[#f5f7fb] text-[#191f28]">
      <header className="bg-white/92 px-5 py-4 shadow-[0_1px_0_rgba(0,0,0,0.06)] backdrop-blur sm:px-8">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <Image
              src="/yonsei-logo.svg"
              alt="연세대학교 로고"
              width={32}
              height={32}
              className="h-8 w-8 shrink-0 object-contain"
              priority
            />
            <span className="truncate text-sm font-semibold">
              {projectSignature}
            </span>
          </Link>
          <span className="hidden text-sm font-medium text-[#6b7684] md:block">
            {projectAuthor}
          </span>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="px-5 py-8 sm:px-8">
        <div className="mx-auto flex w-full max-w-6xl justify-between gap-4 text-xs text-[#8b95a1]">
          <span>{projectAffiliation}</span>
          <span>{projectAuthor}</span>
        </div>
      </footer>
    </div>
  );
}
