export type Order = {
  merchant: string;
  item: string;
  price: string;
};

const FIND_OPTIONS_DELAY_MS = 2500;

/**
 * TODO(reap/qual): replace this with a real merchant catalog search + quote,
 * e.g. Reap's agentic product search against the Dutch Colony merchant,
 * followed by a Qual-side quote/confirmation step. The data below is a
 * placeholder so the overlay flow can be built and demoed end to end.
 */
export function findOptions(): Promise<Order> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        merchant: "Dutch Colony",
        item: "Iced latte",
        price: "S$6.50",
      });
    }, FIND_OPTIONS_DELAY_MS);
  });
}

/**
 * TODO(reap/qual): wire this to open Reap's hosted approval page or the
 * Qual confirm flow for `order`, then resolve once the user completes (or
 * cancels) checkout there. For now it only logs the order.
 */
export function startCheckout(order: Order): Promise<void> {
  console.info("TODO: open Reap hosted approval / Qual confirm flow for order", order);
  return Promise.resolve();
}

/**
 * The single entry point the Muse/focus detector will call later to start
 * the nudge flow. For now only debug keys, the tray menu, and the global
 * shortcuts call this (indirectly, by dispatching the same "nudge" step).
 *
 * TODO(muse): call this from the focus-dip detector once it's wired up.
 */
export function triggerNudge(): void {
  console.info("TODO: triggered by Muse 2 focus-dip detector");
}
