import { configuredEmail, configuredOwnerId, jsonError, reap } from "@/lib/reap";
import { writeStoredState } from "@/lib/state";

export async function POST(request: Request) {
  try {
    const appUrl = process.env.REAP_RETURN_URL ?? request.headers.get("origin");
    if (!appUrl) throw new Error("Set REAP_RETURN_URL to your public HTTPS app URL.");

    const { customerId, email } = (await request.json().catch(() => ({}))) as {
      customerId?: string;
      email?: string;
    };

    const enrollmentPayload = {
      source: "EXTERNAL",
      owner: {
        type: "CLIENT_REFERENCE",
        id: customerId?.trim() || configuredOwnerId(),
        email: email?.trim() || configuredEmail(),
      },
      presentation: {
        type: "REDIRECT",
        returnUrl: `${appUrl.replace(/\/$/, "")}/onboarding?reap_return=enrollment`,
      },
    };

    const enrollment = await reap<{
      id: string;
      status: string;
      nextAction?: { url?: string };
    }>("/agentic/enrollments", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(enrollmentPayload),
    });

    if (!enrollment.nextAction?.url) throw new Error("Reap did not return an enrollment action URL.");
    await writeStoredState({ enrollmentId: enrollment.id });
    return Response.json({ enrollmentId: enrollment.id, url: enrollment.nextAction.url });
  } catch (error) {
    return jsonError(error);
  }
}
