import { useMemo, useState, type KeyboardEvent } from "react";
import { runDemoReconciliation } from "./api";
import type { ReconciliationResult, Report, ResultStatus } from "./types";

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

const statusLabels: Record<ResultStatus, string> = {
  auto_matched: "Auto-matched",
  ai_assisted: "Assisted match",
  needs_review: "Needs review",
};

function inr(paise: number) {
  return currency.format(paise / 100);
}

function downloadReport(report: Report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "paisamatch-demo-report.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

function MetricCard({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <article className="metric-card">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{caption}</span>
    </article>
  );
}

function ResultRow({ item, selected, onSelect }: { item: ReconciliationResult; selected: boolean; onSelect: () => void }) {
  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect();
    }
  }

  return (
    <>
      <tr className={selected ? "selected" : ""} onClick={onSelect} onKeyDown={handleKeyDown} tabIndex={0} aria-label={`Show audit details for ${item.order_id}`}>
        <td>
          <b>{item.order_id}</b>
          <small>{item.payment_id}</small>
        </td>
        <td>{inr(item.gross_amount)}</td>
        <td><span className={`status ${item.status}`}>{statusLabels[item.status]}</span></td>
        <td>{item.settlement_id ?? "—"}</td>
        <td>{item.confidence ? `${Math.round(item.confidence * 100)}%` : "—"}</td>
      </tr>
      {selected && (
        <tr className="audit-row">
          <td colSpan={5}>
            <p><b>Decision:</b> {item.explanation}</p>
            {item.exception_code && <p><b>Exception:</b> {item.exception_code}</p>}
            <ol>
              {item.audit.map((entry) => <li key={`${entry.step}-${entry.detail}`}><b>{entry.step.replaceAll("_", " ")}:</b> {entry.detail}</li>)}
            </ol>
          </td>
        </tr>
      )}
    </>
  );
}

export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [filter, setFilter] = useState<"all" | "needs_review">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleResults = useMemo(() => {
    if (!report) return [];
    return filter === "all" ? report.results : report.results.filter((item) => item.status === "needs_review");
  }, [filter, report]);

  async function runDemo() {
    setLoading(true);
    setError(null);
    setSelectedId(null);
    try {
      setReport(await runDemoReconciliation());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load the demo report.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div className="brand"><span aria-hidden="true">₹</span><div><b>PaisaMatch</b><small>Verifiable AI finance controller</small></div></div>
        <div className="topbar-meta"><span className="environment">DEMO MODE</span><span>Track 4 · AI Finance Controller</span></div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">SETTLEMENT CONTROL, NOT JUST SUMMARIES</p>
          <h1>Reconcile the records.<br /><em>Prove the result.</em></h1>
          <p className="lead">PaisaMatch uses deterministic checks for money, then asks AI only to resolve constrained ambiguity. Anything that cannot be proven stays in the exception queue.</p>
        </div>
        <div className="hero-actions">
          <button className="primary" onClick={runDemo} disabled={loading}>{loading ? "Reconciling…" : report ? "Run demo again" : "Run 72-record demo"}</button>
          <p>3 sources · 72 merchant orders · labelled ground truth</p>
        </div>
      </section>

      {error && <div className="error" role="alert">{error} Start FastAPI on port 8000, then try again.</div>}

      {!report && !error && (
        <section className="empty-state">
          <div className="empty-icon">↔</div>
          <h2>Your audit-ready batch is waiting</h2>
          <p>Run the demo to reconcile merchant orders, Razorpay-style settlements and bank deposits.</p>
        </section>
      )}

      {report && (
        <>
          <section className="metrics" aria-label="Reconciliation metrics">
            <MetricCard label="Match rate" value={`${report.metrics.match_rate}%`} caption={`${report.metrics.auto_matched} exact + ${report.metrics.ai_assisted} assisted`} />
            <MetricCard label="Assisted uplift" value={`+${report.metrics.assisted_uplift} pp`} caption={`From ${report.metrics.baseline_match_rate}% exact-only baseline`} />
            <MetricCard label="Precision" value={`${report.metrics.precision}%`} caption="Compared with hidden ground truth" />
            <MetricCard label="Unresolved value" value={inr(report.metrics.unresolved_value)} caption={`${report.metrics.needs_review} records need review`} />
          </section>

          <section className="report-toolbar">
            <div>
              <p className="eyebrow">BATCH REPORT</p>
              <h2>Every decision has evidence.</h2>
              <p className="mode">Resolver: {report.metrics.model_mode}</p>
              <div className="run-evidence" role="group" aria-label="Run evidence">
                <span>{report.metrics.model_calls} hosted model {report.metrics.model_calls === 1 ? "call" : "calls"}</span>
                <span>{report.metrics.resolver_latency_ms} ms resolver time</span>
                <span>{inr(report.metrics.financial_variance)} accepted-match variance</span>
              </div>
            </div>
            <div className="toolbar-actions">
              <button className={filter === "all" ? "filter active" : "filter"} onClick={() => setFilter("all")}>All records</button>
              <button className={filter === "needs_review" ? "filter active" : "filter"} onClick={() => setFilter("needs_review")}>Exceptions ({report.metrics.needs_review})</button>
              <button className="download" onClick={() => downloadReport(report)}>Download JSON</button>
            </div>
          </section>

          <section className="table-wrap">
            <table>
              <thead><tr><th>Merchant order</th><th>Gross amount</th><th>Outcome</th><th>Settlement</th><th>Confidence</th></tr></thead>
              <tbody>
                {visibleResults.map((item) => (
                  <ResultRow key={item.order_id} item={item} selected={selectedId === item.order_id} onSelect={() => setSelectedId(selectedId === item.order_id ? null : item.order_id)} />
                ))}
              </tbody>
            </table>
          </section>
          <p className="table-note">Select a record to inspect the audit trail. The included data is synthetic and contains no customer PII.</p>
        </>
      )}
    </main>
  );
}
