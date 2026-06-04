"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { RuleCard } from "@/src/components/rule-card";
import type { AiExplainResponse } from "@/src/lib/ai/schema";
import { cleanDisplayText } from "@/src/lib/display-text";
import {
  normalizeDailyIntakeUnit,
  parseDailyIntakeText,
  parseLongTermUseDays,
  removeDoseAndDurationText,
  toNullableNumber,
} from "@/src/lib/query-input";
import type {
  EngineQuery,
  EngineResponse,
  RuleMatch,
} from "@/src/types/knowledge";

type ExplorerMetadata = {
  meta: {
    sourceCount: number;
    evidenceChunkCount: number;
    safetyRuleCount: number;
  };
  ingredients: Array<{
    id: string;
    label: string;
    aliases: string[];
    category: string | null;
  }>;
  medicationOptions: Array<{
    label: string;
    canonicalValue?: string;
    aliases: string[];
  }>;
  conditionOptions: Array<{
    label: string;
    aliases: string[];
  }>;
  jurisdictions: string[];
  sortOptions: Array<{ value: string; label: string }>;
};

type ExplorerValueOption = {
  id?: string;
  label: string;
  canonicalValue?: string;
  aliases?: string[];
};

function getExplorerSearchTerms(option: ExplorerValueOption) {
  return [
    option.label,
    option.canonicalValue ?? option.label,
    ...(option.aliases ?? []),
  ];
}

const sectionLabels = {
  definitely_matched: "먼저 살펴볼 내용",
  possibly_relevant: "함께 참고할 내용",
  needs_more_info: "몇 가지 더 확인해 주세요",
} as const;

const sectionPreviewCounts = {
  definitely_matched: 6,
  possibly_relevant: 5,
  needs_more_info: 4,
} as const;
const sectionLoadMoreStep = {
  definitely_matched: 6,
  possibly_relevant: 5,
  needs_more_info: 8,
} as const;

const confidenceRank = { high: 4, medium: 3, low: 2, unknown: 1 } as const;
const categoryRank: Record<string, number> = {
  interaction: 1,
  timing_separation: 2,
  disease_caution: 3,
  adverse_effect_signal: 4,
  population_caution: 5,
  monitoring: 6,
  dose_limit: 7,
  quality_signal: 8,
  pregnancy_lactation: 9,
};

const fieldLabelClass =
  "mb-2 block text-[0.82rem] font-bold text-slate-950";
const fieldControlClass =
  "w-full rounded-none border border-slate-300 bg-white px-3 py-2.5 text-[15px] leading-6 text-slate-950 outline-none transition duration-150 placeholder:text-slate-400 focus:border-slate-950 focus:shadow-[0_0_0_3px_rgba(251,191,36,0.35)]";
const fieldGroupClass = "text-sm text-slate-800";
const selectControlClass = `${fieldControlClass} appearance-none pr-12`;
const toggleChipBaseClass =
  "group inline-flex min-h-10 items-center justify-between gap-3 rounded-none border px-3.5 py-2 text-[0.86rem] font-semibold transition-[background-color,border-color,color,box-shadow] duration-250 [transition-timing-function:var(--ease-soft)]";
const primaryButtonClass =
  "whitespace-nowrap rounded-none bg-slate-950 px-5 py-[0.62rem] text-[0.86rem] font-bold text-white transition duration-150 hover:bg-slate-800";
const secondaryButtonClass =
  "whitespace-nowrap rounded-none border border-slate-300 bg-amber-100 px-5 py-[0.62rem] text-[0.86rem] font-bold text-slate-950 transition duration-150 hover:bg-amber-200";
const ghostButtonClass =
  "rounded-none border border-slate-300 bg-white px-4 py-[0.58rem] text-[0.84rem] font-semibold text-slate-800 transition duration-150 hover:bg-slate-100";
const subtleActionButtonClass =
  "rounded-none border border-slate-300 bg-white px-3 py-1.5 text-[0.76rem] font-semibold text-slate-700 transition duration-150 hover:bg-slate-100";
const explorerStorageKey = "nutrition-safety-explorer-state-v3";
const minimumQueryLoadingMs = 900;

type PersistedExplorerState = {
  version: 3;
  form: {
    age: string;
    sex: string;
    pregnancyStatus: string;
    lactationStatus: string;
    smokerStatus: string;
    medications: string;
    conditions: string;
    allergies: string;
    selectedCompounds: string;
    dailyIntakeValue: string;
    dailyIntakeUnit: string;
    longTermUseDays: string;
    ingredientForm: string;
    productName: string;
    coingredients: string;
    jurisdiction: string;
    memo: string;
  };
  filters: {
    severityFilter: string;
    medicationOnly: boolean;
    diseaseOnly: boolean;
    sort: NonNullable<EngineQuery["sort"]>;
  };
  ui: {
    isAdvancedOpen: boolean;
    isExamplesOpen: boolean;
    sectionVisibleCounts: Record<keyof typeof sectionPreviewCounts, number>;
  };
  query: {
    hasQueried: boolean;
    response: EngineResponse | null;
  };
};

type ExplorerProfileDraft = {
  age: string;
  sex: string;
  pregnancyStatus: string;
  lactationStatus: string;
  smokerStatus: string;
  medications: string;
  conditions: string;
  allergies: string;
  selectedCompounds: string;
  dailyIntakeValue: string;
  dailyIntakeUnit: string;
  longTermUseDays: string;
  ingredientForm: string;
  productName: string;
  coingredients: string;
  jurisdiction: string;
  memo: string;
};

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const blankExplorerProfile: ExplorerProfileDraft = {
  age: "",
  sex: "",
  pregnancyStatus: "",
  lactationStatus: "",
  smokerStatus: "",
  medications: "",
  conditions: "",
  allergies: "",
  selectedCompounds: "",
  dailyIntakeValue: "",
  dailyIntakeUnit: "",
  longTermUseDays: "",
  ingredientForm: "",
  productName: "",
  coingredients: "",
  jurisdiction: "",
  memo: "",
};

function buildStarterDraft(
  profile: Partial<ExplorerProfileDraft>,
): ExplorerProfileDraft {
  return {
    ...blankExplorerProfile,
    selectedCompounds: profile.selectedCompounds ?? "",
    medications: profile.medications ?? "",
    conditions: profile.conditions ?? "",
    age: profile.age ?? "",
    sex: profile.sex ?? "",
    pregnancyStatus: profile.pregnancyStatus ?? "",
    lactationStatus: profile.lactationStatus ?? "",
    smokerStatus: profile.smokerStatus ?? "",
    allergies: profile.allergies ?? "",
    dailyIntakeValue: profile.dailyIntakeValue ?? "",
    dailyIntakeUnit: profile.dailyIntakeUnit ?? "",
    longTermUseDays: profile.longTermUseDays ?? "",
    ingredientForm: profile.ingredientForm ?? "",
    productName: profile.productName ?? "",
    coingredients: profile.coingredients ?? "",
    jurisdiction: profile.jurisdiction ?? "",
    memo: profile.memo ?? "",
  };
}

function hasAdvancedProfileValues(profile: ExplorerProfileDraft) {
  return Boolean(
    profile.age ||
    profile.sex ||
    profile.pregnancyStatus ||
    profile.lactationStatus ||
    profile.smokerStatus ||
    profile.allergies ||
    profile.dailyIntakeValue ||
    profile.dailyIntakeUnit ||
    profile.longTermUseDays ||
    profile.ingredientForm ||
    profile.productName ||
    profile.coingredients ||
    profile.jurisdiction ||
    profile.memo,
  );
}

const pregnancyStatusLabels = {
  not_pregnant: "해당 없음",
  pregnant: "임신 중",
} as const;

function normalizePregnancyStatus(value: string) {
  switch (value) {
    case "pregnant":
    case "not_pregnant":
      return value;
    case "trying_to_conceive":
    case "unknown_possible":
      return "pregnant";
    default:
      return "";
  }
}

function getPregnancyStatusLabel(value: string) {
  const normalized = normalizePregnancyStatus(value);
  return normalized
    ? (pregnancyStatusLabels[
        normalized as keyof typeof pregnancyStatusLabels
      ] ?? normalized)
    : "";
}

const defaultExampleProfile: ExplorerProfileDraft = {
  ...blankExplorerProfile,
  selectedCompounds: "비타민 D",
  dailyIntakeValue: "5000",
  dailyIntakeUnit: "iu/day",
  longTermUseDays: "90",
  coingredients: "calcium",
  age: "45",
  sex: "female",
  jurisdiction: "US",
  memo: "고함량 비타민 D와 칼슘을 함께 복용하는 경우입니다.",
};

