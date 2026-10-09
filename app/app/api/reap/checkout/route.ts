import { jsonError, reap } from "@/lib/reap";
import { writeStoredState } from "@/lib/state";

export async function POST(request: Request) {
  try {
    const { quoteId, enrollmentId } = (await request.json()) as {
      quoteId?: string;
      enrollmentId?: string;
    };
    if (!quoteId || !enrollmentId) throw new Error("quoteId and enrollmentId are required.");

    const appUrl = process.env.REAP_RETURN_URL ?? request.headers.get("origin");
    if (!appUrl) throw new Error("Set REAP_RETURN_URL to your public HTTPS app URL.");

    const checkout = await reap<{
      id: string;
      status: string;
      nextAction?: { url?: string };
    }>("/agentic/checkouts", {
      method: "POST",
      headers: {
        "Idempotency-Key": crypto.randomUUID(),
        "X-Simulate-Checkout": "COMPLETED",
      },
      body: JSON.stringify({
        quoteId,
        enrollmentId,
        presentation: {
          type: "REDIRECT",
          returnUrl: `${appUrl.replace(/\/$/, "")}/?reap_return=checkout`,
        },
      }),
    });

    if (!checkout.nextAction?.url) throw new Error("Reap did not return a checkout approval URL.");
    await writeStoredState({ checkoutId: checkout.id });
    return Response.json({ checkoutId: checkout.id, url: checkout.nextAction.url });
  } catch (error) {
    return jsonError(error);
  }
}
