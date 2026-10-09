"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_CUSTOMER_EMAIL,
  DEFAULT_CUSTOMER_ID,
  loadIdentity,
  saveIdentity,
} from "@/lib/identity";
import { fetchEnrollment, type EnrollmentResult } from "@/lib/enrollment";
import { request } from "@/lib/request";

type CardState = "loading" | "none" | "pending" | "active";

export default function Onboarding() {
  const [cardState, setCardState] = useState<CardState>("loading");
  const [resumeUrl, setResumeUrl] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState(DEFAULT_CUSTOMER_ID);
  const [email, setEmail] = useState(DEFAULT_CUSTOMER_EMAIL);
  const [message, setMessage] = useState("Checking your card setup…");
  const [busy, setBusy] = useState(false);
  const didSync = useRef(false);
  const router = useRouter();

  const applyEnrollment = useCallback((enrollment: EnrollmentResult) => {
    if (!enrollment.id) {
      localStorage.removeItem("tempo-enrollment-id");
      setCardState("none");
      setMessage("Add a sandbox card to begin.");
    } else if (enrollment.status === "ACTIVE") {
      localStorage.setItem("tempo-enrollment-id", enrollment.id);
      setCardState("active");
      setMessage("Your sandbox card is ready.");
    } else if (enrollment.status === "REQUIRES_ACTION" && enrollment.nextAction?.url) {
      localStorage.setItem("tempo-enrollment-id", enrollment.id);
      setCardState("pending");
      setResumeUrl(enrollment.nextAction.url);
      setMessage("REAP still needs you to finish card setup.");
    } else {
      localStorage.removeItem("tempo-enrollment-id");
      setCardState("none");
      setMessage(`Card setup ${enrollment.status.toLowerCase()}. Add your sandbox card again.`);
    }
  }, []);

  const syncEnrollment = useCallback((ownerId: string) => {
    fetchEnrollment(ownerId)
      .then(applyEnrollment)
      .catch((error: unknown) => {
        setCardState("none");
        setMessage(error instanceof Error ? error.message : "Could not confirm card setup.");
      });
  }, [applyEnrollment]);

  useEffect(() => {
    // Guard against the StrictMode double-mount; the first run strips the
    // return query param.
    if (didSync.current) return;
    didSync.current = true;

    // The hosted Reap card-entry page returns the browser to
    // REAP_RETURN_URL/onboarding, which can be a different origin than where
    // the flow started, so localStorage may be empty here. The status route
    // resolves the owner's enrollment server-side.
    const identity = loadIdentity();
    queueMicrotask(() => {
      setCustomerId(identity.customerId);
      setEmail(identity.email);
    });
    const returned = new URLSearchParams(window.location.search).get("reap_return");
    syncEnrollment(identity.customerId);
    if (returned) window.history.replaceState({}, "", "/onboarding");
  }, [syncEnrollment]);

  function saveSettings() {
    if (!customerId.trim() || !email.trim()) {
      setMessage("Both fields are required.");
      return;
    }
    saveIdentity({ customerId: customerId.trim(), email: email.trim() });
    localStorage.removeItem("tempo-enrollment-id");
    setCardState("loading");
    setMessage("Checking your card setup…");
    syncEnrollment(customerId.trim());
  }

  async function enrollCard() {
    setBusy(true);
    try {
      const enrollment = await request<{ enrollmentId: string; url: string }>("/api/reap/enrollment", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customerId: customerId.trim(), email: email.trim() }) });
      localStorage.setItem("tempo-enrollment-id", enrollment.enrollmentId);
      window.location.assign(enrollment.url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not start card setup.");
      setBusy(false);
    }
  }

  return <main>
    <section className="hero">
      <p className="eyebrow">TEMPO · REAP SANDBOX</p>
      <h1>Set up your card.</h1>
      <p className="intro">Add a sandbox card once. Tempo can then order on your behalf within the limits you set.</p>
    </section>
    <section className="order-card" aria-live="polite">
      <label className="field">
        <span className="field-label">Customer ID</span>
        <input value={customerId} onChange={(e) => setCustomerId(e.target.value)} placeholder={DEFAULT_CUSTOMER_ID} />
      </label>
      <label className="field">
        <span className="field-label">Customer email</span>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={DEFAULT_CUSTOMER_EMAIL} />
      </label>
      <button onClick={saveSettings} disabled={busy}>Save settings</button>
      {cardState === "loading" ? null
        : cardState === "active" ? <button onClick={() => router.push("/")}>Continue to your order</button>
        : cardState === "pending" && resumeUrl ? <button onClick={() => window.location.assign(resumeUrl)} disabled={busy}>Finish card setup on REAP</button>
        : <button onClick={enrollCard} disabled={busy}>Add my sandbox card</button>}
      <p className="status">{busy ? "Working…" : message}</p>
      <p className="subtle">Changing the customer ID switches to a different enrollment set — each customer owns its own cards.</p>
    </section>
    <p className="footnote">Card entry happens on a REAP-hosted page. This app never receives card details.</p>
  </main>;
}
