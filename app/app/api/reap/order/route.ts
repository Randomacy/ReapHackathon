import {
  configuredEmail,
  configuredShippingAddress,
  DUTCH_COLONY_PRODUCT,
  getEnrollment,
  jsonError,
  reap,
  resolveEnrollment,
} from "@/lib/reap";
import { writeStoredState } from "@/lib/state";

// Server-callable one-shot order: a backend POSTs to this endpoint (optionally
// with { customerId, email, enrollmentId, returnUrl }) and it resolves the
// ACTIVE enrollment, prices the fixed product with a live quote, and opens the
// checkout. With REAP_ENROLLMENT_ID / REAP_CUSTOMER_ID / REAP_CUSTOMER_EMAIL set
// in the environment, a bare `curl -X POST` with no body works. The response's
// checkout.approvalUrl is handed to the user — signing that page is the only
// user interaction. When Reap returns no nextAction, the charge already ran.
export async function POST(request: Request) {
  try {
    const { customerId, email, returnUrl, enrollmentId } = (await request
      .json()
      .catch(() => ({}))) as {
      customerId?: string;
      email?: string;
      returnUrl?: string;
      enrollmentId?: string;
    };

    const pinnedId = enrollmentId?.trim() || process.env.REAP_ENROLLMENT_ID;
    const enrollment = pinnedId
      ? await getEnrollment(pinnedId)
      : await resolveEnrollment(null, customerId?.trim() || null);
    if (!enrollment) {
      throw new Error("No sandbox card on file for this customer. Add one on the onboarding page first.");
    }
    if (enrollment.status !== "ACTIVE") {
      throw new Error(
        enrollment.status === "REQUIRES_ACTION" && enrollment.nextAction?.url
          ? `Card setup is unfinished. Continue on REAP: ${enrollment.nextAction.url}`
          : `Card setup is not complete: ${enrollment.status}.`,
      );
    }

    const shippingAddress = configuredShippingAddress();
    const quote = await reap<{
      id: string;
      amountBreakdown: { finalAmount: { amount: number; currency: string } };
      expiresAt: string;
    }>("/agentic/quotes", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        items: [{ variantId: DUTCH_COLONY_PRODUCT.variantId, quantity: 1 }],
        email: email?.trim() || configuredEmail(),
        ...(shippingAddress ? { shippingAddress } : {}),
      }),
    });

    const appUrl = process.env.REAP_RETURN_URL ?? request.headers.get("origin");
    if (!appUrl) throw new Error("Set REAP_RETURN_URL to your public HTTPS app URL.");

    const checkout = await reap<{
      id: string;
      status: string;
      orderId?: string;
      finalAmount?: { amount: number; currency: string };
      nextAction?: { url?: string } | null;
    }>("/agentic/checkouts", {
      method: "POST",
      headers: {
        "Idempotency-Key": crypto.randomUUID(),
        "X-Simulate-Checkout": "COMPLETED",
      },
      body: JSON.stringify({
        quoteId: quote.id,
        enrollmentId: enrollment.id,
        presentation: {
          type: "REDIRECT",
          returnUrl:
            returnUrl?.trim() || `${appUrl.replace(/\/$/, "")}/pending`,
        },
      }),
    });

    await writeStoredState({ checkoutId: checkout.id });
    return Response.json({
      product: DUTCH_COLONY_PRODUCT,
      enrollmentId: enrollment.id,
      quote,
      checkout: {
        id: checkout.id,
        status: checkout.status,
        orderId: checkout.orderId ?? null,
        finalAmount: checkout.finalAmount ?? null,
        approvalUrl: checkout.nextAction?.url ?? null,
      },
    });
  } catch (error) {
    return jsonError(error);
  }
}
