import React, { useState } from "react";
import { AdvisorIcon } from "../components/AdvisorIcon";
import { Formatters } from "../lib/formatters";
import { Presentation } from "../lib/presentation";
import type { AdvisorDefinition } from "../types/api";

interface AdvisorSelectionScreenProps {
  advisors: AdvisorDefinition[];
  advisorWeights: Record<string, number>;
  selectedAdvisorIds: string[];
  onToggle: (advisorId: string) => void;
  onWeightChange: (advisorId: string, nextWeight: number) => void;
  onContinue: () => void;
}

function allocationFor(
  advisorId: string,
  selectedAdvisorIds: string[],
  advisorWeights: Record<string, number>,
): number {
  if (!selectedAdvisorIds.includes(advisorId)) {
    return 0;
  }
  return Math.round(advisorWeights[advisorId] ?? 0);
}

interface TagOption {
  value: string;
  label: string;
}

const PRIMARY_TAG_OPTIONS: TagOption[] = [
  { value: "all", label: "All" },
  { value: "active", label: "🟢 Active" },
  { value: "investments", label: "💰 Investments" },
  { value: "business", label: "🏢 Business" },
  { value: "books", label: "📚 Books" },
  { value: "films", label: "🎬 Films" },
  { value: "anime", label: "🧠 Anime" },
  { value: "games", label: "🎮 Games" }
];

function safePrimaryTag(advisor: AdvisorDefinition): string {
  const value = (advisor as Partial<AdvisorDefinition>).primary_tag;
  if (typeof value !== "string") {
    return "";
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "investment") {
    return "investments";
  }
  if (normalized === "film") {
    return "films";
  }
  return normalized;
}

function safeTags(advisor: AdvisorDefinition): string[] {
  const value = (advisor as Partial<AdvisorDefinition>).tags;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((tag) => (typeof tag === "string" ? tag.trim().toLowerCase() : ""))
    .filter((tag) => tag !== "");
}

