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

      {/* 머리띠. 공공 누리집이 맨 위에 두는 한 줄을 같은 자리에 두고,
          운영 주체를 그대로 적는다. */}
      <div className="masthead">
        <div className="masthead-inner">
          <p className="masthead-text">
            <Image src="/yonsei-logo.svg" alt="" aria-hidden="true" width={16} height={16} />
            <span>이 누리집은 {projectAffiliation}에서 운영하는 졸업논문 연구 누리집입니다.</span>
          </p>
          <nav className="masthead-links" aria-label="보조 메뉴">
            <Link href="/research">연구 정보</Link>
            <Link href="/#guide">이용 안내</Link>
            <a
              href="https://github.com/yeohj0710/otc-nutrient-safety-engine"
              target="_blank"
              rel="noreferrer"
            >
              재현 자료
              <span className="sr-only"> 새 창</span>
            </a>
          </nav>
        </div>
      </div>

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
              width={36}
              height={36}
              className="site-brand-logo"
              priority
            />
            <span className="site-brand-copy">
              <strong className="site-brand-title">일반의약품 안전성 조회</strong>
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
              함께복용 점검
            </Link>
            <Link
              href="/research"
              className="site-nav-link"
              aria-current={pathname === "/research" ? "page" : undefined}
            >
              연구 정보
            </Link>
            <Link href="/#guide" className="site-nav-link">
              이용 안내
            </Link>
          </nav>
        </div>
      </header>

      <div className="site-content">{children}</div>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <nav className="site-footer-links" aria-label="바닥글 메뉴">
            <Link href="/#guide">이용 안내</Link>
            <Link href="/research">연구 정보</Link>
            <Link href="/#checker">함께복용 점검</Link>
            <a
              href="https://nedrug.mfds.go.kr/"
              target="_blank"
              rel="noreferrer"
            >
              식약처 의약품안전나라
            </a>
            <a
              href="https://github.com/yeohj0710/otc-nutrient-safety-engine"
              target="_blank"
              rel="noreferrer"
            >
              재현 자료
            </a>
          </nav>
          <div className="site-footer-body">
            <p className="site-footer-brand">
              <Image src="/yonsei-logo.svg" alt="" aria-hidden="true" width={28} height={28} />
              {siteName}
            </p>
            <div className="site-footer-info">
              <span>{projectAffiliation}</span>
              <span>연구 수행 {projectAuthor}</span>
              <span>자료 출처 식품의약품안전처 의약품 허가사항, PubMed 문헌</span>
            </div>
            <div className="site-footer-info">
              <span>연구용 시스템입니다.</span>
              <span>의료적 진단이나 처방, 약사 상담을 대체하지 않습니다.</span>
            </div>
          </div>
          <p className="site-footer-copy">
            Copyright © Yonsei University College of Pharmacy, Clinical Pharmacy Lab. All Rights Reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
