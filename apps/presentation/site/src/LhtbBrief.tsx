import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  ExternalLink,
  FlaskConical,
  GitCompareArrows,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { usePublicPageNavigation } from "./usePublicPageNavigation";
import study from "../../../../benchmark/LHTB/studies/five-arm-gpt56sol-max/data.json";
import copy from "./lhtb-copy.json";

type Language = "en" | "zh";
type ArmKey = keyof typeof study.arms;
type TaskRow = (typeof study.tasks)[number];
type TableMode = "all" | "spread" | "heartbeat";

const armOrder: ArmKey[] = [
  "plain",
  "native_goal",
  "ssh_goal",
  "legacy_heartbeat",
  "new_heartbeat",
];

const contributorLinks = [
  { label: "@shangzh0", href: "https://github.com/shangzh0" },
  { label: "@gwh6669999", href: "https://github.com/gwh6669999" },
  { label: "Bouwen Zhou", href: "https://bouwenzhou.github.io/" },
  { label: "Wanli Lee", href: "https://wanli-lee.github.io/" },
] as const;

const studyUrl = "https://github.com/huangruiteng/loopx/tree/main/benchmark/LHTB";

function formatMillions(value: number) {
  return `${(value / 1_000_000).toFixed(2)}M`;
}

function formatReward(value: number) {
  return value.toFixed(3);
}

function rewardSpread(row: TaskRow) {
  const values = armOrder.map((arm) => row[arm]);
  return Math.max(...values) - Math.min(...values);
}