function normalizeExplorerInput(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[_\-\/()]+/g, " ")
    .replace(/[^a-z0-9가-힣\s]+/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeExplorerLookupKey(value: string) {
  return normalizeExplorerInput(value).replace(/\s+/g, "");
}

function normalizeExplorerTokens(value: string) {
  return normalizeExplorerInput(value)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function matchesExplorerSearchTerm(query: string, candidate: string) {
  const queryKey = normalizeExplorerLookupKey(query);
  const candidateKey = normalizeExplorerLookupKey(candidate);

  if (!queryKey || !candidateKey) {
    return { exact: false, startsWith: false, includes: false };
  }

  if (candidateKey === queryKey) {
    return { exact: true, startsWith: true, includes: true };
  }

  if (candidateKey.startsWith(queryKey)) {
    return { exact: false, startsWith: true, includes: true };
  }

  const queryTokens = normalizeExplorerTokens(query);
  const candidateTokens = normalizeExplorerTokens(candidate);
  const tokenPrefixMatch =
    queryTokens.length > 0 &&
    candidateTokens.length > 0 &&
    queryTokens.every((queryToken) =>
      candidateTokens.some((candidateToken) =>
        candidateToken.startsWith(queryToken),
      ),
    );

  if (tokenPrefixMatch) {
    return { exact: false, startsWith: true, includes: true };
  }

  return {
    exact: false,
    startsWith: false,
    includes: candidateKey.includes(queryKey),
  };
}

function resolveExplorerOption(value: string, options: ExplorerValueOption[]) {
  const searchValues = [
    value,
    removeDoseAndDurationText(value),
  ].filter((item, index, array) => item && array.indexOf(item) === index);

  for (const searchValue of searchValues) {
    const queryKey = normalizeExplorerLookupKey(searchValue);
    if (!queryKey) continue;

    const exactMatch =
      options.find((option) =>
        getExplorerSearchTerms(option).some(
          (candidate) => matchesExplorerSearchTerm(searchValue, candidate).exact,
        ),
      ) ?? null;

    if (exactMatch) {
      return exactMatch;
    }

    const prefixMatches = options.filter((option) =>
      getExplorerSearchTerms(option).some(
        (candidate) =>
          matchesExplorerSearchTerm(searchValue, candidate).startsWith,
      ),
    );

    if (prefixMatches.length === 1) {
      return prefixMatches[0];
    }
  }

  return null;
}

function buildCanonicalEntryDetails(
  value: string,
  options: ExplorerValueOption[],
) {
  const seen = new Set<string>();
  const entries: Array<{ label: string; id?: string; raw: string }> = [];

  for (const token of splitMultiValue(value)) {
    const resolved = resolveExplorerOption(token, options);
    const canonical =
      resolved?.canonicalValue ?? resolved?.label ?? token.trim();
    const key = normalizeExplorerLookupKey(canonical);

    if (!key || seen.has(key)) continue;
    seen.add(key);
    entries.push({ label: canonical, id: resolved?.id, raw: token });
  }

  return entries;
}

function buildCanonicalEntries(value: string, options: ExplorerValueOption[]) {
  return buildCanonicalEntryDetails(value, options).map((entry) => entry.label);
}

function analyzeExplorerField(value: string, options: ExplorerValueOption[]) {
  const recognized: string[] = [];
  const unresolved: string[] = [];
  const seenRecognized = new Set<string>();
  const seenUnresolved = new Set<string>();

  for (const token of splitMultiValue(value)) {
    const resolved = resolveExplorerOption(token, options);

    if (resolved) {
      const key = normalizeExplorerLookupKey(resolved.label);
      if (!seenRecognized.has(key)) {
        seenRecognized.add(key);
        recognized.push(resolved.label);
      }
      continue;
    }

    const trimmed = token.trim();
    const key = normalizeExplorerLookupKey(trimmed);
    if (key && !seenUnresolved.has(key)) {
      seenUnresolved.add(key);
      unresolved.push(trimmed);
    }
  }

  const currentToken = /[,\n;]\s*$/.test(value)
    ? ""
    : (value
        .split(/[\n,;]+/)
        .at(-1)
        ?.trim() ?? "");
  const currentTokenKey = normalizeExplorerLookupKey(currentToken);

  const suggestions =
    currentTokenKey.length > 0
      ? options
          .map((option) => {
            const searchMatches = getExplorerSearchTerms(option).map(
              (candidate) => matchesExplorerSearchTerm(currentToken, candidate),
            );
            const startsWith = searchMatches.some(
              (candidate) => candidate.startsWith,
            );
            const includes = startsWith
              ? true
              : searchMatches.some((candidate) => candidate.includes);

            return {
              option,
              startsWith,
              includes,
            };
          })
          .filter((entry) => entry.includes)
          .filter(
            (entry) =>
              !recognized.some(
                (candidate) =>
                  normalizeExplorerLookupKey(candidate) ===
                  normalizeExplorerLookupKey(entry.option.label),
              ),
          )
          .sort((left, right) => {
            if (left.startsWith !== right.startsWith) {
              return left.startsWith ? -1 : 1;
            }

            return left.option.label.localeCompare(right.option.label, "ko");
          })
          .map((entry) => entry.option)
          .slice(0, 5)
      : [];

  return {
    recognized,
    unresolved,
    suggestions,
  };
}

function applySuggestionToField(currentValue: string, suggestion: string) {
  const lastDelimiterIndex = Math.max(
    currentValue.lastIndexOf(","),
    currentValue.lastIndexOf("\n"),
    currentValue.lastIndexOf(";"),
  );

  const prefix =
    lastDelimiterIndex >= 0
      ? currentValue.slice(0, lastDelimiterIndex + 1).trimEnd()
      : "";

  if (!prefix) {
    return `${suggestion}, `;
  }

  return `${prefix} ${suggestion}, `;
}

function FieldRecognitionAssist({
  recognized,
  unresolved,
  suggestions,
  onSelectSuggestion,
}: {
  recognized: string[];
  unresolved: string[];
  suggestions: ExplorerValueOption[];
  onSelectSuggestion: (label: string) => void;
}) {
  if (
    recognized.length === 0 &&
    unresolved.length === 0 &&
    suggestions.length === 0
  ) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2.5">
      {recognized.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-stone-500">
            자동 인식됨
          </span>
          {recognized.map((item) => (
            <span
              key={`recognized-${item}`}
              className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-900"
            >
              {item}
            </span>
          ))}
        </div>
      ) : null}

      {unresolved.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-stone-500">확인 필요</span>
          {unresolved.map((item) => (
            <span
              key={`unresolved-${item}`}
              className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-900"
            >
              {item}
            </span>
          ))}
        </div>
      ) : null}

      {suggestions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-stone-500">추천 선택</span>
          {suggestions.map((option) => (
            <button
              key={`suggestion-${option.label}`}
              type="button"
              onClick={() => onSelectSuggestion(option.label)}
              className="rounded-full border border-stone-200 bg-white px-3 py-1 text-xs font-medium text-stone-700 transition duration-200 hover:-translate-y-0.5 hover:border-stone-400 hover:bg-stone-50"
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}

    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  disabled?: boolean;
}) {
  return (
    <label className={fieldGroupClass}>
      <span className={fieldLabelClass}>{label}</span>
      <div className="relative">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          className={`${selectControlClass} disabled:cursor-not-allowed disabled:bg-stone-100 disabled:text-stone-400 disabled:hover:border-stone-200`}
        >
          {options.map((option) => (
            <option key={`${label}-${option.value}`} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-stone-400">
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m5 7.5 5 5 5-5" />
          </svg>
        </span>
      </div>
    </label>
  );
}

function CompactSelectChip({
  label,
  value,
  onChange,
  options,
  minWidthClassName = "min-w-[8.5rem]",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  minWidthClassName?: string;
}) {
  return (
    <label
      className={`relative flex min-h-[3.15rem] flex-col justify-center rounded-[1rem] border border-stone-200 bg-white px-3.5 py-2 pr-10 text-sm text-stone-700 transition duration-150 hover:border-stone-300 hover:bg-stone-50/60 ${minWidthClassName}`}
    >
      <span className="shrink-0 text-[0.68rem] font-semibold tracking-[0.01em] text-stone-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-0.5 w-full appearance-none bg-transparent text-sm font-semibold text-stone-900 outline-none"
      >
        {options.map((option) => (
          <option key={`${label}-${option.value}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-stone-400">
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="m5 7.5 5 5 5-5" />
        </svg>
      </span>
    </label>
  );
}

function ToggleChip({
  checked,
  label,
  onChange,
  className = "",
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
  className?: string;
}) {
  return (
    <label
      className={`${toggleChipBaseClass} ${className} ${
        checked
          ? "border-stone-900 bg-stone-950 text-white shadow-[0_10px_24px_rgba(28,25,23,0.12)]"
          : "border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:bg-stone-50/70"
      }`}
    >
      <span>{label}</span>
      <span
        aria-hidden="true"
        className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-[background-color,border-color,color,transform] duration-250 [transition-timing-function:var(--ease-snappy)] ${
          checked
            ? "border-white/40 bg-white/18 text-white"
            : "border-stone-300 bg-stone-100 text-transparent"
        }`}
      >
        <span
          className={`h-2.5 w-2.5 rounded-full transition-[background-color,transform] duration-250 [transition-timing-function:var(--ease-snappy)] ${
            checked ? "bg-white scale-100" : "bg-stone-300/90 scale-90"
          }`}
        />
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="sr-only"
      />
    </label>
  );
}

function ExplorerLoadingSkeleton() {
  return (
    <section
      aria-live="polite"
      className="surface-card overflow-hidden rounded-[1.8rem] px-5 py-5 md:px-6"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex min-h-9 items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 text-xs font-semibold text-emerald-900">
          조회 중
        </span>
        <span className="text-sm font-medium text-muted">
          입력 조건을 바탕으로 근거를 정리하고 있습니다.
        </span>
      </div>

      <div className="mt-4 rounded-[1.25rem] border border-border-subtle bg-white/78 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="loading-skeleton h-3 w-24 rounded-full" />
            <div className="loading-skeleton mt-3 h-8 w-[min(24rem,80%)] rounded-full" />
            <div className="loading-skeleton mt-4 h-4 w-full rounded-full" />
            <div className="loading-skeleton mt-2 h-4 w-[88%] rounded-full" />
          </div>
          <div className="flex flex-wrap gap-2 md:justify-end">
            <div className="loading-skeleton h-9 w-20 rounded-full" />
            <div className="loading-skeleton h-9 w-24 rounded-full" />
            <div className="loading-skeleton h-9 w-20 rounded-full" />
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3">
        {[0, 1].map((item) => (
          <div
            key={`loading-card-${item}`}
            className="rounded-[1.35rem] border border-border-subtle bg-white/82 p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <div className="loading-skeleton h-7 w-20 rounded-full" />
              <div className="loading-skeleton h-7 w-24 rounded-full" />
              <div className="loading-skeleton h-7 w-[4.5rem] rounded-full" />
            </div>
            <div className="loading-skeleton mt-4 h-8 w-[min(20rem,72%)] rounded-full" />
            <div className="loading-skeleton mt-4 h-24 w-full rounded-[1rem]" />
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="loading-skeleton h-20 w-full rounded-[1rem]" />
              <div className="loading-skeleton h-20 w-full rounded-[1rem]" />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function splitMultiValue(value: string) {
  return value
    .split(/[\n,;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function filterMatches(
  matches: RuleMatch[],
  filters: {
    severity: string;
    medicationOnly: boolean;
    diseaseOnly: boolean;
  },
) {
  return matches.filter((match) => {
    if (filters.severity && match.resolvedSeverity !== filters.severity) {
      return false;
    }
    if (filters.medicationOnly && match.rule.interactionDrugs.length === 0) {
      return false;
    }
    if (filters.diseaseOnly && match.rule.interactionDiseases.length === 0) {
      return false;
    }
    return true;
  });
}

function sortMatches(
  matches: RuleMatch[],
  sort: NonNullable<EngineQuery["sort"]>,
) {
  const sorted = [...matches];

  sorted.sort((left, right) => {
    if (sort === "confidence_desc") {
      const difference =
        confidenceRank[right.rule.confidence] -
        confidenceRank[left.rule.confidence];
      if (difference !== 0) return difference;
    }

    if (sort === "nutrient_name") {
      const difference = left.rule.nutrientOrIngredient.localeCompare(
        right.rule.nutrientOrIngredient,
        "ko",
      );
      if (difference !== 0) return difference;
    }

    if (sort === "recently_reviewed") {
      const difference =
        new Date(right.rule.lastReviewedAt ?? 0).getTime() -
        new Date(left.rule.lastReviewedAt ?? 0).getTime();
      if (difference !== 0) return difference;
    }

    if (sort === "severity_desc") {
      const severityRank = {
        contraindicated: 4,
        avoid: 3,
        warn: 2,
        monitor: 1,
      } as const;
      const difference =
        severityRank[right.resolvedSeverity] -
        severityRank[left.resolvedSeverity];
      if (difference !== 0) return difference;
    }

    const categoryDifference =
      (categoryRank[left.rule.ruleCategory] ?? 99) -
      (categoryRank[right.rule.ruleCategory] ?? 99);
    if (categoryDifference !== 0) return categoryDifference;

    return right.rule.priority - left.rule.priority;
  });

  return sorted;
}

function getVisibleSections(
  response: EngineResponse | null,
  filters: {
    severity: string;
    medicationOnly: boolean;
    diseaseOnly: boolean;
    sort: NonNullable<EngineQuery["sort"]>;
  },
) {
  if (!response) return null;

  return {
    definitely_matched: sortMatches(
      filterMatches(response.definitely_matched, filters),
      filters.sort,
    ),
    possibly_relevant: sortMatches(
      filterMatches(response.possibly_relevant, filters),
      filters.sort,
    ),
    needs_more_info: sortMatches(
      filterMatches(response.needs_more_info, filters),
      filters.sort,
    ),
  };
}

function buildAiProfileSummary(response: EngineResponse) {
  const parts: string[] = [];
  const profile = response.query.profile;
  const selectedItems = (response.query.candidateItems ?? [])
    .map((item) => item.name.trim())
    .filter(Boolean);

  if (profile.age) parts.push(`나이 ${profile.age}`);
  if (profile.sex) parts.push(`성별 ${profile.sex}`);
  if (profile.medications && profile.medications.length > 0) {
    parts.push(`복용 약물 ${profile.medications.join(", ")}`);
  }
  if (profile.conditions && profile.conditions.length > 0) {
    parts.push(`질환/상태 ${profile.conditions.join(", ")}`);
  }
  if (selectedItems.length > 0) {
    parts.push(`선택 성분 ${selectedItems.join(", ")}`);
  }
  if (profile.pregnancyStatus) {
    parts.push(`임신 ${getPregnancyStatusLabel(profile.pregnancyStatus)}`);
  }
  if (profile.lactationStatus) parts.push(`수유 ${profile.lactationStatus}`);
  if (profile.smokerStatus) parts.push(`흡연 ${profile.smokerStatus}`);
  if (profile.jurisdiction) parts.push(`관할권 ${profile.jurisdiction}`);

  return parts.join(" / ") || "선택 성분과 개인 조건에 맞춘 영양 안전 결과";
}

function formatCount(value: number) {
  return value.toLocaleString("ko-KR");
}

function formatPriorityLabel(value: string) {
  if (value === "manual_review_high") return "우선검토 높음";
  if (value === "manual_review_medium") return "우선검토 중간";
  if (value === "manual_review_low") return "우선검토 낮음";
  return cleanDisplayText(value.replace(/_/g, " "));
}

function formatDecisionLabel(value: string) {
  if (value === "include_candidate") return "포함 후보";
  if (value === "maybe_needs_manual_review") return "추가 검토";
  if (value === "manual_review_low") return "낮은 검토";
  return cleanDisplayText(value.replace(/_/g, " "));
}

function formatTargetLabel(value: string) {
  return cleanDisplayText(value.replace(/_/g, " "));
}

function getCandidateTerms(
  candidate: EngineResponse["literature"]["relatedCandidates"][number],
) {
  return [
    ...candidate.matchedIngredientTerms,
    ...candidate.matchedPopulationTerms,
    ...candidate.matchedOutcomeTerms,
  ].slice(0, 5);
}

function LiteratureContextPanel({
  literature,
}: {
  literature: EngineResponse["literature"];
}) {
  const summary = literature.summary;
  const summaryCards = [
    {
      label: "PubMed hit",
      value: formatCount(summary.latestPubMedHitCount),
      caption: `저장 ${formatCount(summary.latestPubMedStoredRecords)}건`,
    },
    {
      label: "누적 후보",
      value: formatCount(summary.cumulativePubMedCandidates),
      caption: `포함 후보 ${formatCount(summary.includeCandidateCount)}건`,
    },
    {
      label: "보조검색 hit",
      value: formatCount(summary.secondaryHitTotal),
      caption: `저장 ${formatCount(summary.secondaryStoredRecords)}건`,
    },
    {
      label: "화면 rule",
      value: formatCount(summary.visibleRuleCount),
      caption: `우선검토 ${formatCount(summary.priorityCandidateCount)}건`,
    },
  ];

  return (
    <section className="surface-card rounded-[1.25rem] p-4 motion-safe:animate-[rise-in_620ms_var(--ease-emphasized)_both]">
      <div className="flex flex-col gap-2 border-b border-border-subtle pb-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <h2 className="text-[0.88rem] font-semibold tracking-[-0.02em] text-foreground md:text-[0.94rem]">
            문헌 검색 풀과 관련 후보문헌
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {literature.matchExplanation}
          </p>
        </div>
        <span className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-muted">
          {formatCount(literature.totalCandidateCount)}건 중{" "}
          {formatCount(literature.shownCandidateCount)}건 표시
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <div
            key={item.label}
            className="rounded-[0.85rem] border border-stone-200 bg-white px-3.5 py-3"
          >
            <p className="text-xs font-medium text-muted">{item.label}</p>
            <p className="mt-1 text-[1.15rem] font-semibold leading-none text-foreground tabular-nums">
              {item.value}
            </p>
            <p className="mt-1.5 text-xs leading-5 text-muted">{item.caption}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {literature.relatedCandidates.map((candidate) => {
          const terms = getCandidateTerms(candidate);

          return (
            <article
              key={candidate.id}
              className="rounded-[0.95rem] border border-stone-200 bg-white p-4"
            >
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[0.72rem] font-medium text-stone-700">
                  {formatPriorityLabel(candidate.priority)}
                </span>
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[0.72rem] font-medium text-emerald-800">
                  {formatDecisionLabel(candidate.suggestedDecision)}
                </span>
                {candidate.year ? (
                  <span className="rounded-full bg-white px-2.5 py-1 text-[0.72rem] font-medium text-muted ring-1 ring-stone-200">
                    {candidate.year}
                  </span>
                ) : null}
              </div>
              <h3 className="mt-3 text-sm font-semibold leading-6 text-foreground">
                <a
                  href={candidate.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-border-subtle underline-offset-4 transition hover:text-stone-600"
                >
                  {cleanDisplayText(candidate.title)}
                </a>
              </h3>
              <div className="mt-3 flex flex-wrap gap-2 text-[0.74rem]">
                <span className="rounded-full border border-stone-200 px-2.5 py-1 text-muted">
                  {formatTargetLabel(candidate.targetId)}
                </span>
                {candidate.pmid ? (
                  <span className="rounded-full border border-stone-200 px-2.5 py-1 text-muted">
                    PMID {candidate.pmid}
                  </span>
                ) : null}
              </div>
              {terms.length > 0 ? (
                <p className="mt-3 text-xs leading-5 text-muted">
                  관련 단어: {terms.map(cleanDisplayText).join(", ")}
                </p>
              ) : null}
              <p className="mt-2 text-xs leading-5 text-muted">
                {candidate.relevanceReasons.map(cleanDisplayText).join(" / ")}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function RuleExplorerClient({
  metadata,
}: {
  metadata: ExplorerMetadata;
}) {
  type SectionKey = keyof typeof sectionLabels;
  const [age, setAge] = useState(blankExplorerProfile.age);
  const [sex, setSex] = useState(blankExplorerProfile.sex);
  const [pregnancyStatus, setPregnancyStatus] = useState(
    blankExplorerProfile.pregnancyStatus,
  );
  const [lactationStatus, setLactationStatus] = useState(
    blankExplorerProfile.lactationStatus,
  );
  const [smokerStatus, setSmokerStatus] = useState(
    blankExplorerProfile.smokerStatus,
  );
  const [medications, setMedications] = useState(
    blankExplorerProfile.medications,
  );
  const [conditions, setConditions] = useState(blankExplorerProfile.conditions);
  const [allergies, setAllergies] = useState(blankExplorerProfile.allergies);
  const [selectedCompounds, setSelectedCompounds] = useState(
    blankExplorerProfile.selectedCompounds,
  );
  const [dailyIntakeValue, setDailyIntakeValue] = useState(
    blankExplorerProfile.dailyIntakeValue,
  );
  const [dailyIntakeUnit, setDailyIntakeUnit] = useState(
    blankExplorerProfile.dailyIntakeUnit,
  );
  const [longTermUseDays, setLongTermUseDays] = useState(
    blankExplorerProfile.longTermUseDays,
  );
  const [ingredientForm, setIngredientForm] = useState(
    blankExplorerProfile.ingredientForm,
  );
  const [productName, setProductName] = useState(
    blankExplorerProfile.productName,
  );
  const [coingredients, setCoingredients] = useState(
    blankExplorerProfile.coingredients,
  );
  const [jurisdiction, setJurisdiction] = useState(
    blankExplorerProfile.jurisdiction,
  );
  const [memo, setMemo] = useState(blankExplorerProfile.memo);
  const [severityFilter, setSeverityFilter] = useState("");
  const [medicationOnly, setMedicationOnly] = useState(false);
  const [diseaseOnly, setDiseaseOnly] = useState(false);
  const [sort, setSort] =
    useState<NonNullable<EngineQuery["sort"]>>("severity_desc");
  const [response, setResponse] = useState<EngineResponse | null>(null);
  const [aiRuleRecommendations, setAiRuleRecommendations] = useState<
    Record<string, string>
  >({});
  const [hasQueried, setHasQueried] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isQueryLoading, setIsQueryLoading] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [isExamplesOpen, setIsExamplesOpen] = useState(false);
  const [sectionVisibleCounts, setSectionVisibleCounts] = useState<
    Record<SectionKey, number>
  >(() => ({ ...sectionPreviewCounts }));
  const [hasRestoredState, setHasRestoredState] = useState(false);
  const [isPending, startTransition] = useTransition();
  const activeQueryIdRef = useRef(0);

  const isMale = sex === "male";
  const visible = getVisibleSections(response, {
    severity: severityFilter,
    medicationOnly,
    diseaseOnly,
    sort,
  });
  const compoundFieldAnalysis = analyzeExplorerField(
    selectedCompounds,
    metadata.ingredients,
  );
  const medicationFieldAnalysis = analyzeExplorerField(
    medications,
    metadata.medicationOptions,
  );
  const conditionFieldAnalysis = analyzeExplorerField(
    conditions,
    metadata.conditionOptions,
  );
  const visibleCount =
    (visible?.definitely_matched.length ?? 0) +
    (visible?.possibly_relevant.length ?? 0) +
    (visible?.needs_more_info.length ?? 0);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(explorerStorageKey);
      if (!raw) {
        setHasRestoredState(true);
        return;
      }

      const snapshot = JSON.parse(raw) as PersistedExplorerState;
      if (snapshot.version !== 3) {
        setHasRestoredState(true);
        return;
      }

      const restoredProfile: ExplorerProfileDraft = {
        age: snapshot.form.age ?? "",
        sex: snapshot.form.sex ?? "",
        pregnancyStatus: normalizePregnancyStatus(
          snapshot.form.pregnancyStatus ?? "",
        ),
        lactationStatus: snapshot.form.lactationStatus ?? "",
        smokerStatus: snapshot.form.smokerStatus ?? "",
        medications: snapshot.form.medications ?? "",
        conditions: snapshot.form.conditions ?? "",
        allergies: snapshot.form.allergies ?? "",
        selectedCompounds: snapshot.form.selectedCompounds ?? "",
        dailyIntakeValue: snapshot.form.dailyIntakeValue ?? "",
        dailyIntakeUnit: snapshot.form.dailyIntakeUnit ?? "",
        longTermUseDays: snapshot.form.longTermUseDays ?? "",
        ingredientForm: snapshot.form.ingredientForm ?? "",
        productName: snapshot.form.productName ?? "",
        coingredients: snapshot.form.coingredients ?? "",
        jurisdiction: snapshot.form.jurisdiction ?? "",
        memo: snapshot.form.memo ?? "",
      };

      setAge(restoredProfile.age);
      setSex(restoredProfile.sex);
      setPregnancyStatus(restoredProfile.pregnancyStatus);
      setLactationStatus(restoredProfile.lactationStatus);
      setSmokerStatus(restoredProfile.smokerStatus);
      setMedications(restoredProfile.medications);
      setConditions(restoredProfile.conditions);
      setAllergies(restoredProfile.allergies);
      setSelectedCompounds(restoredProfile.selectedCompounds);
      setDailyIntakeValue(restoredProfile.dailyIntakeValue);
      setDailyIntakeUnit(restoredProfile.dailyIntakeUnit);
      setLongTermUseDays(restoredProfile.longTermUseDays);
      setIngredientForm(restoredProfile.ingredientForm);
      setProductName(restoredProfile.productName);
      setCoingredients(restoredProfile.coingredients);
      setJurisdiction(restoredProfile.jurisdiction);
      setMemo(restoredProfile.memo);

      setSeverityFilter(snapshot.filters.severityFilter ?? "");
      setMedicationOnly(snapshot.filters.medicationOnly ?? false);
      setDiseaseOnly(snapshot.filters.diseaseOnly ?? false);
      setSort(snapshot.filters.sort ?? "severity_desc");

      setIsAdvancedOpen(
        snapshot.ui.isAdvancedOpen ?? hasAdvancedProfileValues(restoredProfile),
      );
      setIsExamplesOpen(snapshot.ui.isExamplesOpen ?? false);
      setSectionVisibleCounts(
        snapshot.ui.sectionVisibleCounts ?? { ...sectionPreviewCounts },
      );

      setHasQueried(snapshot.query.hasQueried ?? false);
      setResponse(snapshot.query.response ?? null);
      setError(null);
    } catch {
      window.localStorage.removeItem(explorerStorageKey);
    } finally {
      setHasRestoredState(true);
    }
  }, []);

  useEffect(() => {
    if (!hasRestoredState) {
      return;
    }

    const snapshot: PersistedExplorerState = {
      version: 3,
      form: {
        age,
        sex,
        pregnancyStatus,
        lactationStatus,
        smokerStatus,
        medications,
        conditions,
        allergies,
        selectedCompounds,
        dailyIntakeValue,
        dailyIntakeUnit,
        longTermUseDays,
        ingredientForm,
        productName,
        coingredients,
        jurisdiction,
        memo,
      },
      filters: {
        severityFilter,
        medicationOnly,
        diseaseOnly,
        sort,
      },
      ui: {
        isAdvancedOpen,
        isExamplesOpen,
        sectionVisibleCounts,
      },
      query: {
        hasQueried,
        response,
      },
    };

    window.localStorage.setItem(explorerStorageKey, JSON.stringify(snapshot));
  }, [
    age,
    sex,
    pregnancyStatus,
    lactationStatus,
    smokerStatus,
    medications,
    conditions,
    allergies,
    selectedCompounds,
    dailyIntakeValue,
    dailyIntakeUnit,
    longTermUseDays,
    ingredientForm,
    productName,
    coingredients,
    jurisdiction,
    memo,
    severityFilter,
    medicationOnly,
    diseaseOnly,
    sort,
    isAdvancedOpen,
    isExamplesOpen,
    sectionVisibleCounts,
    hasQueried,
    response,
    hasRestoredState,
  ]);

  useEffect(() => {
    if (!response) {
      setAiRuleRecommendations({});
      return;
    }

    const currentResponse = response;
    const controller = new AbortController();

    async function loadAiGuidance() {
      try {
        const result = await fetch("/api/ai-explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            engineResponse: currentResponse,
            profileSummary: buildAiProfileSummary(currentResponse),
          }),
          signal: controller.signal,
        });

        if (!result.ok) {
          setAiRuleRecommendations({});
          return;
        }

        const payload = (await result.json()) as
          | AiExplainResponse
          | { error?: string };
        if (!("ok" in payload) || !payload.ok) {
          setAiRuleRecommendations({});
          return;
        }

        setAiRuleRecommendations(
          Object.fromEntries(
            payload.explanation.ruleCardActions.map((item) => [
              item.ruleId,
              item.recommendation,
            ]),
          ),
        );
      } catch (caught) {
        if (caught instanceof Error && caught.name === "AbortError") {
          return;
        }

        setAiRuleRecommendations({});
      }
    }

    void loadAiGuidance();

    return () => controller.abort();
  }, [response]);

  function resetSectionPreviewCounts() {
    setSectionVisibleCounts({ ...sectionPreviewCounts });
  }

  function updateSeverityFilter(value: string) {
    setSeverityFilter(value);
    resetSectionPreviewCounts();
  }

  function updateMedicationOnly(value: boolean) {
    setMedicationOnly(value);
    resetSectionPreviewCounts();
  }

  function updateDiseaseOnly(value: boolean) {
    setDiseaseOnly(value);
    resetSectionPreviewCounts();
  }

  function updateSort(value: NonNullable<EngineQuery["sort"]>) {
    setSort(value);
    resetSectionPreviewCounts();
  }

  function buildQueryPayload(profile: ExplorerProfileDraft): EngineQuery {
    const isMaleProfile = profile.sex === "male";
    const normalizedPregnancyStatus = normalizePregnancyStatus(
      profile.pregnancyStatus,
    );
    const selectedCompoundDetails = buildCanonicalEntryDetails(
      profile.selectedCompounds,
      metadata.ingredients,
    );
    const selectedCompoundEntries = selectedCompoundDetails.map(
      (entry) => entry.label,
    );
    const coingredientEntries = buildCanonicalEntries(
      profile.coingredients,
      metadata.ingredients,
    );
    const explicitDoseValue = toNullableNumber(profile.dailyIntakeValue);
    const explicitDoseUnit = normalizeDailyIntakeUnit(profile.dailyIntakeUnit);
    const globalDose = parseDailyIntakeText(
      `${profile.dailyIntakeValue} ${profile.dailyIntakeUnit} ${profile.selectedCompounds} ${profile.memo}`,
    );
    const explicitLongTermUseDays = toNullableNumber(profile.longTermUseDays);
    const globalLongTermUseDays = parseLongTermUseDays(
      `${profile.longTermUseDays} ${profile.selectedCompounds} ${profile.memo}`,
    );
    const candidateItems = selectedCompoundDetails.map((entry) => {
      const tokenDose = parseDailyIntakeText(`${entry.raw} ${profile.memo}`);
      const dailyIntakeValue =
        explicitDoseValue ?? tokenDose?.value ?? globalDose?.value;
      const dailyIntakeUnit =
        explicitDoseUnit ?? tokenDose?.unit ?? globalDose?.unit;
      const longTermDays =
        explicitLongTermUseDays ??
        parseLongTermUseDays(`${entry.raw} ${profile.memo}`) ??
        globalLongTermUseDays;
      const otherSelectedCompounds = selectedCompoundEntries.filter(
        (candidate) =>
          normalizeExplorerLookupKey(candidate) !==
          normalizeExplorerLookupKey(entry.label),
      );
      const combinedCoingredients = [
        ...coingredientEntries,
        ...otherSelectedCompounds,
      ].filter(
        (candidate, index, array) =>
          normalizeExplorerLookupKey(candidate) &&
          array.findIndex(
            (item) =>
              normalizeExplorerLookupKey(item) ===
              normalizeExplorerLookupKey(candidate),
          ) === index,
      );

      return {
        ingredientId: entry.id,
        name: entry.label,
        form: profile.ingredientForm.trim() || undefined,
        product: profile.productName.trim() || undefined,
        dailyIntakeValue: dailyIntakeValue ?? undefined,
        dailyIntakeUnit: dailyIntakeUnit ?? undefined,
        longTermUseDays:
          typeof longTermDays === "number" ? Math.round(longTermDays) : undefined,
        sameDay: combinedCoingredients.length > 0 ? true : undefined,
        coingredients:
          combinedCoingredients.length > 0 ? combinedCoingredients : undefined,
      };
    });

    return {
      profile: {
        age: profile.age ? Number(profile.age) : undefined,
        sex: profile.sex || undefined,
        pregnancyStatus: isMaleProfile
          ? undefined
          : normalizedPregnancyStatus || undefined,
        lactationStatus: isMaleProfile
          ? undefined
          : profile.lactationStatus || undefined,
        smokerStatus: profile.smokerStatus || undefined,
        medications: buildCanonicalEntries(
          profile.medications,
          metadata.medicationOptions,
        ),
        conditions: buildCanonicalEntries(
          profile.conditions,
          metadata.conditionOptions,
        ),
        allergies: splitMultiValue(profile.allergies),
        selectedCompounds: selectedCompoundEntries,
        jurisdiction: profile.jurisdiction || "US",
        memo: profile.memo,
        strictestMode: true,
      },
      candidateItems: candidateItems.length > 0 ? candidateItems : undefined,
      sort,
    } satisfies EngineQuery;
  }

  async function submitQuery(profileOverride?: ExplorerProfileDraft) {
    const queryId = activeQueryIdRef.current + 1;
    activeQueryIdRef.current = queryId;
    const profile = profileOverride ?? {
      age,
      sex,
      pregnancyStatus,
      lactationStatus,
      smokerStatus,
      medications,
      conditions,
      allergies,
      selectedCompounds,
      dailyIntakeValue,
      dailyIntakeUnit,
      longTermUseDays,
      ingredientForm,
      productName,
      coingredients,
      jurisdiction,
      memo,
    };

    setHasQueried(true);
    setError(null);
    setAiRuleRecommendations({});
    setResponse(null);
    setIsQueryLoading(true);
    const startedAt = performance.now();

    try {
      const result = await fetch("/api/rules/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildQueryPayload(profile)),
      });

      const payload = (await result.json()) as
        | EngineResponse
        | { error?: string };
      const elapsed = performance.now() - startedAt;
      if (elapsed < minimumQueryLoadingMs) {
        await delay(minimumQueryLoadingMs - elapsed);
      }

      if (activeQueryIdRef.current !== queryId) {
        return;
      }

      if (!result.ok) {
        throw new Error(
          "error" in payload
            ? (payload.error ?? "규칙을 불러오지 못했습니다.")
            : "규칙을 불러오지 못했습니다.",
        );
      }

      setResponse(payload as EngineResponse);
      resetSectionPreviewCounts();
    } finally {
      if (activeQueryIdRef.current === queryId) {
        setIsQueryLoading(false);
      }
    }
  }

  function resetResultFilters() {
    setSeverityFilter("");
    setMedicationOnly(false);
    setDiseaseOnly(false);
    setSort("severity_desc");
    resetSectionPreviewCounts();
  }

  function resetForm() {
    setAge("");
    setSex("");
    setPregnancyStatus("");
    setLactationStatus("");
    setSmokerStatus("");
    setMedications("");
    setConditions("");
    setAllergies("");
    setSelectedCompounds("");
    setDailyIntakeValue("");
    setDailyIntakeUnit("");
    setLongTermUseDays("");
    setIngredientForm("");
    setProductName("");
    setCoingredients("");
    setJurisdiction("");
    setMemo("");
    resetResultFilters();
    setResponse(null);
    setHasQueried(false);
    setError(null);
    setIsAdvancedOpen(false);
    setIsExamplesOpen(false);
    resetSectionPreviewCounts();
    window.localStorage.removeItem(explorerStorageKey);
  }

  function applyStarterProfile(
    profile: Partial<ExplorerProfileDraft>,
    options?: { submit?: boolean },
  ) {
    const nextProfile = buildStarterDraft(profile);

    setSelectedCompounds(nextProfile.selectedCompounds);
    setMedications(nextProfile.medications);
    setConditions(nextProfile.conditions);
    setAge(nextProfile.age);
    setSex(nextProfile.sex);
    setPregnancyStatus(normalizePregnancyStatus(nextProfile.pregnancyStatus));
    setLactationStatus(nextProfile.lactationStatus);
    setSmokerStatus(nextProfile.smokerStatus);
    setAllergies(nextProfile.allergies);
    setDailyIntakeValue(nextProfile.dailyIntakeValue);
    setDailyIntakeUnit(nextProfile.dailyIntakeUnit);
    setLongTermUseDays(nextProfile.longTermUseDays);
    setIngredientForm(nextProfile.ingredientForm);
    setProductName(nextProfile.productName);
    setCoingredients(nextProfile.coingredients);
    setJurisdiction(nextProfile.jurisdiction);
    setMemo(nextProfile.memo);
    setError(null);
    setResponse(null);
    setHasQueried(false);
    setIsAdvancedOpen(false);
    setIsExamplesOpen(false);
    resetSectionPreviewCounts();

    if (options?.submit) {
      startTransition(() => {
        void submitQuery(nextProfile).catch((caught) =>
          setError(
            caught instanceof Error
              ? caught.message
              : "규칙을 불러오지 못했습니다.",
          ),
        );
      });
    }
  }

  const sectionOrder: Array<keyof NonNullable<typeof visible>> = [
    "definitely_matched",
    "possibly_relevant",
    "needs_more_info",
  ];

  const highlightedCounts = [
    {
      label: "출처",
      value: metadata.meta.sourceCount,
      tone: "from-emerald-100/90 to-white",
    },
    {
      label: "근거 청크",
      value: metadata.meta.evidenceChunkCount,
      tone: "from-amber-100/80 to-white",
    },
    {
      label: "규칙",
      value: metadata.meta.safetyRuleCount,
      tone: "from-stone-200/80 to-white",
    },
  ] as const;
  const resultOverview = [
    {
      key: "definitely_matched",
      label: sectionLabels.definitely_matched,
      shortLabel: "먼저 보기",
      description: "직접 관련",
      count: visible?.definitely_matched.length ?? 0,
      tone: "border-stone-200 bg-white",
    },
    {
      key: "possibly_relevant",
      label: sectionLabels.possibly_relevant,
      shortLabel: "같이 보기",
      description: "함께 참고",
      count: visible?.possibly_relevant.length ?? 0,
      tone: "border-stone-200 bg-white",
    },
    {
      key: "needs_more_info",
      label: sectionLabels.needs_more_info,
      shortLabel: "추가 확인",
      description: "정보 더 필요",
      count: visible?.needs_more_info.length ?? 0,
      tone: "border-amber-200 bg-amber-50/60",
    },
  ] as const;
  const hasActiveResultFilters = Boolean(
    severityFilter || medicationOnly || diseaseOnly || sort !== "severity_desc",
  );
  const sectionPresentation = {
    definitely_matched: {
      kicker: "먼저 보기",
      title: "가장 먼저 확인할 내용",
      summary:
        "현재 입력과 직접 연결된 판단입니다. 이 섹션만 먼저 읽어도 핵심을 빠르게 파악할 수 있습니다.",
      railTone: "surface-card bg-white",
      chipTone: "bg-stone-100 text-foreground border border-stone-200",
    },
    possibly_relevant: {
      kicker: "참고",
      title: "같이 보면 좋은 내용",
      summary:
        "지금 바로 위험 판정은 아니지만, 맥락을 이해하는 데 도움이 되는 정보입니다.",
      railTone: "surface-card bg-white",
      chipTone: "bg-white text-muted border border-stone-200",
    },
    needs_more_info: {
      kicker: "추가 입력",
      title: "조금 더 입력하면 정확해집니다",
      summary:
        "용량, 상태, 기간 같은 정보가 부족해 판단을 보수적으로 잡은 항목입니다.",
      railTone: "surface-card bg-amber-50/45",
      chipTone: "border border-amber-200 bg-amber-50 text-amber-900",
    },
  } as const;
  const hasAnyPrimaryInput = Boolean(
    selectedCompounds.trim() ||
      medications.trim() ||
      conditions.trim() ||
      dailyIntakeValue.trim(),
  );
  const starterProfiles: Array<{
    label: string;
    description: string;
    selectedCompounds: string;
    medications?: string;
    conditions?: string;
    age?: string;
    sex?: string;
    pregnancyStatus?: string;
    lactationStatus?: string;
    smokerStatus?: string;
    dailyIntakeValue?: string;
    dailyIntakeUnit?: string;
    longTermUseDays?: string;
    ingredientForm?: string;
    productName?: string;
    coingredients?: string;
    jurisdiction?: string;
    memo?: string;
  }> = [
    {
      label: "비타민 D 5000 IU",
      description: "고함량 비타민 D 확인용 조합",
      selectedCompounds: "비타민 D",
      dailyIntakeValue: "5000",
      dailyIntakeUnit: "iu/day",
      coingredients: "calcium",
      age: "45",
      sex: "female",
      jurisdiction: "US",
    },
    {
      label: "비타민 B6 50 mg",
      description: "장기복용 신경병증 신호 확인용 조합",
      selectedCompounds: "vitamin B6",
      dailyIntakeValue: "50",
      dailyIntakeUnit: "mg/day",
      longTermUseDays: "180",
      age: "35",
      sex: "female",
      jurisdiction: "US",
    },
    {
      label: "아연 50 mg",
      description: "고함량 미네랄 확인용 조합",
      selectedCompounds: "zinc",
      dailyIntakeValue: "50",
      dailyIntakeUnit: "mg/day",
      longTermUseDays: "120",
      age: "40",
      sex: "male",
      jurisdiction: "US",
    },
  ] as const;

  return (
    <div className="dose-explorer space-y-5">
      <section className="overflow-hidden border border-slate-300 bg-white">
        <div>
          <div className="px-4 py-4 md:px-5">
            <div className="hidden flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  입력
                </p>
                <h2 className="mt-2 text-[clamp(1.1rem,1.7vw,1.38rem)] font-semibold tracking-[-0.02em] text-foreground">
                  필요한 정보만 입력하세요
                </h2>
                <p className="measure-copy mt-2 text-sm leading-6 text-muted">
                  성분만으로도 시작할 수 있고, 약물이나 상태를 추가하면 결과가
                  더 정확해집니다.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  applyStarterProfile(defaultExampleProfile, { submit: true })
                }
                className={`${subtleActionButtonClass} hidden`}
              >
                입력만 초기화
              </button>
            </div>

            <div className="hidden rounded-[1rem] border border-emerald-200/70 bg-emerald-50/70 px-4 py-3">
              <div className="space-y-3">
                <div className="max-w-[46rem]">
                  <p className="text-sm font-semibold text-foreground">
                    첫 화면에는 예시 입력과 예시 결과가 바로 보이도록
                    구성했습니다.
                  </p>
                  <p className="mt-0.5 text-sm leading-5 text-muted">
                    그대로 `규칙 조회`를 눌러도 되고, 필요한 칸만 내 상황에 맞게
                    바꿔서 다시 조회해도 됩니다.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      applyStarterProfile(defaultExampleProfile, {
                        submit: true,
                      })
                    }
                    className={subtleActionButtonClass}
                  >
                    기본 예시로 되돌리기
                  </button>
                  {starterProfiles.map((profile) => (
                    <button
                      key={`starter-${profile.label}`}
                      type="button"
                      onClick={() =>
                        applyStarterProfile(profile, { submit: true })
                      }
                      className={ghostButtonClass}
                    >
                      {profile.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="hidden mt-5 grid gap-3 sm:grid-cols-3">
              {highlightedCounts.map((item) => (
                <div
                  key={item.label}
                  className="rounded-[1rem] border border-stone-200 bg-white px-4 py-4"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted">
                    {item.label}
                  </p>
                  <p className="mt-2 text-[1.42rem] font-semibold leading-none text-foreground tabular-nums">
                    {item.value.toLocaleString("ko-KR")}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="px-4 py-4 md:px-5">
            <div className="grid gap-0 border border-slate-300 lg:grid-cols-[1.2fr_0.9fr_0.9fr]">
              <label
                className={`${fieldGroupClass} border-b border-slate-300 bg-white p-3 lg:border-b-0 lg:border-r`}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className={fieldLabelClass}>1. 선택 성분</span>
                  <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-600">
                    필수
                  </span>
                </div>
                <input
                  value={selectedCompounds}
                  onChange={(event) => setSelectedCompounds(event.target.value)}
                  placeholder="예: 비타민 D, vitamin d, vit d"
                  className={fieldControlClass}
                  autoComplete="off"
                />
                <p className="hidden mt-2 text-xs leading-5 text-muted">
                  쉼표로 이어 적으면 됩니다.
                </p>
                <FieldRecognitionAssist
                  recognized={compoundFieldAnalysis.recognized}
                  unresolved={compoundFieldAnalysis.unresolved}
                  suggestions={compoundFieldAnalysis.suggestions}
                  onSelectSuggestion={(suggestion) =>
                    setSelectedCompounds((current) =>
                      applySuggestionToField(current, suggestion),
                    )
                  }
                />
              </label>

              <label
                className={`${fieldGroupClass} rounded-[1rem] border border-stone-200 bg-white p-3`}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className={fieldLabelClass}>2. 복용 약물</span>
                  <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-600">
                    정확도 상승
                  </span>
                </div>
                <input
                  value={medications}
                  onChange={(event) => setMedications(event.target.value)}
                  placeholder="예: 와파린, warfarin, 레보티록신"
                  className={fieldControlClass}
                  autoComplete="off"
                />
                <p className="hidden mt-2 text-xs leading-5 text-muted">
                  복용 중인 약만 짧게 적어도 됩니다.
                </p>
                <FieldRecognitionAssist
                  recognized={medicationFieldAnalysis.recognized}
                  unresolved={medicationFieldAnalysis.unresolved}
                  suggestions={medicationFieldAnalysis.suggestions}
                  onSelectSuggestion={(suggestion) =>
                    setMedications((current) =>
                      applySuggestionToField(current, suggestion),
                    )
                  }
                />
              </label>

              <label
                className={`${fieldGroupClass} rounded-[1rem] border border-stone-200 bg-white p-3`}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className={fieldLabelClass}>3. 질환 및 상태</span>
                  <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-600">
                    선택
                  </span>
                </div>
                <input
                  value={conditions}
                  onChange={(event) => setConditions(event.target.value)}
                  placeholder="예: 당뇨병, diabetes, 간질환"
                  className={fieldControlClass}
                  autoComplete="off"
                />
                <p className="hidden mt-2 text-xs leading-5 text-muted">
                  질환, 상태를 함께 적어도 됩니다.
                </p>
                <FieldRecognitionAssist
                  recognized={conditionFieldAnalysis.recognized}
                  unresolved={conditionFieldAnalysis.unresolved}
                  suggestions={conditionFieldAnalysis.suggestions}
                  onSelectSuggestion={(suggestion) =>
                    setConditions((current) =>
                      applySuggestionToField(current, suggestion),
                    )
                  }
                />
              </label>
            </div>

            <div className="mt-3 grid gap-0 border border-slate-300 md:grid-cols-2 xl:grid-cols-6">
              <label
                className={`${fieldGroupClass} border-b border-slate-300 bg-slate-50 p-3 xl:border-b-0 xl:border-r`}
              >
                <span className={fieldLabelClass}>1일 섭취량</span>
                <input
                  value={dailyIntakeValue}
                  onChange={(event) => setDailyIntakeValue(event.target.value)}
                  type="number"
                  inputMode="decimal"
                  placeholder="예: 5000"
                  className={fieldControlClass}
                />
              </label>

              <div className="border-b border-slate-300 bg-white p-3 md:border-r xl:border-b-0">
                <SelectField
                  label="단위"
                  value={dailyIntakeUnit}
                  onChange={setDailyIntakeUnit}
                  options={[
                    { value: "", label: "자동" },
                    { value: "iu/day", label: "IU/day" },
                    { value: "mg/day", label: "mg/day" },
                    { value: "mcg/day", label: "mcg/day" },
                    { value: "mcg RAE/day", label: "mcg RAE/day" },
                  ]}
                />
              </div>

              <label
                className={`${fieldGroupClass} border-b border-slate-300 bg-slate-50 p-3 xl:border-b-0 xl:border-r`}
              >
                <span className={fieldLabelClass}>복용 기간</span>
                <input
                  value={longTermUseDays}
                  onChange={(event) => setLongTermUseDays(event.target.value)}
                  type="number"
                  inputMode="numeric"
                  placeholder="일수"
                  className={fieldControlClass}
                />
              </label>

              <label
                className={`${fieldGroupClass} border-b border-slate-300 bg-white p-3 md:border-r xl:border-b-0`}
              >
                <span className={fieldLabelClass}>제형</span>
                <input
                  value={ingredientForm}
                  onChange={(event) => setIngredientForm(event.target.value)}
                  placeholder="예: capsule"
                  className={fieldControlClass}
                />
              </label>

              <label
                className={`${fieldGroupClass} border-b border-slate-300 bg-slate-50 p-3 xl:border-b-0 xl:border-r`}
              >
                <span className={fieldLabelClass}>동시 성분</span>
                <input
                  value={coingredients}
                  onChange={(event) => setCoingredients(event.target.value)}
                  placeholder="예: calcium"
                  className={fieldControlClass}
                />
              </label>

              <label
                className={`${fieldGroupClass} bg-white p-3`}
              >
                <span className={fieldLabelClass}>제품명</span>
                <input
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                  placeholder="선택"
                  className={fieldControlClass}
                />
              </label>
            </div>

            <section className="mt-3 overflow-hidden border border-slate-300 bg-white">
              <button
                type="button"
                onClick={() => setIsAdvancedOpen((value) => !value)}
                aria-expanded={isAdvancedOpen}
                data-open={isAdvancedOpen}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-[background-color] duration-300 [transition-timing-function:var(--ease-soft)] hover:bg-white/40"
              >
                <div>
                  <p className="text-[15px] font-semibold text-stone-900">
                    추가 정보 입력
                  </p>
                  <p className="hidden mt-1 text-sm leading-6 text-stone-600">
                    꼭 필요할 때만 더 열어 입력할 수 있습니다.
                  </p>
                </div>
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-full border border-stone-200 bg-white shadow-sm transition-[background-color,border-color,box-shadow] duration-300 [transition-timing-function:var(--ease-soft)] ${
                    isAdvancedOpen ? "border-stone-300 bg-stone-50" : ""
                  }`}
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 20 20"
                    className="collapsible-chevron h-4 w-4 text-stone-700"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="m5 7.5 5 5 5-5" />
                  </svg>
                </span>
              </button>

              <div
                className="collapsible-panel collapsible-panel-dense"
                data-open={isAdvancedOpen}
              >
                <div className="collapsible-panel-inner">
                  <div className="collapsible-panel-body border-t border-stone-200/80 px-5 pb-5 pt-5">
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <label className={fieldGroupClass}>
                        <span className={fieldLabelClass}>나이</span>
                        <input
                          value={age}
                          onChange={(event) => setAge(event.target.value)}
                          type="number"
                          inputMode="numeric"
                          className={fieldControlClass}
                        />
                      </label>

                      <SelectField
                        label="성별"
                        value={sex}
                        onChange={(nextSex) => {
                          setSex(nextSex);
                          if (nextSex === "male") {
                            setPregnancyStatus("");
                            setLactationStatus("");
                          }
                        }}
                        options={[
                          { value: "", label: "미입력" },
                          { value: "male", label: "남성" },
                          { value: "female", label: "여성" },
                        ]}
                      />

                      <SelectField
                        label="흡연 상태"
                        value={smokerStatus}
                        onChange={setSmokerStatus}
                        options={[
                          { value: "", label: "미입력" },
                          { value: "current", label: "현재 흡연" },
                          { value: "former", label: "과거 흡연" },
                          { value: "never", label: "비흡연" },
                        ]}
                      />

                      <SelectField
                        label="관할권"
                        value={jurisdiction}
                        onChange={setJurisdiction}
                        options={[
                          { value: "", label: "미입력" },
                          { value: "KR", label: "KR" },
                          ...metadata.jurisdictions
                            .filter((item) => item !== "KR")
                            .map((item) => ({ value: item, label: item })),
                        ]}
                      />

                      <SelectField
                        label="임신 상태"
                        value={pregnancyStatus}
                        onChange={(nextPregnancyStatus) =>
                          setPregnancyStatus(
                            normalizePregnancyStatus(nextPregnancyStatus),
                          )
                        }
                        disabled={isMale}
                        options={[
                          {
                            value: "",
                            label: isMale ? "남성 선택 시 비활성" : "미입력",
                          },
                          { value: "not_pregnant", label: "해당 없음" },
                          { value: "pregnant", label: "임신 중" },
                        ]}
                      />

                      <SelectField
                        label="수유 상태"
                        value={lactationStatus}
                        onChange={setLactationStatus}
                        disabled={isMale}
                        options={[
                          {
                            value: "",
                            label: isMale ? "남성 선택 시 비활성" : "미입력",
                          },
                          { value: "lactating", label: "수유 중" },
                        ]}
                      />

                      <label className={`${fieldGroupClass} xl:col-span-2`}>
                        <span className={fieldLabelClass}>알레르기</span>
                        <input
                          value={allergies}
                          onChange={(event) => setAllergies(event.target.value)}
                          placeholder="예: shellfish"
                          className={fieldControlClass}
                        />
                      </label>

                      <label
                        className={`${fieldGroupClass} md:col-span-2 xl:col-span-4`}
                      >
                        <span className={fieldLabelClass}>메모</span>
                        <textarea
                          value={memo}
                          onChange={(event) => setMemo(event.target.value)}
                          rows={2}
                          placeholder="추가로 참고할 복용 방식, 생활 습관, 키워드를 적어둘 수 있습니다."
                          className={`${fieldControlClass} min-h-[6.75rem] resize-y`}
                        />
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-3 overflow-hidden border border-slate-300 bg-white">
              <button
                type="button"
                onClick={() => setIsExamplesOpen((value) => !value)}
                aria-expanded={isExamplesOpen}
                data-open={isExamplesOpen}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-[background-color] duration-300 [transition-timing-function:var(--ease-soft)] hover:bg-white/40"
              >
                <div>
                  <p className="text-[15px] font-semibold text-stone-900">
                    예시 입력
                  </p>
                  <p className="hidden mt-1 text-sm leading-6 text-stone-600">
                    자주 쓰는 조합을 바로 불러와 빠르게 조회할 수 있습니다.
                  </p>
                </div>
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-full border border-stone-200 bg-white shadow-sm transition-[background-color,border-color,box-shadow] duration-300 [transition-timing-function:var(--ease-soft)] ${
                    isExamplesOpen ? "border-stone-300 bg-stone-50" : ""
                  }`}
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 20 20"
                    className="collapsible-chevron h-4 w-4 text-stone-700"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="m5 7.5 5 5 5-5" />
                  </svg>
                </span>
              </button>

              <div
                className="collapsible-panel collapsible-panel-dense"
                data-open={isExamplesOpen}
              >
                <div className="collapsible-panel-inner">
                  <div className="collapsible-panel-body border-t border-stone-200/80 px-5 pb-5 pt-5">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          applyStarterProfile(defaultExampleProfile, {
                            submit: true,
                          })
                        }
                        className={subtleActionButtonClass}
                      >
                        기본 예시로 되돌리기
                      </button>
                      {starterProfiles.map((profile) => (
                        <button
                          key={`starter-inline-${profile.label}`}
                          type="button"
                          onClick={() =>
                            applyStarterProfile(profile, { submit: true })
                          }
                          className={ghostButtonClass}
                        >
                          {profile.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
              <p className="hidden text-sm leading-6 text-muted">
                {hasAnyPrimaryInput
                  ? "직접 관련된 규칙을 먼저 정리하고, 일반 참고 항목은 뒤에서 보조적으로 이어 보여드립니다."
                  : "성분 하나만 먼저 넣고 시작해도 됩니다. 필요한 순간에만 추가 조건을 더해 보세요."}
              </p>
              <div className="flex flex-wrap gap-2 sm:flex-nowrap sm:justify-end">
                <button
                  type="button"
                  disabled={isQueryLoading || isPending}
                  onClick={() =>
                    startTransition(
                      () =>
                        void submitQuery().catch((caught) =>
                          setError(
                            caught instanceof Error
                              ? caught.message
                              : "규칙을 불러오지 못했습니다.",
                          ),
                        ),
                    )
                  }
                  className={`${primaryButtonClass} disabled:cursor-wait disabled:bg-stone-900 disabled:opacity-80`}
                >
                  {isQueryLoading ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-flex h-4 w-4 rounded-full border-2 border-white/35 border-t-white animate-spin" />
                      근거 정리 중
                    </span>
                  ) : (
                    "규칙 조회"
                  )}
                </button>
                <button
                  type="button"
                  onClick={resetForm}
                  className={secondaryButtonClass}
                >
                  전체 초기화
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {response ? (
        <>
          <section className="surface-card rounded-[1.25rem] p-3 md:p-4">
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-stone-950 px-3 py-1.5 text-xs font-semibold text-white">
                  결과 {visibleCount}건
                </span>
                {resultOverview.map((item) => (
                  <span
                    key={`summary-${item.key}`}
                    className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-700"
                  >
                    {item.shortLabel} {item.count}
                  </span>
                ))}
              </div>

              <div className="rounded-[1.1rem] border border-stone-200/90 bg-stone-50/75 p-2.5 md:p-3">
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium text-stone-500">
                      결과 필터
                    </p>
                    {hasActiveResultFilters ? (
                      <button
                        type="button"
                        onClick={resetResultFilters}
                        className="text-sm font-medium text-stone-500 transition duration-150 hover:text-stone-900"
                      >
                        필터 초기화
                      </button>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <CompactSelectChip
                      label="위험도"
                      value={severityFilter}
                      onChange={updateSeverityFilter}
                      options={[
                        { value: "", label: "전체" },
                        { value: "contraindicated", label: "금지" },
                        { value: "avoid", label: "중단/회피" },
                        { value: "warn", label: "강한 주의" },
                        { value: "monitor", label: "일반 주의" },
                      ]}
                      minWidthClassName="min-w-[9.5rem] flex-[1_1_10rem]"
                    />
                    <CompactSelectChip
                      label="정렬"
                      value={sort}
                      onChange={(value) =>
                        updateSort(value as NonNullable<EngineQuery["sort"]>)
                      }
                      options={metadata.sortOptions}
                      minWidthClassName="min-w-[11rem] flex-[1.1_1_12rem]"
                    />
                    <ToggleChip
                      checked={medicationOnly}
                      onChange={updateMedicationOnly}
                      label="약물 관련만"
                      className="min-w-[10rem] flex-[1_1_10rem]"
                    />
                    <ToggleChip
                      checked={diseaseOnly}
                      onChange={updateDiseaseOnly}
                      label="질환 관련만"
                      className="min-w-[10rem] flex-[1_1_10rem]"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="hidden surface-card rounded-[1.5rem] p-5 md:p-6">
            <div className="flex flex-col gap-3 border-b border-border-subtle pb-5 2xl:flex-row 2xl:items-end 2xl:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                  결과
                </p>
                <h2 className="mt-2 text-[clamp(1rem,1.38vw,1.22rem)] font-semibold tracking-[-0.02em] text-foreground">
                  중요한 내용부터 바로 확인하세요
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  먼저 봐야 할 내용과 추가 확인이 필요한 내용을 분리해
                  보여드립니다.
                </p>
              </div>
              <p className="text-sm font-medium text-muted">
                총{" "}
                <span className="font-semibold text-foreground tabular-nums">
                  {visibleCount}
                </span>
                건
              </p>
            </div>

            <div className="mt-5 space-y-4">
              <div className="space-y-2">
                {resultOverview.map((item) => (
                  <div
                    key={item.key}
                    className={`rounded-[1rem] border px-4 py-3.5 ${item.tone}`}
                  >
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <div className="min-w-0 md:flex md:items-center md:gap-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted md:min-w-[4.5rem]">
                          {item.shortLabel}
                        </p>
                        <p className="mt-1 text-sm font-medium leading-5 text-foreground md:mt-0">
                          {item.label}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 md:shrink-0">
                        <p className="text-xs leading-5 text-muted">
                          {item.description}
                        </p>
                        <p className="text-[1.36rem] font-semibold leading-none text-foreground tabular-nums">
                          {item.count}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="rounded-[1rem] border border-stone-200 bg-white p-4 md:p-5">
                <div className="flex flex-col gap-3 border-b border-border-subtle pb-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      결과 보기 설정
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      필요한 범위만 남기도록 필터를 간단히 조절해 보세요.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={resetResultFilters}
                    className={ghostButtonClass}
                    hidden={!hasActiveResultFilters}
                  >
                    필터 초기화
                  </button>
                </div>

                <div className="mt-5 space-y-6">
                  <div>
                    <SelectField
                      label="위험도"
                      value={severityFilter}
                      onChange={updateSeverityFilter}
                      options={[
                        { value: "", label: "전체" },
                        { value: "contraindicated", label: "금지" },
                        { value: "avoid", label: "중단/회피" },
                        { value: "warn", label: "강한 주의" },
                        { value: "monitor", label: "일반 주의" },
                      ]}
                    />
                  </div>

                  <div>
                    <SelectField
                      label="정렬"
                      value={sort}
                      onChange={(value) =>
                        updateSort(value as NonNullable<EngineQuery["sort"]>)
                      }
                      options={metadata.sortOptions}
                    />
                  </div>

                  <div className="pt-1">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                      관련 조건
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <ToggleChip
                        checked={medicationOnly}
                        onChange={updateMedicationOnly}
                        label="약물 관련만"
                      />
                      <ToggleChip
                        checked={diseaseOnly}
                        onChange={updateDiseaseOnly}
                        label="질환 관련만"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </>
      ) : null}

      {isQueryLoading ? <ExplorerLoadingSkeleton /> : null}
      {error ? (
        <div
          aria-live="polite"
          className="rounded-[1.5rem] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800"
        >
          {error}
        </div>
      ) : null}

      {visible ? (
        visibleCount > 0 ? (
          sectionOrder.map((sectionKey, index) => {
            const sectionItems = visible[sectionKey];
            if (sectionItems.length === 0) return null;
            const previewCount = sectionVisibleCounts[sectionKey];
            const visibleItems = sectionItems.slice(0, previewCount);
            const hiddenCount = Math.max(sectionItems.length - previewCount, 0);
            const initialPreviewCount = sectionPreviewCounts[sectionKey];
            const canCollapse = previewCount > initialPreviewCount;
            const presentation = sectionPresentation[sectionKey];
            const revealCountLabel =
              sectionKey === "needs_more_info"
                ? `${Math.min(sectionLoadMoreStep[sectionKey], hiddenCount)}건 더 보기`
                : `${hiddenCount}건 더 보기`;

            return (
              <section
                key={sectionKey}
                className="surface-card rounded-[1.25rem] p-4 motion-safe:animate-[rise-in_620ms_var(--ease-emphasized)_both]"
                style={{ animationDelay: `${index * 90}ms` }}
              >
                <div className="flex flex-col gap-2 border-b border-border-subtle pb-3 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <p className="hidden text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                      {presentation.kicker}
                    </p>
                    <h2 className="text-[0.88rem] font-semibold tracking-[-0.02em] text-foreground md:text-[0.94rem]">
                      {presentation.title}
                    </h2>
                    <p className="hidden mt-2 text-sm leading-6 text-muted">
                      {cleanDisplayText(presentation.summary)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${presentation.chipTone}`}
                    >
                      {sectionItems.length}건
                    </span>
                    <span className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-muted">
                      {sectionLabels[sectionKey]}
                    </span>
                  </div>
                </div>

                <div className="mt-3 space-y-3">
                  {visibleItems.map((match, matchIndex) => (
                    <div
                      key={`${sectionKey}-${match.ruleId}`}
                      className="motion-safe:animate-[rise-in_540ms_var(--ease-emphasized)_both]"
                      style={{
                        animationDelay: `${index * 90 + matchIndex * 45}ms`,
                      }}
                    >
                      <RuleCard
                        match={match}
                        aiRecommendation={
                          aiRuleRecommendations[match.ruleId] ?? null
                        }
                      />
                    </div>
                  ))}

                  {sectionItems.length > initialPreviewCount ? (
                    <div className="rounded-[1rem] border border-stone-200 bg-white px-4 py-4 md:px-5">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <p className="text-sm leading-6 text-muted">
                          {hiddenCount > 0
                            ? `아직 ${hiddenCount}건이 더 남아 있습니다. 필요한 범위까지만 펼쳐서 검토해 보세요.`
                            : "지금은 모든 항목을 펼쳐둔 상태입니다. 다시 접어서 핵심 순서만 볼 수도 있습니다."}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {hiddenCount > 0 ? (
                            <button
                              type="button"
                              onClick={() =>
                                setSectionVisibleCounts((current) => ({
                                  ...current,
                                  [sectionKey]: Math.min(
                                    current[sectionKey] +
                                      sectionLoadMoreStep[sectionKey],
                                    sectionItems.length,
                                  ),
                                }))
                              }
                              className={ghostButtonClass}
                            >
                              {revealCountLabel}
                            </button>
                          ) : null}
                          {canCollapse ? (
                            <button
                              type="button"
                              onClick={() =>
                                setSectionVisibleCounts((current) => ({
                                  ...current,
                                  [sectionKey]: initialPreviewCount,
                                }))
                              }
                              className={secondaryButtonClass}
                            >
                              다시 핵심만 보기
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            );
          })
        ) : (
          <section className="surface-card rounded-[1.5rem] px-6 py-6 md:px-7">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              필터 결과 없음
            </p>
            <h3 className="mt-3 text-[clamp(1rem,1.35vw,1.2rem)] font-semibold tracking-[-0.02em] text-foreground">
              지금 적용된 필터 안에서는 보이는 항목이 없어요.
            </h3>
            <p className="measure-copy mt-3 text-sm leading-6 text-muted">
              위험도나 관련 조건 필터가 좁게 걸려 있을 가능성이 큽니다. 필터를
              조금만 느슨하게 바꾸면 같은 결과 안에서도 다른 판단 근거를 바로
              확인할 수 있어요.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={resetResultFilters}
                className={primaryButtonClass}
              >
                필터 전체 초기화
              </button>
            </div>
          </section>
        )
      ) : !isQueryLoading && hasQueried ? (
        <section className="surface-card rounded-[1.5rem] px-6 py-6 md:px-7">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            {hasQueried ? "결과 없음" : "입력 전"}
          </p>
          <h3 className="mt-3 text-[clamp(1rem,1.35vw,1.2rem)] font-semibold tracking-[-0.02em] text-foreground">
            {hasQueried
              ? "현재 조건으로는 연결된 결과를 찾지 못했어요."
              : "첫 입력은 아주 간단해도 괜찮아요."}
          </h3>
          <p className="measure-copy mt-3 text-sm leading-6 text-muted">
            {hasQueried
              ? "성분 표기나 약물 이름을 조금 다르게 적어 보거나, 질환과 임신 및 수유 상태 같은 조건을 추가하면 더 정확하게 다시 좁혀볼 수 있습니다."
              : "성분만 먼저 넣고 시작해도 됩니다. 개인 조건이 아직 없으면 일반적인 참고 안내를 중심으로 차분하게 보여드립니다."}
          </p>
          {!hasQueried ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {starterProfiles.map((profile) => (
                <button
                  key={`empty-starter-${profile.label}`}
                  type="button"
                  onClick={() => applyStarterProfile(profile, { submit: true })}
                  className={ghostButtonClass}
                >
                  {profile.label}
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {response?.literature ? (
        <LiteratureContextPanel literature={response.literature} />
      ) : null}
    </div>
  );
}
