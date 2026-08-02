"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { MouseEvent } from "react";

import {
  projectAffiliation,
  projectAuthor,
} from "@/src/lib/project-identity";
import { siteName } from "@/src/lib/site";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  function focusMainContent(event: MouseEvent<HTMLAnchorElement>) {
    const target = document.getElementById("main-content");

    if (!target) return;

    event.preventDefault();
    target.tabIndex = -1;
    target.focus();
  }

  return (
    <div className="site-frame">
      <a
        href="#main-content"
        className="skip-link"
        onClick={focusMainContent}
      >
        본문 바로가기
      </a>
      <header className="site-header">
        <div className="site-header-inner">
          <Link
            href="/"
            className="site-brand"
            aria-label={`${siteName} 홈`}
          >
            <Image
              src="/yonsei-logo.svg"
              alt=""
              aria-hidden="true"
              width={32}
              height={32}
              className="site-brand-logo"
            />
            <span className="site-brand-copy">
              <strong className="site-brand-title">OTC 함께복용 점검</strong>
              <small className="site-brand-affiliation">
                {projectAffiliation}
              </small>
            </span>
          </Link>
          <nav className="site-nav" aria-label="주요 메뉴">
            <Link
              href="/#checker"
              className="site-nav-link"
              aria-current={pathname === "/" ? "page" : undefined}
            >
              약 점검
            </Link>
            <Link
              href="/research"
              className="site-nav-link"
              aria-current={pathname === "/research" ? "page" : undefined}
            >
              연구 정보
            </Link>
          </nav>
        </div>
      </header>

      <div className="site-content">{children}</div>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <span>연구용 시스템 · 의료적 진단이나 처방을 대신하지 않습니다.</span>
          <span>
            {projectAuthor} · {projectAffiliation}
          </span>
        </div>
      </footer>
    </div>
  );
}