export function AdvisorSelectionScreen(
  props: AdvisorSelectionScreenProps,
): JSX.Element {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState("all");

  const selectedCount = props.selectedAdvisorIds.length;
  const totalWeight = Math.round(
    props.selectedAdvisorIds.reduce(
      (sum, advisorId) => sum + (props.advisorWeights[advisorId] ?? 0),
      0,
    ),
  );
  const canContinue = selectedCount === 3 && totalWeight === 100;
  const canAdjustWeights = selectedCount === 3;

  const filteredAdvisors = props.advisors.filter((advisor) => {
    const advisorPrimaryTag = safePrimaryTag(advisor);
    const advisorTags = safeTags(advisor);
    const isActive = props.selectedAdvisorIds.includes(advisor.id);
    const matchesTag =
      selectedTag === "all" ||
      (selectedTag === "active" && isActive) ||
      advisorPrimaryTag === selectedTag;
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      !query ||
      advisor.name.toLowerCase().includes(query) ||
      advisor.role.toLowerCase().includes(query) ||
      advisorTags.some((tag) => tag.includes(query));
    return matchesTag && matchesSearch;
  });

  return (
    <div className="screen advisors-screen">
      <section className="stack">
        <h1 className="screen-title">Configure Your Team</h1>
        <p className="screen-copy">
          Activate your preferred advisors and allocate their portfolio
          influence.
        </p>
      </section>

      <section className="filter-section">
        <div className="search-wrap">
          <span className="material-symbols-outlined search-icon">search</span>
          <input
            type="text"
            className="search-input"
            placeholder="Search advisors..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="search-clear"
              onClick={() => setSearchQuery("")}
              type="button"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          )}
        </div>

        <div className="tag-filter-row">
          {PRIMARY_TAG_OPTIONS.map((tag) => (
            <button
              key={tag.value}
              className={`tag-filter-pill ${selectedTag === tag.value ? "active" : ""}`}
              onClick={() => setSelectedTag(tag.value)}
              type="button"
            >
              {tag.label}
            </button>
          ))}
        </div>
      </section>

      <section className="advisor-list">
        {filteredAdvisors.map((advisor) => {
          const advisorPrimaryTag = safePrimaryTag(advisor);
          const advisorTags = safeTags(advisor);
          const displayName = Formatters.advisorDisplayName(advisor.id, advisor.name);
          const isActive = props.selectedAdvisorIds.includes(advisor.id);
          const isDisabled = !isActive && selectedCount >= 3;
          const tone = Presentation.advisorAccent(advisorTags);
          const allocation = allocationFor(
            advisor.id,
            props.selectedAdvisorIds,
            props.advisorWeights,
          );
          const toneTag = Formatters.titleCase(
            advisorTags[0] ?? advisor.category,
          );

          return (
            <article
              key={advisor.id}
              className={[
                "advisor-tile",
                `tone-${tone}`,
                isActive ? "active" : "",
                isDisabled ? "disabled" : "",
              ]
                .join(" ")
                .trim()}
              aria-disabled={isDisabled}
              aria-label={
                isActive
                  ? `Deactivate ${displayName}`
                  : `Activate ${displayName}`
              }
              aria-pressed={isActive}
              onClick={() => {
                if (isDisabled) {
                  return;
                }
                props.onToggle(advisor.id);
              }}
              onKeyDown={(event) => {
                if (isDisabled) {
                  return;
                }
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  props.onToggle(advisor.id);
                }
              }}
              role="button"
              tabIndex={isDisabled ? -1 : 0}
            >
              <div className="advisor-card-head">
                <div className="advisor-row">
                  <div className="advisor-avatar-wrap">
                    <div className="advisor-leading">
                      <span className="advisor-primary-icon">
                        {advisorPrimaryTag === "investments"
                          ? "💰"
                          : advisorPrimaryTag === "business"
                            ? "🏢"
                            : advisorPrimaryTag === "books"
                              ? "📚"
                              : advisorPrimaryTag === "films"
                                ? "🎬"
                                : advisorPrimaryTag === "anime"
                                  ? "🧠"
                                  : advisorPrimaryTag === "games"
                                    ? "🎮"
                                    : "🏷️"}
                      </span>
                      <div className={`advisor-avatar tone-${tone}`}>
                        <AdvisorIcon
                          advisorId={advisor.id}
                          className="advisor-face-icon"
                          tablerIcon={advisor.tabler_icon}
                        />
                      </div>
                    </div>
                    <span className="advisor-tag">{toneTag}</span>
                  </div>
                  <div>
                    <strong>{displayName}</strong>
                    <p className="advisor-role">{advisor.role}</p>
                  </div>
                </div>

                <button
                  aria-label={
                    isActive
                      ? `Deactivate ${displayName}`
                      : `Activate ${displayName}`
                  }
                  className={isActive ? "toggle active" : "toggle"}
                  disabled={isDisabled}
                  onClick={(event) => {
                    event.stopPropagation();
                    props.onToggle(advisor.id);
                  }}
                  type="button"
                />
              </div>

              <div
                className={
                  isActive && canAdjustWeights
                    ? "allocation-meter"
                    : "allocation-meter disabled-control"
                }
                onClick={(event) => event.stopPropagation()}
              >
                <div className="summary-head">
                  <span className="muted">Allocation Weight</span>
                  <span className="signal-pill buy">{allocation}% Weight</span>
                </div>
                <input
                  aria-label={`${displayName} allocation weight`}
                  disabled={!isActive || !canAdjustWeights}
                  max="100"
                  min="0"
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) =>
                    props.onWeightChange(advisor.id, Number(event.target.value))
                  }
                  step="1"
                  type="range"
                  value={allocation}
                />
                <p className="advisor-description">
                  {advisor.style[0] ?? "Strategic advisor"}
                </p>
              </div>
            </article>
          );
        })}
        {filteredAdvisors.length === 0 && (
          <div className="empty-state">
            <span className="material-symbols-outlined">search_off</span>
            <p>No advisors match your search</p>
          </div>
        )}
      </section>

      <section className="sticky-action">
        <div className="muted center-text">
          {selectedCount}/3 Advisors Selected · {totalWeight}% Weighted
        </div>
        <button
          className="cta-button"
          disabled={!canContinue}
          onClick={props.onContinue}
          type="button"
        >
          Confirm Team ({totalWeight}%)
        </button>
      </section>
    </div>
  );
}
