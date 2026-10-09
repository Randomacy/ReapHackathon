export const DEFAULT_CUSTOMER_ID = "tempo-demo-user";
export const DEFAULT_CUSTOMER_EMAIL = "demo@example.com";

export type Identity = { customerId: string; email: string };

const defaults: Identity = {
  customerId: DEFAULT_CUSTOMER_ID,
  email: DEFAULT_CUSTOMER_EMAIL,
};

export function loadIdentity(): Identity {
  if (typeof window === "undefined") return defaults;
  return {
    customerId: localStorage.getItem("tempo-customer-id") || DEFAULT_CUSTOMER_ID,
    email: localStorage.getItem("tempo-customer-email") || DEFAULT_CUSTOMER_EMAIL,
  };
}

export function saveIdentity(identity: Identity) {
  localStorage.setItem("tempo-customer-id", identity.customerId);
  localStorage.setItem("tempo-customer-email", identity.email);
}
