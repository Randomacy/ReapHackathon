"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import styles from "./AgentFace.module.css";

// Emoji placeholders for now; swap for a CSS sprite sheet later without
// touching AgentOverlay, since only this file knows how a face is drawn.
export type AgentFaceState = "concerned" | "confirm" | "sorry";

const FACE_EMOJI: Record<AgentFaceState, string> = {
  concerned: "🥺",
  confirm: "👌",
  sorry: "🙆",
};

const FACE_LABEL: Record<AgentFaceState, string> = {
  concerned: "Companion looking concerned",
  confirm: "Companion giving a thumbs up",
  sorry: "Companion apologizing",
};

export function AgentFace({ state }: { state: AgentFaceState }) {
  const reduceMotion = useReducedMotion();

  return (
    <div className={styles.face}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={state}
          className={styles.emoji}
          role="img"
          aria-label={FACE_LABEL[state]}
          initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
          transition={
            reduceMotion
              ? { duration: 0.15 }
              : { type: "spring", stiffness: 420, damping: 22 }
          }
        >
          {FACE_EMOJI[state]}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
