import { ApiError } from "@/lib/api";

/** Human-readable message from an ApiError (FastAPI detail may be a string or a 422 array). */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return "network error — the backend is unreachable";
    const body = err.body as { detail?: unknown; code?: unknown } | null;
    const detail = body?.detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
    return `request failed with ${err.status}`;
  }
  if (err instanceof Error) return err.message;
  return "something went wrong";
}
