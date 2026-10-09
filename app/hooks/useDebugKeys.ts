import { useEffect, useRef, useState } from "react";

export type DebugKeyHandlers = {
  nudge: () => void;
  confirming: () => void;
  searching: () => void;
  payment: () => void;
  dismiss: () => void;
};

function isDebugEnabled(): boolean {
  if (process.env.NODE_ENV === "development") return true;
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("debug") === "1";
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
}

/**
 * In-page fallback for the Electron global shortcuts, used when the app runs
 * in a plain browser (no window.agentBridge). Active only in development or
 * with ?debug=1, so it never leaks into a production web build.
 */
export function useDebugKeys(handlers: DebugKeyHandlers, enabled = true): boolean {
  const [debugEnabled] = useState(isDebugEnabled);
  const active = enabled && debugEnabled;
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!active) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat || isTypingTarget(event.target)) return;
      switch (event.key) {
        case "1":
          handlersRef.current.nudge();
          break;
        case "2":
          handlersRef.current.confirming();
          break;
        case "3":
          handlersRef.current.searching();
          break;
        case "4":
          handlersRef.current.payment();
          break;
        case "Escape":
          handlersRef.current.dismiss();
          break;
        default:
          break;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active]);

  return active;
}
