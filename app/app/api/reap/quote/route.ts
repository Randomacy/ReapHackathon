import {
  configuredEmail,
  configuredShippingAddress,
  DUTCH_COLONY_PRODUCT,
  jsonError,
  reap,
} from "@/lib/reap";

export async function POST(request: Request) {
  try {
    const { email } = (await request.json().catch(() => ({}))) as { email?: string };
    const shippingAddress = configuredShippingAddress();
    const quote = await reap<{
      id: string;
      amountBreakdown: { finalAmount: { amount: number; currency: string } };
      expiresAt: string;
      shippingOptions?: Array<{ id: string; name: string; selected: boolean }>;
    }>("/agentic/quotes", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        items: [{ variantId: DUTCH_COLONY_PRODUCT.variantId, quantity: 1 }],
        email: email?.trim() || configuredEmail(),
        ...(shippingAddress ? { shippingAddress } : {}),
      }),
    });

    return Response.json({ product: DUTCH_COLONY_PRODUCT, quote });
  } catch (error) {
    return jsonError(error);
  }
}
