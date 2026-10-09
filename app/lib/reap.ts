const REAP_BASE_URL = "https://sg.sandbox.api.reap.global";
const REAP_VERSION = "2025-02-14";

export const DUTCH_COLONY_PRODUCT = {
  merchant: "Dutch Colony Coffee Co.",
  name: "Coffee: Brew On-The-Go",
  productId: "prd_62b0d4ff24034b59bc9b9aba5d01650b",
  variantId: "var_369289e65536460cab88fabdd3a5360e",
};

type ReapError = { error?: { code?: string; message?: string } };

export async function reap<T>(path: string, init: RequestInit = {}): Promise<T> {
  const apiKey = process.env.REAP_API_KEY;
  if (!apiKey) throw new Error("REAP_API_KEY is not configured on the server.");

  const response = await fetch(`${REAP_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Reap-Version": REAP_VERSION,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  const body = (await response.json()) as T & ReapError;
  if (!response.ok) {
    throw new Error(body.error?.message ?? `Reap request failed (${response.status}).`);
  }
  return body;
}

export function configuredOwnerId(): string {
  return process.env.REAP_CUSTOMER_ID ?? "tempo-demo-user";
}

export type Enrollment = {
  id: string;
  status: string;
  createdAt?: string;
  nextAction?: { url?: string } | null;
};

export const getEnrollment = (id: string) =>
  reap<Enrollment>(`/agentic/enrollments/${encodeURIComponent(id)}`);

// The browser can return from the hosted Reap pages on a different origin, so
// the enrollment id may be absent client-side. Resolve it server-side by
// listing the owner's enrollments: prefer the newest ACTIVE card, then the
// most recent enrollment still awaiting the hosted step.
export async function resolveEnrollment(
  explicitId: string | null,
  ownerId: string | null = null,
) {
  if (explicitId) return getEnrollment(explicitId);

  const owner = ownerId || configuredOwnerId();
  const list = await reap<{ items?: Enrollment[] }>(
    `/agentic/enrollments?ownerType=CLIENT_REFERENCE&ownerId=${encodeURIComponent(owner)}&limit=50`,
  );
  const items = (list.items ?? []).sort(
    (a, b) => (a.createdAt ?? "").localeCompare(b.createdAt ?? ""),
  );
  const candidate =
    [...items].reverse().find((e) => e.status === "ACTIVE") ??
    items.findLast((e) => e.status === "REQUIRES_ACTION");
  return candidate ? getEnrollment(candidate.id) : null;
}

export function configuredEmail(): string {
  const email = process.env.REAP_CUSTOMER_EMAIL;
  if (!email) throw new Error("REAP_CUSTOMER_EMAIL is not configured on the server.");
  return email;
}

export function configuredShippingAddress(): Record<string, string> | undefined {
  const raw = process.env.REAP_SHIPPING_ADDRESS_JSON;
  if (!raw) return undefined;
  try {
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    throw new Error("REAP_SHIPPING_ADDRESS_JSON must be valid JSON.");
  }
}

export function jsonError(error: unknown) {
  const message = error instanceof Error ? error.message : "Unexpected server error.";
  return Response.json({ error: message }, { status: 400 });
}
