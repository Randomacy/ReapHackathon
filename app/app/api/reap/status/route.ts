import { jsonError, reap, resolveEnrollment } from "@/lib/reap";
import { readStoredState } from "@/lib/state";

export async function GET(request: Request) {
  try {
    const params = new URL(request.url).searchParams;
    const id = params.get("id");
    const kind = params.get("kind");
    if (kind !== "enrollment" && kind !== "checkout") {
      throw new Error("Provide an enrollment or checkout id.");
    }

    if (kind === "enrollment") {
      return Response.json((await resolveEnrollment(id, params.get("ownerId"))) ?? { status: "NONE" });
    }

    const checkoutId = id ?? (await readStoredState()).checkoutId;
    if (!checkoutId) return Response.json({ status: "NONE" });
    return Response.json(await reap(`/agentic/checkouts/${encodeURIComponent(checkoutId)}`));
  } catch (error) {
    return jsonError(error);
  }
}
