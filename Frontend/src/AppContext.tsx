import { createContext, useContext } from "react";
import type { LlmProvider } from "./App";

export interface AppContextValue {
  role: string;
  llmProvider: LlmProvider;
  setLlmProvider: (p: LlmProvider) => void;
  latestExecutionId: string | null;
  setLatestExecutionId: (id: string) => void;
}

export const AppContext = createContext<AppContextValue>({
  role: "viewer",
  llmProvider: "ChatGPT",
  setLlmProvider: () => {},
  latestExecutionId: null,
  setLatestExecutionId: () => {},
});

export const useAppContext = () => useContext(AppContext);
