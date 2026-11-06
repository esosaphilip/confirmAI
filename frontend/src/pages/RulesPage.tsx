import { useEffect, useState } from "react";
import { getRules, saveRules } from "../api";
import { formatEUR } from "../format";

const PRESETS: { label: string; value: number }[] = [
  { label: "Exact", value: 0 },
  { label: "€1.00", value: 1 },
  { label: "€5.00", value: 5 },
  { label: "€25.00", value: 25 },
];

const PREVIEW_AB = 1200.0;
const PREVIEW_INVOICE = 1203.5;

export default function RulesPage() {
  const [tolerance, setTolerance] = useState(5);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getRules()
      .then((rules) => setTolerance(rules.price_tolerance_eur))
      .catch(() => setError("Could not load the current rules."));
  }, []);

  const previewDifference = PREVIEW_INVOICE - PREVIEW_AB;
  const previewPasses = previewDifference <= tolerance;

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const updated = await saveRules({ price_tolerance_eur: tolerance });
      setTolerance(updated.price_tolerance_eur);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the rules.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container narrow">
      <p className="eyebrow">MATCHING RULES</p>
      <h1 className="headline">Matching rules</h1>
      <p className="lede">Applied to the next verification run.</p>

      <section className="card card-pad">
        <p className="field-label">Price tolerance</p>
        <p className="mono-hint">price_tolerance_eur</p>
        <div className="input-eur">
          <span className="input-eur-symbol">€</span>
          <input
            type="number"
            min={0}
            step={0.01}
            value={Number.isNaN(tolerance) ? "" : tolerance}
            onChange={(e) => setTolerance(Number(e.target.value))}
          />
        </div>
        <p className="help-text">
          The largest difference in euros allowed between the invoice price and the AB price. A gap
          up to this amount still returns POSITIVE. A larger gap returns NEGATIVE and is listed as a
          discrepancy. Set it to 0.00 to require an exact match.
        </p>
      </section>

      <section className="block">
        <p className="block-label">QUICK PRESETS</p>
        <div className="presets">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`preset${tolerance === preset.value ? " preset-active" : ""}`}
              onClick={() => setTolerance(preset.value)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      <section className="block">
        <p className="block-label">IMPACT PREVIEW</p>
        <div className="card card-pad">
          <div className="preview-row">
            <span>AB price</span>
            <span>{formatEUR(PREVIEW_AB)}</span>
          </div>
          <div className="preview-row">
            <span>Invoice price</span>
            <span>{formatEUR(PREVIEW_INVOICE)}</span>
          </div>
          <div className="preview-row">
            <span>Difference</span>
            <span>{formatEUR(previewDifference)}</span>
          </div>
          <div className="preview-row">
            <span>Your tolerance</span>
            <span>{formatEUR(tolerance)}</span>
          </div>
          <p className={`preview-verdict ${previewPasses ? "positive" : "negative"}`}>
            This example would {previewPasses ? "pass as POSITIVE" : "fail as NEGATIVE"}
          </p>
        </div>
      </section>

      {error && <p className="form-error">{error}</p>}
      {saved && <p className="form-ok">Rules saved.</p>}

      <div className="actions split">
        <button type="button" className="btn btn-ghost" onClick={() => setTolerance(5)}>
          Reset to €5.00
        </button>
        <button type="button" className="btn btn-primary" onClick={apply} disabled={busy}>
          {busy ? "Saving…" : "Apply rules"}
        </button>
      </div>
    </div>
  );
}
