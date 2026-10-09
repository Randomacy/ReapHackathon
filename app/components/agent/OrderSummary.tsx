import type { Order } from "@/lib/agent/stubs";
import styles from "./OrderSummary.module.css";

export function OrderSummary({ order }: { order: Order }) {
  return (
    <div className={styles.pill}>
      <span className={styles.merchant}>{order.merchant}</span>
      <span className={styles.dot} aria-hidden="true">
        ·
      </span>
      <span className={styles.item}>{order.item}</span>
      <span className={styles.dot} aria-hidden="true">
        ·
      </span>
      <span className={styles.price}>{order.price}</span>
    </div>
  );
}
