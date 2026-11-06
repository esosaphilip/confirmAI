export default function HistoryPage() {
  return (
    <div className="container narrow">
      <p className="eyebrow">HISTORY</p>
      <h1 className="headline">Verification history</h1>
      <p className="lede">
        Past runs will be listed here with their outcome and discrepancies.
      </p>
      <div className="card card-pad empty-state">
        <p className="empty-title">No verifications yet</p>
        <p className="muted-note">
          Run your first check from the Verify tab. Persisted history is planned for a later phase.
        </p>
      </div>
    </div>
  );
}
