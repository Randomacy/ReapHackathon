import { useCallback, useEffect, useRef } from "react";
import { useDebugKeys } from "@/hooks/useDebugKeys";
import type { UseAgentFlow } from "@/hooks/useAgentFlow";
import { triggerNudge } from "@/lib/agent/stubs";

export type DebugStep = "nudge" | "confirming" | "searching" | "payment" | "dismiss";

export interface AgentBridge {
  onDebug: (callback: (step: DebugStep) => void) => () => void;
  setInteractive: (interactive: boolean) => void;
  setVisible: (visible: boolean) => void;
}

declare global {
  interface Window {
    agentBridge?: AgentBridge;
  }
}

// The one place that handles a "nudge" request from any of the three
// current triggers (debug keys, Electron tray menu, Electron global
// shortcuts), all of which route through here so they all call
// triggerNudge() the same way the Muse/focus detector will later.
function applyDebugStep(flow: UseAgentFlow, step: DebugStep) {
  if (step === "nudge") {
    triggerNudge();
    flow.debugGoto("nudge");
    return;
  }
  if (step === "dismiss") {
    flow.dismiss();
    return;
  }
  flow.debugGoto(step);
}

/**
 * Bridges the Electron IPC API (window.agentBridge, from preload.ts) into
 * the flow state machine. In a plain browser (no Electron shell), falls
 * back to in-page debug keys so the UI can still be developed and demoed
 * at http://localhost:3000/overlay.
 */
export function useAgentBridge(flow: UseAgentFlow) {
  const flowRef = useRef(flow);
  useEffect(() => {
    flowRef.current = flow;
  }, [flow]);

  const hasElectronBridge = typeof window !== "undefined" && Boolean(window.agentBridge);

  useEffect(() => {
    const bridge = window.agentBridge;
    if (!bridge) return;
    const unsubscribe = bridge.onDebug((step) => applyDebugStep(flowRef.current, step));
    return unsubscribe;
  }, [hasElectronBridge]);

  useEffect(() => {
    window.agentBridge?.setVisible(flow.step !== "idle");
  }, [flow.step, hasElectronBridge]);

  const debugActive = useDebugKeys(
    {
      nudge: () => applyDebugStep(flowRef.current, "nudge"),
      confirming: () => applyDebugStep(flowRef.current, "confirming"),
      searching: () => applyDebugStep(flowRef.current, "searching"),
      payment: () => applyDebugStep(flowRef.current, "payment"),
      dismiss: () => applyDebugStep(flowRef.current, "dismiss"),
    },
    !hasElectronBridge,
  );

  const setInteractive = useCallback((interactive: boolean) => {
    window.agentBridge?.setInteractive(interactive);
  }, []);

  return {
    setInteractive,
    showDebugHint: debugActive,
  };
}
