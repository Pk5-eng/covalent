import { usePlanStore, type Stage } from "../state/planStore";

const STEPS: { id: Stage; label: string }[] = [
  { id: "boundary", label: "Boundary" },
  { id: "rooms", label: "Rooms" },
  { id: "generate", label: "Generate" },
  { id: "plan", label: "Edit & Export" },
];

export function Stepper() {
  const stage = usePlanStore((s) => s.stage);
  const setStage = usePlanStore((s) => s.setStage);
  const plan = usePlanStore((s) => s.plan);
  const check = usePlanStore((s) => s.check);
  const rooms = usePlanStore((s) => s.rooms);

  const roomsCount = Object.values(rooms).reduce((a, b) => a + b, 0);
  const currentIdx = STEPS.findIndex((s) => s.id === stage);

  // Stages reachable based on progress so far
  function reachable(target: Stage): boolean {
    const targetIdx = STEPS.findIndex((s) => s.id === target);
    if (targetIdx === 0) return true;
    if (target === "rooms") return true; // always allowed to go back to rooms
    if (target === "generate") return roomsCount > 0 && check?.ok === true;
    if (target === "plan") return !!plan;
    return false;
  }

  function statusClass(idx: number, id: Stage): string {
    if (id === stage) return "step current";
    // a stage is "done" if it is before the current one in order AND reachable
    if (idx < currentIdx) return "step done";
    return "step";
  }

  return (
    <nav className="stepper" aria-label="Workflow stages">
      {STEPS.map((s, i) => (
        <span key={s.id} style={{ display: "contents" }}>
          {i > 0 && <span className="separator" />}
          <button
            className={statusClass(i, s.id)}
            onClick={() => setStage(s.id)}
            disabled={!reachable(s.id)}
            aria-current={s.id === stage ? "step" : undefined}
            title={s.label}
          >
            <span className="bubble">{i < currentIdx ? "✓" : i + 1}</span>
            <span>{s.label}</span>
          </button>
        </span>
      ))}
    </nav>
  );
}
