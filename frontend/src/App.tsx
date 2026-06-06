import { useEffect, useState } from "react";
import { getHealth } from "./lib/api";
import { Stepper } from "./components/Stepper";
import { BoundaryStage } from "./components/stages/BoundaryStage";
import { RoomsStage } from "./components/stages/RoomsStage";
import { GenerateStage } from "./components/stages/GenerateStage";
import { PlanStage } from "./components/stages/PlanStage";
import { usePlanStore } from "./state/planStore";

export function App() {
  const [health, setHealth] = useState<string>("checking…");
  const stage = usePlanStore((s) => s.stage);

  useEffect(() => {
    getHealth()
      .then((h) => setHealth(`${h.service} ${h.version}`))
      .catch(() => setHealth(`api unreachable`));
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark">Covalent</span>
          <span className="tag">Floor Plan AI</span>
        </div>
        <Stepper />
        <div className="status">{health}</div>
      </header>

      {stage === "boundary" && <BoundaryStage />}
      {stage === "rooms" && <RoomsStage />}
      {stage === "generate" && <GenerateStage />}
      {stage === "plan" && <PlanStage />}
    </div>
  );
}
