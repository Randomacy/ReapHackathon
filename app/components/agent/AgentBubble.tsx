"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import styles from "./AgentBubble.module.css";

export function AgentBubble({
  contentKey,
  children,
  onMouseEnter,
  onMouseLeave,
}: {
  contentKey: string;
  children: ReactNode;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <div className={styles.bubbleWrap}>
      <div className={styles.tail} />
      <motion.div
        layout
        className={styles.bubble}
        role="status"
        aria-live="polite"
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        transition={reduceMotion ? { duration: 0.001 } : undefined}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={contentKey}
            className={styles.bubbleContent}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
