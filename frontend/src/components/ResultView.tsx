import { Link, useNavigate } from "react-router-dom";
import type { JobSnapshot } from "../types";
import { formatEUR, formatTolerance } from "../format";

export default function ResultView({ job }: { job: JobSnapshot }) {
  const navigate = useNavigate();
  const result = job.result!;
  const isNegative = result.status === "NEGATIVE";
  const difference = result.difference;
  const isHigher = difference > 0;

  const headline = isNegative
    ? `Invoice price is ${isHigher ? "higher" : "lower"} than the AB`
    : "Invoice matches the order confirmation";

  const subtext = isNegative
    ? `The invoice is ${formatEUR(Math.abs(difference))} ${
        isHigher ? "above" : "below"
      } the confirmed price, outside your ${formatEUR(result.tolerance)} tolerance. Check with the supplier before releasing.`
    : `The gap of ${formatEUR(Math.abs(difference))} is within your ${formatEUR(
        result.tolerance,
      )} tolerance, so the invoice can be released.`;

  const ratio =
    isNegative && result.tolerance > 0
      ? Math.round(Math.abs(difference) / result.tolerance)
      : null;

  function downloadReport() {
    const lines = [
      "confirmAI · Verification report",
      "================================",
      `Status:            ${result.status}`,
      `Checked:           ${result.checked_at}`,
      `Order confirmation:${result.ab_number ?? "—"}`,
      `Invoice:           ${result.invoice_number ?? "—"}`,
      "",
      `Invoice price (net): ${formatEUR(result.invoice_price)}`,
      `AB price (net):      ${formatEUR(result.ab_price)}`,
      `Difference:          ${formatEUR(difference, true)}`,
      `Allowed tolerance:   ${formatTolerance(result.tolerance)}`,
      `Outcome:             ${isNegative ? "Exceeds tolerance" : "Within tolerance"}`,
      "",
      "Discrepancies:",
      ...(result.discrepancies.length
        ? result.discrepancies.map((d) => `- ${d}`)
        : ["- none"]),
      "",
      "Tolerance log:",
      ...job.log.map((entry) => `${entry.time}  ${entry.type.padEnd(8)} ${entry.message}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `confirmAI-report-${job.run_id}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="container">
      <div className="result-top">
        <p className="eyebrow">New verification</p>
        <span className={`tag ${isNegative ? "tag-negative" : "tag-positive"}`}>
          {result.status}
        </span>
      </div>

      <h1 className="headline">{headline}</h1>
      <p className="lede">{subtext}</p>

      <div className="meta-grid card">
        <div className="meta-cell">
          <p className="meta-label">ORDER CONFIRMATION</p>
          <p className="meta-value">{result.ab_number ?? "—"}</p>
        </div>
        <div className="meta-cell">
          <p className="meta-label">INVOICE</p>
          <p className="meta-value">{result.invoice_number ?? "—"}</p>
        </div>
        <div className="meta-cell">
          <p className="meta-label">SUPPLIER</p>
          <p className="meta-value">—</p>
        </div>
        <div className="meta-cell">
          <p className="meta-label">CHECKED</p>
          <p className="meta-value">{result.checked_at}</p>
        </div>
      </div>

      <section className="block">
        <p className="block-label">Financial summary</p>
        <div className={`card card-pad summary${isNegative ? " summary-negative" : " summary-positive"}`}>
          <div className="summary-row">
            <div>
              <p className="summary-label">INVOICE PRICE · NET</p>
              <p className="summary-sub">{result.invoice_filename ?? "—"}</p>
            </div>
            <p className="summary-value">{formatEUR(result.invoice_price)}</p>
          </div>
          <div className="summary-row">
            <div>
              <p className="summary-label">AB PRICE · NET</p>
              <p className="summary-sub">{result.ab_filename ?? "—"}</p>
            </div>
            <p className="summary-value">{formatEUR(result.ab_price)}</p>
          </div>
          <div className="summary-row summary-row-strong">
            <p className="summary-label">Difference</p>
            <p className={`summary-value ${isNegative ? "danger" : "success"}`}>
              {formatEUR(difference, true)}
            </p>
          </div>
          <div className="summary-row">
            <p className="summary-label">Allowed tolerance</p>
            <p className="summary-value">{formatTolerance(result.tolerance)}</p>
          </div>
          <div className="summary-row">
            <p className="summary-label">Outcome</p>
            <p className={`summary-value ${isNegative ? "danger" : "success"}`}>
              {isNegative ? "Exceeds tolerance" : "Within tolerance"}
            </p>
          </div>
        </div>
      </section>

      <section className="block">
        <p className="block-label">
          Discrepancies · {result.discrepancies.length} found
        </p>
        {result.discrepancies.length === 0 ? (
          <div className="card card-pad">
            <p className="muted-note">No discrepancies — the invoice is within tolerance.</p>
          </div>
        ) : (
          result.discrepancies.map((message, index) => (
            <div className="card card-pad discrepancy" key={index}>
              <div className="discrepancy-head">
                <p className="discrepancy-eyebrow">TOTAL</p>
                <div className="discrepancy-tags">
                  {ratio !== null && <span className="chip chip-danger">{ratio}× limit</span>}
                  <span className={`chip ${isNegative ? "chip-danger" : "chip-success"}`}>
                    {formatEUR(difference, true)}
                  </span>
                </div>
              </div>
              <p className="discrepancy-title">
                {isNegative ? "Net total outside tolerance" : "Net total within tolerance"}
              </p>
              <p className="discrepancy-body">{message}</p>
            </div>
          ))
        )}
      </section>

      <section className="block">
        <p className="block-label">Tolerance log</p>
        <div className="log-card">
          {job.log.map((entry, index) => (
            <div className="log-row" key={index}>
              <span className="log-time">{entry.time}</span>
              <span className={`log-type log-type-${entry.type}`}>{entry.type}</span>
              <span className="log-message">{entry.message}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="actions split">
        <button className="btn btn-primary" onClick={downloadReport}>
          Download report
        </button>
        <button className="btn btn-ghost" onClick={() => navigate("/")}>
          Start new verification
        </button>
      </div>
      <p className="muted-note">
        <Link to="/history" className="link-quiet">
          Go to history
        </Link>
      </p>
    </div>
  );
}