export function LhtbBrief() {
  const [language, setLanguage] = usePublicPageNavigation();
  const [query, setQuery] = useState("");
  const [tableMode, setTableMode] = useState<TableMode>("all");
  const c = copy[language];
  const basePath = import.meta.env.BASE_URL;

  useEffect(() => {
    document.title = language === "zh"
      ? "LoopX × LHTB：五种长程执行机制"
      : "LoopX × LHTB: five long-horizon execution mechanisms";
  }, [language]);

  const visibleTasks = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return study.tasks.filter((row) => {
      if (normalized && !row.task.toLowerCase().includes(normalized)) return false;
      if (tableMode === "spread") return rewardSpread(row) >= 0.2;
      if (tableMode === "heartbeat") {
        return Math.abs(row.new_heartbeat - row.legacy_heartbeat) >= 0.05;
      }
      return true;
    });
  }, [query, tableMode]);

  return (
    <div className="bm-page lhtb-page" id="top">
      <header className="bm-topbar">
        <a href={`${basePath}${language === "zh" ? "?lang=zh" : ""}`} className="bm-home-link">
          <ArrowLeft size={14} /> {c.back}
        </a>
        <span className="bm-edition">RESEARCH BRIEF / LHTB</span>
        <div className="bm-top-actions">
          <div className="bm-language" aria-label="Language">
            <button aria-pressed={language === "en"} className={language === "en" ? "is-active" : ""} onClick={() => setLanguage("en")} type="button">EN</button>
            <button aria-pressed={language === "zh"} className={language === "zh" ? "is-active" : ""} onClick={() => setLanguage("zh")} type="button">中文</button>
          </div>
          <a href={studyUrl} target="_blank" rel="noreferrer">
            {c.source} <ExternalLink size={13} />
          </a>
        </div>
      </header>

      <main>
        <section className="bm-hero bm-shell lhtb-hero">
          <div className="bm-hero-copy">
            <p className="bm-eyebrow"><FlaskConical size={14} /> {c.meta}</p>
            <h1>{c.title}</h1>
            <p className="bm-deck">{c.deck}</p>
            <div className="bm-hero-meta">
              <span className="bm-evidence-tag"><ShieldCheck size={14} /> {c.evidenceTag}</span>
              <p className="bm-contributors">
                <span>{c.contributorsLabel}</span>
                {contributorLinks.map((person) => (
                  <a href={person.href} key={person.href} target="_blank" rel="noreferrer">
                    {person.label}<ExternalLink size={11} />
                  </a>
                ))}
              </p>
            </div>
          </div>
        </section>

        <nav className="bm-reading-path bm-shell" aria-label={c.readingLabel}>
          {c.readingPath.map(([number, label, href]) => (
            <a href={href} key={href}><span>{number}</span><b>{label}</b></a>
          ))}
        </nav>

        <section className="bm-section bm-shell bm-summary" id="result">
          <div className="bm-section-lead bm-section-lead-wide">
            <p className="bm-kicker">{c.resultEyebrow}</p>
            <h2>{c.resultTitle}</h2>
            <p>{c.resultBody}</p>
          </div>
          <div className="bm-table-wrap lhtb-summary-table">
            <table>
              <thead><tr>{c.summaryColumns.map((label) => <th key={label}>{label}</th>)}</tr></thead>
              <tbody>
                {armOrder.map((arm) => {
                  const row = study.arms[arm];
                  const isNew = arm === "new_heartbeat";
                  const tokens = "tokens" in row
                    ? formatMillions(row.tokens)
                    : `${formatMillions(row.input_tokens)} in / ${formatMillions(row.output_tokens)} out`;
                  const cost = "estimated_cost_usd" in row ? row.estimated_cost_usd : row.recorded_cost_usd;
                  return (
                    <tr className={isNew ? "is-highlight" : undefined} key={arm}>
                      <th scope="row"><code>{c.armLabels[arm]}</code><span>{c.armKinds[arm]}</span></th>
                      <td><strong>{row.mean_reward.toFixed(4)}</strong></td>
                      <td>{row.pass_095}/46</td>
                      <td>{tokens}</td>
                      <td>${cost.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="lhtb-delta-strip">
            <div><strong>+{study.heartbeat_comparison.mean_delta.toFixed(4)}</strong><span>{c.deltaMean}</span></div>
            <div><strong>{study.heartbeat_comparison.wins}</strong><span>{c.deltaWins}</span></div>
            <div><strong>{study.heartbeat_comparison.ties}</strong><span>{c.deltaTies}</span></div>
            <div><strong>{study.heartbeat_comparison.losses}</strong><span>{c.deltaLosses}</span></div>
          </div>
          <p className="bm-runner-note"><strong>{c.readingNoteLabel}</strong>{c.readingNote}</p>
        </section>

        <section className="bm-section bm-shell" id="benchmark">
          <div className="bm-section-lead">
            <p className="bm-kicker">{c.benchmarkEyebrow}</p>
            <h2>{c.benchmarkTitle}</h2>
            <p>{c.benchmarkBody}</p>
          </div>
          <div className="lhtb-official-links">
            {c.officialLinks.map(([label, body, href]) => (
              <a href={href} key={href} target="_blank" rel="noreferrer">
                <div><strong>{label}</strong><p>{body}</p></div><ArrowUpRight size={18} />
              </a>
            ))}
          </div>
          <div className="bm-fact-grid">
            {c.benchmarkFacts.map(([value, label, note]) => (
              <article key={label}><strong>{value}</strong><span>{label}</span><small>{note}</small></article>
            ))}
          </div>
        </section>

        <section className="bm-section bm-shell" id="mechanisms">
          <div className="bm-section-lead bm-section-lead-wide">
            <p className="bm-kicker">{c.mechanismEyebrow}</p>
            <h2>{c.mechanismTitle}</h2>
            <p>{c.mechanismBody}</p>
          </div>
          <div className="lhtb-arm-flow">
            {c.mechanismRows.map(([key, title, owner, body], index) => (
              <article className={key === "new_heartbeat" ? "is-new" : undefined} key={key}>
                <span>0{index + 1}</span>
                <div><h3>{title}</h3><small>{owner}</small><p>{body}</p></div>
              </article>
            ))}
          </div>
        </section>

        <section className="bm-section bm-shell lhtb-insight-section" id="insights">
          <div className="bm-section-lead bm-section-lead-wide">
            <p className="bm-kicker">{c.insightEyebrow}</p>
            <h2>{c.insightTitle}</h2>
            <p>{c.insightBody}</p>
          </div>
          <div className="bm-insight-grid lhtb-insight-grid">
            {c.insights.map(([title, body], index) => (
              <article key={title}><span>0{index + 1}</span><h3>{title}</h3><p>{body}</p></article>
            ))}
          </div>
          <div className="lhtb-cases">
            <div>
              <p className="bm-kicker">{c.gainTitle}</p>
              {c.gainCases.map(([task, before, after, note]) => (
                <article key={task}><h3>{task}</h3><strong>{before} → {after}</strong><p>{note}</p></article>
              ))}
            </div>
            <div>
              <p className="bm-kicker lhtb-caution">{c.lossTitle}</p>
              {c.lossCases.map(([task, before, after, note]) => (
                <article key={task}><h3>{task}</h3><strong>{before} → {after}</strong><p>{note}</p></article>
              ))}
            </div>
          </div>
        </section>

        <section className="bm-section bm-shell" id="scores">
          <div className="bm-section-lead bm-section-lead-wide">
            <p className="bm-kicker">{c.scoresEyebrow}</p>
            <h2>{c.scoresTitle}</h2>
            <p>{c.scoresBody}</p>
          </div>
          <div className="lhtb-table-tools">
            <label><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={c.searchPlaceholder} /></label>
            <div className="lhtb-segments" aria-label={c.filterLabel}>
              {(["all", "spread", "heartbeat"] as TableMode[]).map((mode) => (
                <button className={tableMode === mode ? "is-active" : undefined} onClick={() => setTableMode(mode)} type="button" key={mode}>
                  {c.filters[mode]}
                </button>
              ))}
            </div>
          </div>
          <div className="bm-table-wrap lhtb-task-table">
            <table>
              <thead><tr><th>{c.taskColumn}</th>{armOrder.map((arm) => <th key={arm}>{c.armLabels[arm]}</th>)}</tr></thead>
              <tbody>
                {visibleTasks.map((row) => {
                  const best = Math.max(...armOrder.map((arm) => row[arm]));
                  return (
                    <tr key={row.task}>
                      <th scope="row"><code>{row.task}</code></th>
                      {armOrder.map((arm) => (
                        <td className={row[arm] === best ? "is-best" : undefined} key={arm}>{formatReward(row[arm])}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="lhtb-visible-count">{c.visibleCount.replace("{count}", String(visibleTasks.length))}</p>
        </section>

        <section className="bm-section bm-shell lhtb-program" id="program">
          <div>
            <p className="bm-kicker">{c.programEyebrow}</p>
            <h2>{c.programTitle}</h2>
            <p>{c.programBody}</p>
          </div>
          <div className="lhtb-program-map">
            {c.programSteps.map(([title, body], index) => (
              <article key={title}><span>{index + 1}</span><div><h3>{title}</h3><p>{body}</p></div></article>
            ))}
            <a href={c.programUrl} target="_blank" rel="noreferrer">{c.programAction}<ExternalLink size={14} /></a>
          </div>
        </section>

        <section className="bm-section bm-shell bm-boundary" id="limits">
          <div>
            <p className="bm-kicker">{c.limitsEyebrow}</p>
            <h2>{c.limitsTitle}</h2>
            <ul>{c.limits.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <aside>
            <GitCompareArrows size={24} />
            <h3>{c.nextTitle}</h3>
            <p>{c.nextBody}</p>
          </aside>
        </section>

        <section className="bm-section bm-shell" id="sources">
          <div className="bm-section-lead bm-section-lead-wide">
            <p className="bm-kicker">{c.sourcesEyebrow}</p>
            <h2>{c.sourcesTitle}</h2>
          </div>
          <div className="bm-source-list">
            {c.sourceItems.map(([title, body, href], index) => (
              <a href={href} target="_blank" rel="noreferrer" key={title}>
                <span>0{index + 1}</span><div><strong>{title}</strong><p>{body}</p></div><ExternalLink size={15} />
              </a>
            ))}
          </div>
          <p className="lhtb-attestation"><CheckCircle2 size={15} /> {c.attestation}</p>
        </section>
      </main>

      <footer className="bm-footer bm-shell"><span>LoopX / LHTB Research Brief</span><p>{c.footer}</p><a href="#top">{c.backTop}</a></footer>
    </div>
  );
}
