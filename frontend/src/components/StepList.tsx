import type { Step } from "../types";

const LABEL: Record<Step["status"], string> = {
  done: "DONE",
  running: "RUNNING",
  queued: "QUEUED",
  error: "ERROR",
};

function StepIcon({ status }: { status: Step["status"] }) {
  if (status === "done") return <span className="step-icon done">✓</span>;
  if (status === "error") return <span className="step-icon error">!</span>;
  if (status === "running") return <span className="step-icon running" aria-label="running" />;
  return <span className="step-icon queued" />;
}

export default function StepList({ steps }: { steps: Step[] }) {
  return (
    <ol className="steps">
      {steps.map((step) => (
        <li key={step.key} className={`step step-${step.status}`}>
          <span className="step-number">{step.id}</span>
          <div className="step-main">
            <div className="step-head">
              <p className="step-title">{step.title}</p>
              <span className={`step-label step-label-${step.status}`}>{LABEL[step.status]}</span>
            </div>
            <p className="step-desc">{step.description}</p>
          </div>
          <StepIcon status={step.status} />
        </li>
      ))}
    </ol>
  );
}
