import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getVerification } from "../api";
import type { JobSnapshot } from "../types";
import StepList from "../components/StepList";
import ResultView from "../components/ResultView";

interface RunNavState {
  abName?: string;
  invoiceName?: string;
}

export default function RunPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state ?? {}) as RunNavState;

  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    async function poll() {
      try {
        const snapshot = await getVerification(runId);
        if (!active) return;
        setJob(snapshot);
        if (snapshot.state === "running") {
          timer = window.setTimeout(poll, 1000);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Lost connection to the run.");
      }
    }

    poll();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [runId]);

  if (error) {
    return (
      <div className="container narrow">
        <p className="eyebrow">VERIFICATION</p>
        <h1 className="headline">Run unavailable</h1>
        <p className="lede">{error}</p>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => navigate("/")}>
            Start a new verification
          </button>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="container narrow">
        <p className="lede">Loading run…</p>
      </div>
    );
  }

  if (job.state === "completed" && job.result) {
    return <ResultView job={job} />;
  }

  if (job.state === "error") {
    return (
      <div className="container narrow">
        <p className="eyebrow">VERIFICATION FAILED</p>
        <h1 className="headline">The run could not be completed</h1>
        <p className="lede">{job.error ?? "Unknown error."}</p>
        <StepList steps={job.steps} />
        <div className="actions">
          <button className="btn btn-primary" onClick={() => navigate("/")}>
            Start a new verification
          </button>
        </div>
      </div>
    );
  }

  const runningIndex = job.steps.findIndex((s) => s.status === "running");
  const doneCount = job.steps.filter((s) => s.status === "done").length;
  const currentStep = runningIndex >= 0 ? runningIndex + 1 : Math.max(doneCount, 1);
  const configLog = job.log.find((entry) => entry.type === "config")?.message;

  return (
    <div className="container narrow">
      <p className="eyebrow">
        VERIFICATION RUNNING · STEP {currentStep} OF {job.steps.length}
      </p>
      <h1 className="headline">
        Comparing {navState.abName ?? "the AB"} with {navState.invoiceName ?? "the invoice"}
      </h1>

      <StepList steps={job.steps} />

      {configLog && <p className="mono-note">{configLog}</p>}

      <p className="muted-note">The result appears here when the evaluator finishes.</p>

      <div className="actions">
        <button className="btn btn-ghost" onClick={() => navigate("/")}>
          Cancel run
        </button>
      </div>
    </div>
  );
}
