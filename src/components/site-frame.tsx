import Image from "next/image";
import Link from "next/link";

import {
  projectAffiliation,
  projectAuthor,
  projectSignature,
} from "@/src/lib/project-identity";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="px-4 pt-3 sm:px-6 lg:px-6">
        <div className="page-shell">
          <div className="site-masthead rounded-[1.1rem] px-4 py-2.5">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <Link
                href="/"
                className="flex min-w-0 items-center gap-3 text-sm font-medium text-foreground transition duration-200 hover:text-stone-700"
              >
                <span className="site-brand-mark">
                  <Image
                    src="/yonsei-logo.svg"
                    alt="연세대학교 로고"
                    width={42}
                    height={42}
                    className="h-10 w-10 object-contain"
                    priority
                  />
                </span>
                <span className="min-w-0">
                  <span className="site-topbar-label">
                    Research Attribution
                  </span>
                  <span className="block truncate">{projectAffiliation}</span>
                  <span className="mt-0.5 block text-sm font-normal leading-5 text-muted">
                    {projectSignature}
                  </span>
                </span>
              </Link>

              <div className="site-credit-pill md:max-w-[20rem] md:items-end">
                <span className="site-topbar-label md:text-right">
                  Researcher
                </span>
                <span className="text-sm font-medium leading-5 text-foreground md:text-right">
                  {projectAuthor}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="px-4 pb-4 pt-2 sm:px-6 lg:px-6">
        <div className="page-shell">
          <div className="site-footer-panel rounded-[0.95rem] px-4 py-2.5 text-xs text-muted">
            <div className="flex flex-col gap-1.5 md:flex-row md:items-center md:justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <span className="site-brand-mark site-brand-mark-footer">
                  <Image
                    src="/yonsei-logo.svg"
                    alt="연세대학교 로고"
                    width={28}
                    height={28}
                    className="h-6 w-6 object-contain"
                  />
                </span>
                <p className="truncate">{projectSignature}</p>
              </div>
              <p className="truncate md:text-right">
                {projectAffiliation} · {projectAuthor}
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
