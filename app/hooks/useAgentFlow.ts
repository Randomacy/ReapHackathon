import { useCallback, useEffect, useReducer } from "react";
import { findOptions, startCheckout, type Order } from "@/lib/agent/stubs";

export type AgentStep =
  | "idle"
  | "nudge"
  | "confirming"
  | "searching"
  | "payment"
  | "dismissed";

type FlowState = {
  step: AgentStep;
  order: Order | null;
};

type FlowAction = { type: "GOTO"; step: AgentStep } | { type: "SET_ORDER"; order: Order };

const CONFIRMING_DURATION_MS = 1800;
const SEARCHING_MIN_DURATION_MS = 1500;

function reducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "GOTO":
      return {
        step: action.step,
        order: action.step === "idle" || action.step === "nudge" ? null : state.order,
      };
    case "SET_ORDER":
      return { ...state, order: action.order };
    default:
      return state;
  }
}

const initialState: FlowState = { step: "idle", order: null };

export function useAgentFlow() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const goto = useCallback((step: AgentStep) => dispatch({ type: "GOTO", step }), []);

  // nudge -> confirming
  const accept = useCallback(() => goto("confirming"), [goto]);
  // nudge -> dismissed ("Nah I'm good")
  const decline = useCallback(() => goto("dismissed"), [goto]);
  // any state -> dismissed (Esc, Ctrl+Alt+0, etc.)
  const dismiss = useCallback(() => goto("dismissed"), [goto]);
  // dismissed -> idle, called once the exit animation finishes
  const exitComplete = useCallback(() => goto("idle"), [goto]);
  // debug/tray/shortcut jumps land directly on a step
  const debugGoto = useCallback((step: AgentStep) => goto(step), [goto]);

  // payment -> dismissed, after the checkout stub runs
  const pay = useCallback(() => {
    if (!state.order) return;
    void startCheckout(state.order).then(() => goto("dismissed"));
  }, [goto, state.order]);

  // confirming auto-advances to searching after a fixed delay
  useEffect(() => {
    if (state.step !== "confirming") return;
    const timer = setTimeout(() => goto("searching"), CONFIRMING_DURATION_MS);
    return () => clearTimeout(timer);
  }, [state.step, goto]);

  // searching calls the findOptions stub, with a minimum time on screen
  useEffect(() => {
    if (state.step !== "searching") return;
    let cancelled = false;
    let settleTimer: ReturnType<typeof setTimeout> | null = null;
    const startedAt = Date.now();

    findOptions().then((order) => {
      if (cancelled) return;
      const elapsed = Date.now() - startedAt;
      const remaining = Math.max(0, SEARCHING_MIN_DURATION_MS - elapsed);
      settleTimer = setTimeout(() => {
        if (cancelled) return;
        dispatch({ type: "SET_ORDER", order });
        goto("payment");
      }, remaining);
    });

    return () => {
      cancelled = true;
      if (settleTimer) clearTimeout(settleTimer);
    };
  }, [state.step, goto]);

  // debug jump straight to "payment" (skipping searching) still needs an order
  useEffect(() => {
    if (state.step !== "payment" || state.order) return;
    let cancelled = false;
    findOptions().then((order) => {
      if (!cancelled) dispatch({ type: "SET_ORDER", order });
    });
    return () => {
      cancelled = true;
    };
  }, [state.step, state.order]);

  return {
    step: state.step,
    order: state.order,
    accept,
    decline,
    dismiss,
    pay,
    exitComplete,
    debugGoto,
  };
}

export type UseAgentFlow = ReturnType<typeof useAgentFlow>;
