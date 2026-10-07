export const MODES = ["never", "always", "adaptive"] as const;
export type Mode = (typeof MODES)[number];
export type Split = "test" | "tune" | "all";
export type Verdict = "correct (both)" | "lenient only" | "abstained" | "wrong";

export interface Run {
  mode: Mode;
  split: Split;
  n: number;
  accuracy: number;
  strict_accuracy: number;
  hallucination_rate: number;
  abstain_rate: number;
  retrieval_rate: number;
  avg_latency_ms: number;
}

export interface Summary {
  model: string;
  pop_threshold: number;
  conf_threshold: number;
  runs: Run[];
}

export interface GridPoint {
  pop_threshold: number;
  conf_threshold: number;
  accuracy: number;
  strict_accuracy: number;
  retrieval_rate: number;
}

export interface Frontier {
  grid: GridPoint[];
  pareto: GridPoint[];
  modes: { mode: Mode; accuracy: number; retrieval_rate: number }[];
}

export type PopularityBucket = { bucket: number; min: number; max: number; n: number } & Record<Mode, number>;

export interface ModeAnswer {
  answer: string;
  confidence: number;
  correct: boolean;
  correct_strict: boolean;
  hallucinated: boolean;
  retrieved: boolean;
  verdict: Verdict;
}

export type Question = {
  question_id: number;
  question: string;
  prop: string;
  s_pop: number;
  answers: string[];
  split: "tune" | "test";
} & Record<Mode, ModeAnswer>;
