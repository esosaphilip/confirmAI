import { useRef, useState, type DragEvent } from "react";
import { formatBytes } from "../format";

interface FileDropProps {
  index: string;
  title: string;
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
}

const MAX_BYTES = 20 * 1024 * 1024;

export default function FileDrop({ index, title, file, onFile, disabled }: FileDropProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const isPdf = !!file && file.name.toLowerCase().endsWith(".pdf");
  const underLimit = !!file && file.size <= MAX_BYTES;
  const ready = isPdf && underLimit;

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) onFile(dropped);
  }

  return (
    <div className={`doc-card${file ? " filled" : ""}`}>
      <div className="doc-card-head">
        <span className="doc-index">{index}</span>
        <div className="doc-titles">
          <p className="doc-title">{title}</p>
          <p className="doc-status">{ready ? "Ready" : file ? "Check file" : "Awaiting upload"}</p>
        </div>
        <span className={`pill ${ready ? "pill-ready" : "pill-empty"}`}>
          {ready ? "PDF" : "—"}
        </span>
      </div>

      <div
        className={`dropzone${dragging ? " dragging" : ""}${file ? " has-file" : ""}`}
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        {file ? (
          <>
            <p className="drop-filename">{file.name}</p>
            <p className="drop-meta">
              {formatBytes(file.size)} · click to replace
            </p>
          </>
        ) : (
          <>
            <p className="drop-filename">Drop {title} here</p>
            <p className="drop-meta">or click to browse · PDF up to 20 MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          disabled={disabled}
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <ul className="checks">
        <li className={isPdf ? "ok" : "muted"}>
          <span className="tick">{isPdf ? "✓" : "•"}</span> File type PDF {isPdf ? "accepted" : "required"}
        </li>
        <li className={underLimit ? "ok" : "muted"}>
          <span className="tick">{underLimit ? "✓" : "•"}</span> Under 20 MB
        </li>
        <li className="muted">
          <span className="tick">•</span> Text readability is checked when the run starts
        </li>
      </ul>
    </div>
  );
}
