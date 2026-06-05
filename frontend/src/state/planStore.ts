import { create } from "zustand";
import type {
  Boundary,
  CatalogRoom,
  ProgramCheckResponse,
  RoomRequest,
} from "../lib/model";
import { checkProgram, getCatalog } from "../lib/api";

type Status = "idle" | "loading" | "ready" | "error";

type PlanState = {
  catalog: CatalogRoom[];
  catalogStatus: Status;
  boundary: Boundary;
  rooms: Record<string, number>; // type -> count
  check: ProgramCheckResponse | null;
  checking: boolean;
  lastError: string | null;

  loadCatalog: () => Promise<void>;
  setBoundary: (b: Partial<Boundary>) => void;
  setRoomCount: (type: string, count: number) => void;
  incRoom: (type: string, delta: number, max: number) => void;
  resetRooms: () => void;
  runCheck: () => Promise<void>;
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

export const usePlanStore = create<PlanState>((set, get) => ({
  catalog: [],
  catalogStatus: "idle",
  boundary: initialBoundary,
  rooms: {},
  check: null,
  checking: false,
  lastError: null,

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

  resetRooms: () => set({ rooms: {}, check: null }),

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
}));

export function totalRoomCount(rooms: Record<string, number>): number {
  return Object.values(rooms).reduce((a, b) => a + b, 0);
}

export function buildProgramRequest(boundary: Boundary, rooms: Record<string, number>) {
  return { boundary, rooms: roomsList(rooms) };
}
