export function formatEUR(value: number, withSign = false): string {
  const formatted = `€${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
  if (!withSign) return value < 0 ? `-${formatted}` : formatted;
  return value < 0 ? `-${formatted}` : `+${formatted}`;
}

export function formatTolerance(value: number): string {
  return `±€${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
