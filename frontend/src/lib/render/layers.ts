// NCS / AIA layer name mapping. Locked at the project level so the SVG
// renderer and DXF exporter agree.

export const LAYER = {
  EXTERIOR_WALL: "A-WALL-EXTR",
  INTERIOR_WALL: "A-WALL",
  DOOR: "A-DOOR",
  WINDOW: "A-GLAZ",
  FIXTURE: "A-FLOR-FIXT",
  AREA: "A-AREA-IDEN",
  DIMS: "A-ANNO-DIMS",
  TEXT: "A-ANNO-TEXT",
  TITLE: "A-ANNO-TTLB",
} as const;

export type LayerName = (typeof LAYER)[keyof typeof LAYER];

// Visual treatments per layer in the SVG renderer.
export const LAYER_STYLE: Record<LayerName, { stroke: string; strokeWidth: number; fill?: string }> = {
  "A-WALL-EXTR": { stroke: "#1a1a1a", strokeWidth: 2.5 },
  "A-WALL": { stroke: "#1a1a1a", strokeWidth: 1.5 },
  "A-DOOR": { stroke: "#7a1a1a", strokeWidth: 1 },
  "A-GLAZ": { stroke: "#1a4a7a", strokeWidth: 1 },
  "A-FLOR-FIXT": { stroke: "#444", strokeWidth: 0.8 },
  "A-AREA-IDEN": { stroke: "#1a1a1a", strokeWidth: 0 },
  "A-ANNO-DIMS": { stroke: "#444", strokeWidth: 0.6 },
  "A-ANNO-TEXT": { stroke: "#1a1a1a", strokeWidth: 0 },
  "A-ANNO-TTLB": { stroke: "#1a1a1a", strokeWidth: 1 },
};

export const ZONE_FILL: Record<string, string> = {
  public: "#f1f4ee",
  private: "#efeaf3",
  service: "#f4ece2",
  circulation: "#f1f1ee",
  exterior: "#e9eff3",
};
