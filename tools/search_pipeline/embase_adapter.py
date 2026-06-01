from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .ris_parser import parse_ris_file
from .schemas import RETRIEVED_RECORD_COLUMNS, SEARCH_RUN_COLUMNS, RetrievedRecord, SearchRun
from .storage import (
    SYSTEMATIC_SEARCH_DIR,
    append_csv_rows,
    ensure_layout,
    stable_hash,
    timestamp_id,
    to_repo_relative,
    upsert_csv_rows,
)

EMBASE_QUICK_SEARCH_URL = "https://www.embase.com/search/quick"


class EmbaseLoginRequired(RuntimeError):
    pass


class EmbaseAutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbaseResult:
    search_run: SearchRun
    records: list[RetrievedRecord]
    ris_path: Path


class EmbaseAdapter:
    def __init__(
        self,
        output_root: Path = SYSTEMATIC_SEARCH_DIR,
        profile_dir: Path | None = None,
        headed: bool = True,
    ) -> None:
        self.output_root = output_root
        self.profile_dir = profile_dir or output_root / ".browser" / "embase"
        self.headed = headed

    def run(
        self,
        *,
        target_id: str,
        query: str,
        filters: str = "",
        max_records: int = 500,
        search_date: str | None = None,
        login_wait_seconds: int = 0,
    ) -> EmbaseResult:
        return asyncio.run(
            self._run_async(
                target_id=target_id,
                query=query,
                filters=filters,
                max_records=max_records,
                search_date=search_date,
                login_wait_seconds=login_wait_seconds,
            )
        )

    async def _run_async(
        self,
        *,
        target_id: str,
        query: str,
        filters: str,
        max_records: int,
        search_date: str | None,
        login_wait_seconds: int,
    ) -> EmbaseResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise EmbaseAutomationError(
                "Python Playwright is required. Install requirements and run: playwright install chromium"
            ) from error

        ensure_layout(self.output_root)
        run_id = f"embase_{target_id}_{timestamp_id()}_{stable_hash(query, 8)}"
        run_dir = self.output_root / "raw" / "embase" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=not self.headed,
                accept_downloads=True,
                downloads_path=str(run_dir),
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(EMBASE_QUICK_SEARCH_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)
                await self._wait_for_embase_access(page, login_wait_seconds)
                await self._dismiss_overlays(page)
                await self._submit_query(page, query)
                body_text = await page.locator("body").inner_text(timeout=15000)
                mapped_query, hit_count = _extract_history_query_and_count(body_text)
                selected_count = await self._select_records(page, max_records)
                ris_path = await self._export_ris(page, run_dir, run_id)
            finally:
                await context.close()

        records = parse_ris_file(
            ris_path,
            source="embase",
            target_id=target_id,
            search_run_id=run_id,
        )
        notes = f"selected_records={selected_count}; parsed_records={len(records)}"
        if selected_count and len(records) != selected_count:
            notes += "; parsed_record_count_differs_from_selected_count"

        search_run = SearchRun(
            search_run_id=run_id,
            source="embase",
            target_id=target_id,
            query=query,
            mapped_query=mapped_query,
            filters=filters,
            search_date=search_date or date.today().isoformat(),
            hit_count=hit_count,
            max_records=max_records,
            export_method="embase_browser_ris_export",
            raw_path=to_repo_relative(run_dir),
            status="completed",
            notes=notes,
        )
        append_csv_rows(
            self.output_root / "search_runs.csv",
            [search_run.csv_row(SEARCH_RUN_COLUMNS)],
            SEARCH_RUN_COLUMNS,
        )
        upsert_csv_rows(
            self.output_root / "retrieved_records.csv",
            [record.csv_row(RETRIEVED_RECORD_COLUMNS) for record in records],
            RETRIEVED_RECORD_COLUMNS,
            key_column="record_id",
        )

        return EmbaseResult(search_run=search_run, records=records, ris_path=ris_path)

    async def _wait_for_embase_access(self, page: object, login_wait_seconds: int) -> None:
        if await _looks_like_embase_app(page):
            return
        if login_wait_seconds > 0:
            deadline = asyncio.get_running_loop().time() + login_wait_seconds
            while asyncio.get_running_loop().time() < deadline:
                if await _looks_like_embase_app(page):
                    return
                await page.wait_for_timeout(1000)
        url = getattr(page, "url", "")
        raise EmbaseLoginRequired(
            "Embase search page is not accessible in this browser profile. "
            f"Open the profile and log in first, then rerun. Current URL: {url}"
        )

    async def _dismiss_overlays(self, page: object) -> None:
        for label in [
            "쿠키 수락",
            "Accept cookies",
            "Accept all cookies",
            "Accept",
            "I agree",
            "Close",
        ]:
            try:
                locator = page.get_by_role("button", name=label)
                if await locator.count() > 0:
                    await locator.first.click(timeout=2500)
                    await page.wait_for_timeout(500)
            except Exception:
                continue

    async def _submit_query(self, page: object, query: str) -> None:
        searchbox = page.get_by_role("searchbox").first
        await searchbox.fill(query, timeout=10000)
        await page.wait_for_timeout(1000)

        show_results = page.get_by_role("button", name=re.compile(r"Show results", re.I))
        try:
            if await show_results.count() > 0 and await show_results.first.is_enabled():
                await show_results.first.click(timeout=10000)
            else:
                await searchbox.press("Enter", timeout=10000)
        except Exception:
            await searchbox.press("Enter", timeout=10000)

        await page.wait_for_load_state("domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)
        body_text = await page.locator("body").inner_text(timeout=15000)
        if "results for search" not in body_text.lower() and "search history" not in body_text.lower():
            raise EmbaseAutomationError("Embase did not navigate to a recognizable results page.")

    async def _select_records(self, page: object, max_records: int) -> int:
        await self._try_batch_selection(page, max_records)
        selected = await _selected_count(page)
        if selected:
            return selected

        checkbox = page.get_by_role("checkbox", name=re.compile(r"Select page results", re.I))
        if await checkbox.count() > 0:
            await checkbox.first.check(timeout=5000)
            await page.wait_for_timeout(1000)
            selected = await _selected_count(page)
            if selected:
                return selected

        raise EmbaseAutomationError("Could not select Embase records for export.")

    async def _try_batch_selection(self, page: object, max_records: int) -> None:
        labels = [
            f"First {max_records}",
            f"first {max_records}",
            f"{max_records} records",
            "All results",
            "Select all results",
            "All records",
        ]
        try:
            combo = page.get_by_role("combobox", name=re.compile(r"Batch selection", re.I))
            if await combo.count() == 0:
                return
            await combo.first.click(timeout=3000)
            await page.wait_for_timeout(500)
            for label in labels:
                option = page.get_by_text(label, exact=False)
                if await option.count() > 0:
                    await option.first.click(timeout=3000)
                    await page.wait_for_timeout(1000)
                    return
        except Exception:
            return

    async def _export_ris(self, page: object, run_dir: Path, run_id: str) -> Path:
        export_buttons = page.get_by_role("button", name=re.compile(r"^Export$", re.I))
        count = await export_buttons.count()
        if count == 0:
            raise EmbaseAutomationError("No Embase Export button found.")

        clicked = False
        for index in range(count - 1, -1, -1):
            button = export_buttons.nth(index)
            try:
                if await button.is_enabled():
                    await button.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            raise EmbaseAutomationError("No enabled Embase Export button found.")

        await page.wait_for_timeout(3000)
        dialog = page.get_by_role("dialog")
        if await dialog.count() == 0:
            raise EmbaseAutomationError("Embase export dialog did not open.")

        try:
            export_to = dialog.first.get_by_role("combobox", name=re.compile(r"Export to", re.I))
            if await export_to.count() > 0:
                await export_to.first.select_option(label=re.compile(r"RIS", re.I), timeout=3000)
        except Exception:
            pass

        final_button = dialog.first.get_by_role("button", name=re.compile(r"^Export$", re.I))
        if await final_button.count() == 0:
            final_button = page.get_by_role("button", name=re.compile(r"^Export$", re.I))

        async with page.expect_download(timeout=90000) as download_info:
            await final_button.last.click(timeout=10000)
        download = await download_info.value
        ris_path = run_dir / f"{run_id}.ris"
        await download.save_as(str(ris_path))
        return ris_path


async def _looks_like_embase_app(page: object) -> bool:
    try:
        body_text = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        return False
    app_markers = [
        "Quick",
        "PICO",
        "Search history",
        "Find articles by simple keyword search",
        "Broad search",
    ]
    return any(marker in body_text for marker in app_markers)


async def _selected_count(page: object) -> int:
    try:
        body_text = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        return 0
    match = re.search(r"(\d[\d,]*)\s+selected", body_text, re.I)
    return int(match.group(1).replace(",", "")) if match else 0


def _extract_history_query_and_count(body_text: str) -> tuple[str, int]:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    mapped_query = ""
    hit_count = 0

    for index, line in enumerate(lines):
        if line == "#1" or line.endswith("#1"):
            for candidate in lines[index + 1 : index + 6]:
                if not mapped_query and not _is_integer_text(candidate):
                    mapped_query = candidate
                elif mapped_query and _is_integer_text(candidate):
                    hit_count = int(candidate.replace(",", ""))
                    break
            break

    if not hit_count:
        match = re.search(r"(\d[\d,]*)\s+results for search #1", body_text, re.I)
        if match:
            hit_count = int(match.group(1).replace(",", ""))

    return mapped_query, hit_count


def _is_integer_text(value: str) -> bool:
    return bool(re.fullmatch(r"\d[\d,]*", value))
