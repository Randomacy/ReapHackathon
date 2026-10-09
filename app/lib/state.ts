// The hosted Reap pages send the browser back to REAP_RETURN_URL, which may be
// a different origin than the one the flow started on, so client-side storage
// cannot be trusted to carry Reap resource IDs across the redirect. Keep the
// latest IDs in server memory instead — a pending order only needs to survive
// until it is signed, and a restart just drops it.
type StoredState = {
  enrollmentId?: string;
  checkoutId?: string;
  dismissedCheckoutId?: string;
};

const state: StoredState = {};

export async function readStoredState(): Promise<StoredState> {
  return { ...state };
}

export async function writeStoredState(patch: Partial<StoredState>): Promise<void> {
  Object.assign(state, patch);
}
