import { useState } from 'react';
import { ApiError } from '../api/client';
import { copy } from '../copy';
import { startAutopilot, stopAutopilot } from '../state/autopilot';
import { runStep } from '../state/endpoints';
import { useStore } from '../state/store';

const STEPS = ['inject_poison', 'run_agents', 'audit', 'supersede', 'restore', 'reset'] as const;

export function ScenarioControls() {
  const scenario = useStore((s) => s.scenario);
  const autopilot = useStore((s) => s.autopilot);
  const pushToast = useStore((s) => s.pushToast);
  const [pending, setPending] = useState<string | null>(null);
  const active = scenario.active ?? pending;

  async function go(step: string) {
    setPending(step);
    try {
      await runStep(step);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'FORBIDDEN_ROLE') pushToast(copy.errors.forbiddenRoleScenario);
      else pushToast(copy.errors.generic(e instanceof ApiError ? e.code : 'ERROR', e instanceof ApiError ? e.message : 'Request failed'));
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="panel scenario" aria-label={copy.scenario.title}>
      <h2 className="panel-h">{copy.scenario.title}</h2>
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button
              className={`btn step${s === 'audit' ? ' primary' : ''}${s === 'reset' ? ' ghost' : ''}`}
              disabled={!!active || autopilot}
              onClick={() => void go(s)}
              title={copy.scenario.hints[s]}
            >
              <span className="stepno" aria-hidden="true">{i + 1}</span>
              {copy.scenario.steps[s]}
            </button>
          </li>
        ))}
      </ol>
      <p className="progress" role="status" aria-live="polite">
        {active
          ? copy.scenario.running(copy.scenario.steps[active]?.toLowerCase() ?? active)
          : scenario.lastState === 'failed' && scenario.detail
            ? copy.scenario.failed(scenario.detail)
            : ' '}
      </p>
      <button
        className={`btn autopilot${autopilot ? ' on' : ''}`}
        onClick={() => (autopilot ? stopAutopilot() : void startAutopilot())}
        title={copy.scenario.autopilotHint}
      >
        {autopilot ? copy.scenario.autopilotStop : copy.scenario.autopilot}
      </button>
    </section>
  );
}
