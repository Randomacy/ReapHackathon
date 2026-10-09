"use client";

import type { CSSProperties } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import styles from "./AgentFace.module.css";

export type AgentFaceState = "concerned" | "confirm" | "sorry";

type SpriteDef = {
  sheet: string;
  frames: number;
  msPerFrame: number;
  loop: boolean;
  label: string;
};

// Reap agent sprite pack (public/agent-sprites), values from its manifest.json.
// 256px frames laid out in a horizontal strip per sheet.
const SPRITE_BY_STATE: Record<AgentFaceState, SpriteDef> = {
  concerned: {
    sheet: "/agent-sprites/sprite_nudge_transparent.png",
    frames: 8,
    msPerFrame: 100,
    loop: true,
    label: "Companion looking concerned",
  },
  confirm: {
    sheet: "/agent-sprites/sprite_confirming_transparent.png",
    frames: 6,
    msPerFrame: 100,
    loop: false,
    label: "Companion confirming with a checkmark",
  },
  sorry: {
    sheet: "/agent-sprites/sprite_payment_transparent.png",
    frames: 8,
    msPerFrame: 100,
    loop: true,
    label: "Companion looking apologetic",
  },
};

const DISPLAY_SIZE = 96;

export function AgentFace({ state }: { state: AgentFaceState }) {
  const reduceMotion = useReducedMotion();
  const sprite = SPRITE_BY_STATE[state];
  const lastFrameOffset = -(DISPLAY_SIZE * (sprite.frames - 1));

  const stripStyle: CSSProperties = {
    width: DISPLAY_SIZE * sprite.frames,
    height: DISPLAY_SIZE,
    backgroundImage: `url(${sprite.sheet})`,
    ...(reduceMotion
      ? { transform: `translateX(${lastFrameOffset}px)` }
      : {
          animationDuration: `${sprite.frames * sprite.msPerFrame}ms`,
          animationTimingFunction: `steps(${sprite.frames - 1}, jump-end)`,
          animationIterationCount: sprite.loop ? "infinite" : 1,
          animationFillMode: sprite.loop ? "none" : "forwards",
          // Read by the spritePlay keyframes below.
          ["--sprite-end-x" as string]: `${lastFrameOffset}px`,
        }),
  };

  return (
    <div className={styles.face}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={state}
          className={styles.viewport}
          style={{ width: DISPLAY_SIZE, height: DISPLAY_SIZE }}
          role="img"
          aria-label={sprite.label}
          initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
          transition={
            reduceMotion
              ? { duration: 0.15 }
              : { type: "spring", stiffness: 420, damping: 22 }
          }
        >
          <div
            className={reduceMotion ? styles.stripStill : styles.strip}
            style={stripStyle}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
