import { request } from "@/lib/request";

export type EnrollmentResult = {
  id?: string;
  status: string;
  nextAction?: { url?: string } | null;
};

// Resolves the owner's enrollment server-side — the newest ACTIVE card, else
// the most recent enrollment still awaiting the hosted step, else "NONE".
export function fetchEnrollment(ownerId: string) {
  return request<EnrollmentResult>(
    `/api/reap/status?kind=enrollment&ownerId=${encodeURIComponent(ownerId)}`,
  );
}

export function isActiveCard(enrollment: EnrollmentResult): enrollment is EnrollmentResult & { id: string } {
  return Boolean(enrollment.id) && enrollment.status === "ACTIVE";
}
