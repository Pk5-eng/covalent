// TS mirror of backend/app/models.py. Keep both in sync.

export type Units = "metric" | "imperial";
export type Zone = "public" | "private" | "service" | "circulation" | "exterior";

export type Boundary = {
  width_mm: number;
  depth_mm: number;
  units_display: Units;
};

export type RoomRequest = {
  type: string;
  count: number;
};

export type CatalogRoom = {
  type: string;
  label: string;
  zone: Zone;
  target_m2: number;
  min_m2: number;
  min_width_m: number;
  needs_window: boolean;
  needs_egress: boolean;
  needs_exterior_wall: boolean;
  max_count: number;
};

export type ProgramSummary = {
  boundary_area_m2: number;
  usable_area_m2: number;
  min_required_m2: number;
  target_total_m2: number;
  rooms_expanded: {
    id: string;
    type: string;
    label: string;
    zone: Zone;
    target_area_m2: number;
    min_area_m2: number;
    min_width_m: number;
    needs_window: boolean;
    needs_egress: boolean;
    needs_exterior_wall: boolean;
  }[];
};

export type ProgramCheckResponse = {
  ok: boolean;
  warnings: string[];
  errors: string[];
  summary: ProgramSummary;
};

// Geometry-side types appear in Step 3+.
export type Point = { x: number; y: number };

export type Room = {
  id: string;
  type: string;
  label: string;
  zone: Zone;
  polygon: [number, number][];
  area_mm2: number;
  needs_window: boolean;
  needs_egress: boolean;
  needs_exterior_wall: boolean;
};

export type Wall = {
  id: string;
  a: [number, number];
  b: [number, number];
  thickness_mm: number;
  type: "interior" | "exterior";
};

export type Opening = {
  id: string;
  kind: "door" | "window";
  wall_id: string;
  position: number;
  width_mm: number;
  swing?: string | null;
  is_egress: boolean;
};

export type FloorPlan = {
  boundary: Boundary;
  rooms: Room[];
  walls: Wall[];
  openings: Opening[];
  meta: { scale: string; north_deg: number; title: string };
};
