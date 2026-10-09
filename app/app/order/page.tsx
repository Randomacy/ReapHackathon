"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { fetchEnrollment, isActiveCard } from "@/lib/enrollment";
import { loadIdentity } from "@/lib/identity";
import { request } from "@/lib/request";

type OrderResponse = {
  checkout: { id: string; status: string; approvalUrl: string | null };
};

export default function Order() {
  const [failed, setFailed] = useState(false);
  const router = useRouter();
  const didStart = useRef(false);

  useEffect(() => {
    // StrictMode mounts effects twice; without this guard the second run would
    // place a duplicate order.
    if (didStart.current) return;
    didStart.current = true;

    (async () => {
      try {
        const identity = loadIdentity();
        const enrollment = await fetchEnrollment(identity.customerId);
        if (!isActiveCard(enrollment)) {
          router.replace("/onboarding");
          return;
        }
        const result = await request<OrderResponse>("/api/reap/order", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            customerId: identity.customerId,
            email: identity.email,
            returnUrl: `${window.location.origin}/pending`,
          }),
        });
        if (result.checkout.approvalUrl) {
          // Signing on the hosted REAP page returns the browser to /pending.
          window.location.assign(result.checkout.approvalUrl);
        } else {
          router.push("/pending");
        }
      } catch {
        setFailed(true);
      }
    })();
  }, [router]);

  return <main className="plain">
    {failed ? <button className="ghost" onClick={() => router.push("/onboarding")}>Set up my card</button> : <div className="spinner" role="status" aria-label="Ordering" />}
  </main>;
}
