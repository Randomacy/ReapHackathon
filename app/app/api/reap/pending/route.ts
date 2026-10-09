import { DUTCH_COLONY_PRODUCT, jsonError, reap } from "@/lib/reap";
import { readStoredState, writeStoredState } from "@/lib/state";

// Poll target for "is there an order waiting for the user's signature?". A
// pending order is the latest checkout still in REQUIRES_ACTION; signing moves
// it along and the next poll reports its live status. DELETE dismisses the
// current pending order locally — Reap checkouts cannot be cancelled server
// side and simply expire.
export async function GET() {
  try {
    const { checkoutId, dismissedCheckoutId } = await readStoredState();
    if (!checkoutId || checkoutId === dismissedCheckoutId) {
      return Response.json({ pending: false });
    }

    const checkout = await reap<{
      id: string;
      status: string;
      orderId?: string;
      amount?: { amount: number; currency: string };
      finalAmount?: { amount: number; currency: string };
      nextAction?: { url?: string } | null;
    }>(`/agentic/checkouts/${encodeURIComponent(checkoutId)}`);

    const approvalUrl = checkout.nextAction?.url ?? null;
    return Response.json({
      pending: checkout.status === "REQUIRES_ACTION" && !!approvalUrl,
      checkoutId: checkout.id,
      status: checkout.status,
      orderId: checkout.orderId ?? null,
      approvalUrl,
      amount: checkout.finalAmount ?? checkout.amount ?? null,
      product: DUTCH_COLONY_PRODUCT,
    });
  } catch (error) {
    return jsonError(error);
  }
}

export async function DELETE() {
  try {
    const { checkoutId } = await readStoredState();
    if (checkoutId) await writeStoredState({ dismissedCheckoutId: checkoutId });
    return Response.json({ cancelled: true });
  } catch (error) {
    return jsonError(error);
  }
}
