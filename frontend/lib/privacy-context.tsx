"use client";

import { createContext, useContext, useState } from "react";

interface PrivacyModeValue {
  hidden: boolean;
  toggle: () => void;
}

const PrivacyModeContext = createContext<PrivacyModeValue | null>(null);

// Session-only by design (resets on reload) -- the user asked for a toggle, not a persisted
// setting, and defaulting to "hidden" would risk masking amounts the user actually wants to
// see right after logging in.
export function PrivacyModeProvider({ children }: { children: React.ReactNode }) {
  const [hidden, setHidden] = useState(false);
  return (
    <PrivacyModeContext.Provider value={{ hidden, toggle: () => setHidden((h) => !h) }}>
      {children}
    </PrivacyModeContext.Provider>
  );
}

export function usePrivacyMode(): PrivacyModeValue {
  const ctx = useContext(PrivacyModeContext);
  if (!ctx) {
    throw new Error("usePrivacyMode must be used within a PrivacyModeProvider");
  }
  return ctx;
}
