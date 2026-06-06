import { create } from "zustand";
import type {
  Boundary,
  CatalogRoom,
  FloorPlan,
  ProgramCheckResponse,
  RoomRequest,
} from "../lib/model";
import {
  type AgentProgram,
  type Diagnostics,
  checkProgram,
  generatePlan,
  getCatalog,
  resizePlan,
} from "../lib/api";

type Status = "idle" | "loading" | "ready" | "error";

export type Stage = "boundary" | "rooms" | "generate" | "plan";

type PlanState = {
  stage: Stage;

  catalog: CatalogRoom[];
  catalogStatus: Status;
  boundary: Boundary;
  rooms: Record<string, number>; // type -> count
  check: ProgramCheckResponse | null;
  checking: boolean;
  lastError: string | null;

  program: AgentProgram | null;
  plan: FloorPlan | null;
  diagnostics: Diagnostics | null;
  generating: boolean;
  generateError: string | null;
  seedCounter: number;

  setStage: (stage: Stage) => void;
  goNext: () => void;
  goBack: () => void;
  startOver: () => void;

  loadCatalog: () => Promise<void>;
  setBoundary: (b: Partial<Boundary>) => void;
  setRoomCount: (type: string, count: number) => void;
  incRoom: (type: string, delta: number, max: number) => void;
  resetRooms: () => void;
  runCheck: () => Promise<void>;
  runGenerate: () => Promise<void>;
  runResize: (roomId: string, newTargetAreaM2: number) => Promise<void>;
};

const initialBoundary: Boundary = {
  width_mm: 12000,
  depth_mm: 10000,
  units_display: "metric",
};

function roomsList(rooms: Record<string, number>): RoomRequest[] {
  return Object.entries(rooms)
    .filter(([, c]) => c > 0)
    .map(([type, count]) => ({ type, count }));
}

const STAGE_ORDER: Stage[] = ["boundary", "rooms", "generate", "plan"];

export const usePlanStore = create<PlanState>((set, get) => ({
  stage: "boundary",

  catalog: [],
  catalogStatus: "idle",
  boundary: initialBoundary,
  rooms: {},
  check: null,
  checking: false,
  lastError: null,

  program: null,
  plan: null,
  diagnostics: null,
  generating: false,
  generateError: null,
  seedCounter: 1,

  setStage: (stage) => set({ stage }),
  goNext: () => {
    const cur = get().stage;
    const idx = STAGE_ORDER.indexOf(cur);
    if (idx < STAGE_ORDER.length - 1) set({ stage: STAGE_ORDER[idx + 1] });
  },
  goBack: () => {
    const cur = get().stage;
    const idx = STAGE_ORDER.indexOf(cur);
    if (idx > 0) set({ stage: STAGE_ORDER[idx - 1] });
  },
  startOver: () =>
    set({
      stage: "boundary",
      rooms: {},
      check: null,
      program: null,
      plan: null,
      diagnostics: null,
      generateError: null,
    }),

  loadCatalog: async () => {
    set({ catalogStatus: "loading" });
    try {
      const r = await getCatalog();
      set({ catalog: r.rooms, catalogStatus: "ready" });
    } catch (e) {
      set({ catalogStatus: "error", lastError: (e as Error).message });
    }
  },

  setBoundary: (patch) => {
    set({ boundary: { ...get().boundary, ...patch } });
  },

  setRoomCount: (type, count) => {
    const rooms = { ...get().rooms };
    if (count <= 0) delete rooms[type];
    else rooms[type] = count;
    set({ rooms });
  },

  incRoom: (type, delta, max) => {
    const current = get().rooms[type] ?? 0;
    const next = Math.max(0, Math.min(max, current + delta));
    get().setRoomCount(type, next);
  },

  resetRooms: () =>
    set({
      rooms: {},
      check: null,
      program: null,
      plan: null,
      diagnostics: null,
      generateError: null,
    }),

  runCheck: async () => {
    set({ checking: true, lastError: null });
    try {
      const list = roomsList(get().rooms);
      if (list.length === 0) {
        set({ check: null, checking: false });
        return;
      }
      const result = await checkProgram(get().boundary, list);
      set({ check: result, checking: false });
    } catch (e) {
      set({ checking: false, lastError: (e as Error).message });
    }
  },

  runGenerate: async () => {
    const list = roomsList(get().rooms);
    if (list.length === 0) return;
    const seed = get().seedCounter;
    set({ generating: true, generateError: null, stage: "generate" });
    try {
      const result = await generatePlan(get().boundary, list, seed);
      set({
        program: result.program,
        plan: result.plan,
        diagnostics: result.diagnostics,
        generating: false,
        seedCounter: seed + 1,
        stage: "plan",
      });
    } catch (e) {
      set({ generating: false, generateError: (e as Error).message, stage: "rooms" });
    }
  },

  runResize: async (roomId, newTargetAreaM2) => {
    const { plan, program } = get();
    if (!plan || !program) return;
    set({ generating: true, generateError: null });
    try {
      const result = await resizePlan(plan, program, roomId, newTargetAreaM2);
      set({ plan: result.plan, diagnostics: result.diagnostics, generating: false });
    } catch (e) {
      set({ generating: false, generateError: (e as Error).message });
    }
  },
}));

export function totalRoomCount(rooms: Record<string, number>): number {
  return Object.values(rooms).reduce((a, b) => a + b, 0);
}

export function buildProgramRequest(boundary: Boundary, rooms: Record<string, number>) {
  return { boundary, rooms: roomsList(rooms) };
}
