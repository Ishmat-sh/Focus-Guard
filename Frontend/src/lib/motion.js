import { useReducedMotion } from "motion/react";

export const breathingPulse = {
  animate: { scale: [1, 1.04, 1] },
  transition: { duration: 3.5, repeat: Infinity, ease: "easeInOut" },
};

export const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.22, ease: "easeOut" },
};

export function useMotionPreferences() {
  const reducedMotion = useReducedMotion();
  return {
    reducedMotion,
    breathing: reducedMotion ? {} : breathingPulse,
    page: reducedMotion
      ? {
          initial: false,
          animate: { opacity: 1 },
          exit: { opacity: 1 },
          transition: { duration: 0 },
        }
      : pageTransition,
  };
}
