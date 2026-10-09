"use client";

import { useEffect } from "react";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "framer-motion";
import { useAgentFlow, type AgentStep } from "@/hooks/useAgentFlow";
import { useAgentBridge } from "@/hooks/useAgentBridge";
import { USER_NAME } from "@/lib/agent/config";
import { AgentFace, type AgentFaceState } from "@/components/agent/AgentFace";
import { AgentBubble } from "@/components/agent/AgentBubble";
import { OrderSummary } from "@/components/agent/OrderSummary";
import styles from "./AgentOverlay.module.css";

const FACE_BY_STEP: Partial<Record<AgentStep, AgentFaceState>> = {
  nudge: "concerned",
  confirming: "confirm",
  payment: "sorry",
};

function LoadingDots() {
  const reduceMotion = useReducedMotion();
  return (
    <div className={styles.loadingDots} aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className={styles.dot}
          animate={reduceMotion ? { opacity: [0.3, 1, 0.3] } : { opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: index * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

export function AgentOverlay() {
  const flow = useAgentFlow();
  const { setInteractive, showDebugHint } = useAgentBridge(flow);
  const reduceMotion = useReducedMotion();

  // The /overlay route renders inside a transparent Electron window, so the
  // page itself must have no opaque background (the global stylesheet sets
  // one for the rest of the app).
  useEffect(() => {
    const html = document.documentElement;
    const { body } = document;
    const previousHtmlBg = html.style.background;
    const previousBodyBg = body.style.background;
    html.style.background = "transparent";
    body.style.background = "transparent";
    return () => {
      html.style.background = previousHtmlBg;
      body.style.background = previousBodyBg;
    };
  }, []);

  const isPresent = flow.step !== "idle" && flow.step !== "dismissed";
  const showFace = flow.step === "nudge" || flow.step === "confirming" || flow.step === "payment";
  const faceState = FACE_BY_STEP[flow.step];

  const companionVariants: Variants = reduceMotion
    ? {
        initial: { opacity: 0 },
        animate: { opacity: 1, transition: { duration: 0.32 } },
        exit: { opacity: 0, transition: { duration: 0.22 } },
      }
    : {
        initial: { opacity: 0, scale: 0.9, y: -12 },
        animate: {
          opacity: 1,
          scale: 1,
          y: 0,
          transition: { duration: 0.32, ease: [0.16, 1, 0.3, 1] },
        },
        exit: {
          opacity: 0,
          scale: 0.95,
          transition: { duration: 0.22, ease: "easeIn" },
        },
      };

  return (
    <div className={styles.overlayRoot}>
      <AnimatePresence onExitComplete={flow.exitComplete}>
        {isPresent && (
          <motion.div
            key="companion"
            className={styles.companion}
            initial="initial"
            animate="animate"
            exit="exit"
            variants={companionVariants}
          >
            <AnimatePresence mode="popLayout" initial={false}>
              {showFace && faceState && (
                <motion.div
                  key="face"
                  layout
                  className={styles.faceSlot}
                  initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85, y: -8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.85, y: -8 }}
                  transition={
                    reduceMotion
                      ? { duration: 0.15 }
                      : { type: "spring", stiffness: 320, damping: 26 }
                  }
                >
                  <AgentFace state={faceState} />
                </motion.div>
              )}
            </AnimatePresence>

            <motion.div
              layout
              className={styles.bubbleSlot}
              initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12, duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            >
              <AgentBubble
                contentKey={flow.step}
                onMouseEnter={() => setInteractive(true)}
                onMouseLeave={() => setInteractive(false)}
              >
                {flow.step === "nudge" && (
                  <>
                    <p className={styles.bubbleText}>You seem tired, want a coffee?</p>
                    <div className={styles.buttonRow}>
                      <button type="button" className={styles.secondaryButton} onClick={flow.decline}>
                        Nah I&apos;m good
                      </button>
                      <button type="button" className={styles.primaryButton} onClick={flow.accept}>
                        Sure
                      </button>
                    </div>
                  </>
                )}

                {flow.step === "confirming" && (
                  <p className={styles.bubbleText}>{`OK I got you, ${USER_NAME}!`}</p>
                )}

                {flow.step === "searching" && (
                  <>
                    <p className={styles.bubbleText}>Finding you the best options…</p>
                    <LoadingDots />
                  </>
                )}

                {flow.step === "payment" && (
                  <>
                    <p className={styles.bubbleText}>
                      Hey, sorry to bug you but I&apos;ve got your order ready!
                    </p>
                    {flow.order && <OrderSummary order={flow.order} />}
                    <div className={styles.buttonRow}>
                      <button type="button" className={styles.primaryButton} onClick={flow.pay}>
                        Pay Here
                      </button>
                    </div>
                  </>
                )}
              </AgentBubble>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {showDebugHint && (
        <div className={styles.debugHint}>
          Debug: 1 nudge · 2 confirm · 3 searching · 4 payment · Esc dismiss
        </div>
      )}
    </div>
  );
}
