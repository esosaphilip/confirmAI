import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createVerification, getRules } from "../api";
import FileDrop from "../components/FileDrop";
import { formatEUR } from "../format";

export default function VerifyPage() {
  const navigate = useNavigate();
  const [abFile, setAbFile] = useState<File | null>(null);
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);
  const [tolerance, setTolerance] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRules()
      .then((rules) => setTolerance(rules.price_tolerance_eur))
      .catch(() => setTolerance(5));
  }, []);

  const canRun = !!abFile && !!invoiceFile && !submitting;

  async function runVerification() {
    if (!abFile || !invoiceFile) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await createVerification(
        abFile,
        invoiceFile,
        tolerance ?? undefined,
      );
      navigate(`/runs/${job.run_id}`, {
        state: { abName: abFile.name, invoiceName: invoiceFile.name },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the verification.");
      setSubmitting(false);
    }
  }

  return (
    <div className="container">
      <p className="eyebrow">NEW VERIFICATION</p>
      <h1 className="headline">Check an invoice against its order confirmation</h1>
      <p className="lede">
        Upload the supplier&apos;s Auftragsbestätigung (AB) and the matching invoice. confirmAI reads
        both documents and compares prices against your tolerance rules.
      </p>

      <div className="doc-grid">
        <FileDrop index="01" title="Order confirmation (AB)" file={abFile} onFile={setAbFile} disabled={submitting} />
        <FileDrop index="02" title="Invoice (Rechnung)" file={invoiceFile} onFile={setInvoiceFile} disabled={submitting} />
      </div>

      <div className="tolerance-row card">
        <div>
          <p className="field-label">Price tolerance</p>
          <p className="tolerance-value">
            {tolerance === null ? "…" : formatEUR(tolerance)}
          </p>
        </div>
        <Link to="/rules" className="link-quiet">
          Edit matching rules
        </Link>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="actions">
        <button type="button" className="btn btn-primary" disabled={!canRun} onClick={runVerification}>
          {submitting ? "Starting…" : "Run verification"}
        </button>
      </div>
    </div>
  );
}
