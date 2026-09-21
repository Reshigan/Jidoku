/* 14 · Crew — the team takes the engagement as far as it can go alone, then hands it back.

   Five agents with opposed objectives, each holding only the authority its ring permits. The
   report shows what each one was allowed to do beside what it did, because a run that listed the
   work without the authority would read like a person's and hide the whole argument: the operator
   cannot emit an artefact, the auditor cannot write a single ledger row, and no ring an agent can
   occupy holds APPROVE.

   So the run ends in a handover. Every Tier-A write comes back rehearsed, never written — the
   crew has no way to arm one. What is waiting on a person is the first thing on the screen,
   because it is the only part somebody has to act on. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, CrewCard, CrewRun, NightShift, TeamMember, platform } from "./api";
import { Empty, Field, Pill, Section } from "./ui";

/** Ring 3 reads as the loudest badge on the card: the auditor's whole power is that it has none. */
const RING_LAMP: Record<string, string> = { AGENT: "run", SERVICE: "run", UNTRUSTED: "call" };
const RING_WORDS: Record<string, string> = {
  AGENT: "ring 2 · agent", SERVICE: "ring 1 · service", UNTRUSTED: "ring 3 · untrusted",
};
/* A write that reached a customer's system reads green; one that stopped at a gate reads amber;
   a refusal or a half-landed batch reads red. Nothing here is decorative — an operator scanning
   this column is asking "did we change production", and the colour has to answer it. */
const STATUS_LAMP: Record<string, string> = {
  VERIFIED: "run", APPLIED: "run",
  DRY_RUN: "call", IN_TRANSPORT: "call", HANDED_OFF: "call",
  REFUSED: "stop", FAILED: "stop", PARTIAL: "stop", DRIFTED: "stop",
};

export function CrewView(props: {
  eid: string | null;
  canRun: boolean;            // execute — the builder's authority, and not one permission more
  onRefusal: (title: string, text: string) => void;
  onChanged: () => Promise<void>;  // a run raises decisions and ledgers evidence; the console must learn
}) {
  const { eid, onRefusal } = props;
  const [run, setRun] = useState<CrewRun | null>(null);
  const [night, setNight] = useState<NightShift | null>(null);
  const [team, setTeam] = useState<TeamMember[] | null>(null);
  const [week, setWeek] = useState<Record<string, number>>({});
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [joiner, setJoiner] = useState({ name: "", authority: "", cost: "1", tz: "",
                                         capacity_per_week: "20" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!eid) return;
    platform.lastRun(eid)
      .then((r) => setRun(r.crew.length ? r : null))
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The last run", e.detail); });
    platform.lastNight(eid)
      .then((n) => setNight(n.handover ? n : null))
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The handover", e.detail); });
    platform.team(eid)
      .then((t) => { setTeam(t.people); setWeek(t.asked_this_week); setAnswers(t.answers_in_hours); })
      .catch((e) => { if (e instanceof ApiError && !e.notAvailable) onRefusal("The team", e.detail); });
  }, [eid, onRefusal]);

  useEffect(() => { setRun(null); setNight(null); setTeam(null); load(); }, [load]);

  if (!eid) return <Empty title="No engagement" body="Choose an engagement to put the crew on it." />;

  /** A person's word, under their own name. The server refuses it where the object is readable,
      and that refusal is quoted rather than pre-empted here. */
  const attest = async (key: string) => {
    setBusy(true);
    try {
      await platform.attest(eid, key);
      setRun(await platform.runCrew(eid));
      await props.onChanged();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("The attestation was not recorded", e.detail);
    } finally {
      setBusy(false);
    }
  };

  /** Adds one person. The API replaces the list, so the console sends the team it is showing plus
      the new name — a team is a statement about now, and the screen is what "now" looks like. */
  const addPerson = async () => {
    try {
      const person = {
        name: joiner.name.trim(),
        authority: joiner.authority.split(/[,\s]+/).filter(Boolean),
        cost: Number(joiner.cost) || 1,
        tz: joiner.tz.trim(),
        capacity_per_week: Number(joiner.capacity_per_week) || 20,
      };
      const out = await platform.registerTeam(eid, [...(team ?? []), person]);
      setTeam(out.people);
      setJoiner({ name: "", authority: "", cost: "1", tz: "", capacity_per_week: "20" });
    } catch (e) {
      if (e instanceof ApiError) onRefusal("That person was not registered", e.detail);
    }
  };

  const workTheNight = async () => {
    setBusy(true);
    try {
      setNight(await platform.runNight(eid));
      await props.onChanged();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("The night shift did not run", e.detail);
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    setBusy(true);
    try {
      setRun(await platform.runCrew(eid));
      await props.onChanged();
    } catch (e) {
      if (e instanceof ApiError) onRefusal("The crew did not run", e.detail);
    } finally {
      setBusy(false);
    }
  };

  const v = run?.verification ?? null;
  const checked = v
    ? v.verified.length + v.drift.length + v.not_applied.length + v.awaiting_a_person.length +
      v.unconfirmable.length + v.attested.length + v.skipped.length
    : 0;

  return (
    <>
      <Section
        title="The night shift"
        note="The work that needs no person, done while nobody is watching — and a handover in the morning. Everything found is ranked by what it costs to stay quiet, and the interruption budget is hard."
        lamp={night ? (night.interrupted.length ? "stop" : "run") : undefined}
        status={night?.budget
          ? night.budget.spent
            ? `woke somebody ${night.budget.spent} of ${night.budget.of} times`
            : "nobody was woken"
          : undefined}
        actions={
          <button className="btn" disabled={!props.canRun || busy} onClick={() => void workTheNight()}>
            {busy ? "Working…" : night ? "Work another night" : "Work the night"}
          </button>
        }
      >
        {!night ? (
          <p className="mut">
            No night has been worked on this engagement. A night reads every system, checks signed
            intent against them, chases what was handed to a person, re-scores the twin and runs
            the controls — then writes the morning a note in first person: what I did, what I
            found, what I need from you today.
          </p>
        ) : (
          <>
            {/* The handover is markdown because it is meant to travel — into an email, a channel,
                the ledger. On screen an operator should read it, not its syntax, so the only
                markup it uses is rendered rather than shown. */}
            <div className="verbatim calm" style={{ whiteSpace: "pre-wrap" }}>
              {night.handover.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
                part.startsWith("**") && part.endsWith("**")
                  ? <strong key={i}>{part.slice(2, -2)}</strong>
                  : <span key={i}>{part}</span>)}
            </div>
            {team !== null && (
              <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
                {team.length === 0
                  ? "Nobody is registered on this engagement, so the handover names a role rather " +
                    "than a person — honest, and nobody answers a request addressed to nobody."
                  : `Asks go to the least senior person registered who may sign the thing, in their own ` +
                    `working hours, and nobody is asked past the capacity their organisation ` +
                    `declared: ${team.map((p) => {
                      const asked = week[p.name] ?? 0;
                      const speed = answers[p.name];
                      return `${p.name} (${p.authority.join(", ") || "no authority"}` +
                        `, ${asked}/${p.capacity_per_week} this week` +
                        `${speed === undefined ? "" : `, answers in ~${speed}h`})`;
                    }).join(" · ")}.`}
              </p>
            )}
            {night.interrupted.length > 0 && (
              <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
                Woken for:{" "}
                {night.interrupted.map((f) => `${f.what} (cost ${f.cost})`).join("; ")}. Anything
                below {night.budget?.threshold} waits for the morning.
              </p>
            )}
          </>
        )}
        {props.canRun && (
          <div className="row" style={{ gap: 12, alignItems: "flex-end", marginTop: 14, flexWrap: "wrap" }}>
            <Field label="Who" value={joiner.name} placeholder="T. Mabaso"
                   onChange={(v) => setJoiner({ ...joiner, name: v })} />
            <Field label="May" value={joiner.authority} placeholder="approve, resolve_dp"
                   onChange={(v) => setJoiner({ ...joiner, authority: v })} />
            <Field label="Costs" value={joiner.cost}
                   onChange={(v) => setJoiner({ ...joiner, cost: v })} />
            <Field label="Timezone" value={joiner.tz} placeholder="Africa/Maputo"
                   onChange={(v) => setJoiner({ ...joiner, tz: v })} />
            <Field label="Asks a week" value={joiner.capacity_per_week}
                   onChange={(v) => setJoiner({ ...joiner, capacity_per_week: v })} />
            <button className="btn" disabled={!joiner.name.trim() || !joiner.authority.trim()}
                    onClick={() => void addPerson()}>
              Add to the team
            </button>
          </div>
        )}
      </Section>

      <Section
        title="The crew"
        note="Five agents, opposed objectives, no shared memory. Each one holds only what its ring permits — and no ring an agent can occupy can approve."
        lamp={run ? (run.halted ? "stop" : run.plan_blocked ? "call" : "run") : undefined}
        status={run ? (run.halted ? "line halted" : `${run.waiting_on_a_person.length} waiting on a person`) : undefined}
        actions={
          <button className="btn" disabled={!props.canRun || busy} onClick={() => void start()}>
            {busy ? "The crew is working…" : run ? "Run again" : "Put the crew on it"}
          </button>
        }
      >
        {!run ? (
          <p className="mut">
            Nobody has run the crew on this engagement. A run sequences the work, snapshots every
            target, writes each Tier-A step — for real where an approver has armed the system, as
            a rehearsal everywhere else — carries an ABAP change along its declared route until it
            lands in production, emits the artefacts a person must execute by hand, raises the
            statutory questions nobody may guess, objects to its own output from a ring that
            cannot write, prices what is left and verifies the result. It cannot arm a target and
            it cannot approve anything, so it ends by handing the engagement back.
          </p>
        ) : (
          <>
            {run.halted && (
              <div className="verbatim" style={{ marginBottom: 14 }}>
                The line is halted: {run.halt_reason}
              </div>
            )}
            {run.plan_blocked && (
              <>
                <p className="mut">
                  The plan stopped, which is the platform working — JIDOKA does not sequence
                  around an open question or guess a value to get past one. The planner's words,
                  verbatim:
                </p>
                <div className="verbatim">{run.plan_blocked}</div>
              </>
            )}
            <div className="tblwrap" style={{ marginTop: 14 }}>
              <table className="tbl">
                <thead>
                  <tr><th>Agent</th><th>Authority</th><th>Objective</th><th>Did</th><th>Syscalls</th></tr>
                </thead>
                <tbody>
                  {run.crew.map((card: CrewCard) => (
                    <tr key={card.name}>
                      <td>
                        {card.name}
                        {card.state === "KILLED" && (
                          <div><Pill lamp="stop">{card.exit_reason || "killed"}</Pill></div>
                        )}
                      </td>
                      <td>
                        <Pill lamp={RING_LAMP[card.ring]}>{RING_WORDS[card.ring] ?? card.ring}</Pill>
                        <div className="mut mono" style={{ fontSize: 11.5, marginTop: 4 }}>
                          {card.capabilities.join(" · ")}
                        </div>
                      </td>
                      <td className="mut" style={{ fontSize: 12.5 }}>{card.objective}</td>
                      <td style={{ fontSize: 12.5 }}>
                        {card.did.length === 0
                          ? <span className="mut">nothing to do this pass</span>
                          : card.did.map((d, i) => <div key={i}>{d}</div>)}
                      </td>
                      <td className="mono">{card.syscalls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>

      {run && run.waiting_on_a_person.length > 0 && (
        <Section
          title="Waiting on a person"
          note="Where the machine stops. Arming a live write and approving work are human acts, by design and not by omission."
          lamp="call"
          status={`${run.waiting_on_a_person.length} item${run.waiting_on_a_person.length === 1 ? "" : "s"}`}
        >
          <div className="tblwrap">
            <table className="tbl">
              <thead><tr><th>What</th><th>Who</th><th>Why</th></tr></thead>
              <tbody>
                {run.waiting_on_a_person.map((w, i) => (
                  <tr key={i}>
                    <td className="mono">{w.what}</td>
                    <td>{w.who}</td>
                    <td style={{ fontSize: 12.5 }}>{w.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {run && v && (
        <Section
          title="Verification"
          note="The pass the Verify screen runs, run again at the end of the crew's work. The test plan is the signed intent itself."
          lamp={v.planning_blocked ? "stop" : v.verified.length ? "run" : "idle"}
          status={`${checked} record${checked === 1 ? "" : "s"} checked`}
        >
          <div className="counters">
            <div className="counter"><b>{v.verified.length}</b><span>match the live system</span></div>
            <div className="counter"><b>{v.drift.length}</b><span>unexplained differences</span></div>
            <div className="counter"><b>{v.awaiting_a_person.length}</b><span>with a person</span></div>
            <div className="counter"><b>{v.not_applied.length}</b><span>not built yet</span></div>
            <div className="counter">
              <b>{v.unconfirmable.length}</b><span>no read path</span>
            </div>
            <div className="counter"><b>{v.attested.length}</b><span>attested, not checked</span></div>
          </div>
          {v.drift.length > 0 && (
            <div className="tblwrap" style={{ marginTop: 12 }}>
              <table className="tbl">
                <thead><tr><th>Record</th><th>Found</th><th>Decision</th></tr></thead>
                <tbody>
                  {v.drift.map((f) => (
                    <tr key={f.key}>
                      <td className="mono">{f.key}</td>
                      <td><Pill lamp="stop">{f.status === "MISSING" ? "Missing" : "Drifted"}</Pill></td>
                      <td className="mono">{f.decision_point}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {v.awaiting_a_person.length > 0 && (
            <>
              <p className="mut" style={{ marginTop: 12 }}>
                With a person — the platform produced the artefact and the work is not in the
                system yet. Tier B and C have no write path to take, so a person does them and
                JIDOKA re-reads the system to see it done. That is a chase with a date on it,
                never a decision point: it would stop the line over somebody's inbox.
              </p>
              <div className="tblwrap">
                <table className="tbl">
                  <thead><tr><th>Record</th><th>Tier</th><th>System</th><th>Handed over</th></tr></thead>
                  <tbody>
                    {v.awaiting_a_person.map((a) => (
                      <tr key={a.key}>
                        <td className="mono">{a.key}</td>
                        <td>{a.tier}</td>
                        <td className="mono">{a.system}</td>
                        <td className="mono">{a.handed_over || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {(v.unconfirmable.length > 0 || v.attested.length > 0) && (
            <>
              <p className="mut" style={{ marginTop: 12 }}>
                No read path — the product publishes nothing that reads these objects back, so no
                re-read will ever confirm them and waiting would be waiting forever. What is owed
                is a named person's word, on the chain, about the version of the intent they
                worked to. An attestation is never counted as a verification: this platform has
                not seen the system.
              </p>
              <div className="tblwrap">
                <table className="tbl">
                  <thead><tr><th>Record</th><th>Tier</th><th>Why it cannot be read</th><th>Attested</th></tr></thead>
                  <tbody>
                    {v.attested.map((a) => (
                      <tr key={a.key}>
                        <td className="mono">{a.key}</td>
                        <td>{a.tier}</td>
                        <td className="mut" style={{ fontSize: 12.5 }}>{a.reason}</td>
                        <td>
                          <Pill lamp="call">by {a.attested_by}</Pill>
                          <div className="mut mono" style={{ fontSize: 11.5, marginTop: 4 }}>{a.at}</div>
                          {a.note && <div className="mut" style={{ fontSize: 12 }}>{a.note}</div>}
                        </td>
                      </tr>
                    ))}
                    {v.unconfirmable.map((u) => (
                      <tr key={u.key}>
                        <td className="mono">{u.key}</td>
                        <td>{u.tier}</td>
                        <td className="mut" style={{ fontSize: 12.5 }}>{u.reason}</td>
                        <td>
                          {props.canRun ? (
                            <button className="btn" disabled={busy}
                                    onClick={() => void attest(u.key)}>
                              I made this change
                            </button>
                          ) : <Pill lamp="stop">nobody yet</Pill>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {v.not_applied.length > 0 && (
            <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
              Not built yet — signed intent describes {v.not_applied.length} record
              {v.not_applied.length === 1 ? "" : "s"} nobody has written. That is unbuilt work, not
              drift: nothing changed under anyone, because nothing was ever there. The plan is what
              closes it.
            </p>
          )}
        </Section>
      )}

      {run && (run.steps.length > 0 || run.artefacts.length > 0) && (
        <Section
          title="What the crew did"
          note="An armed target is written for real and verified against the live system. Everything else is a rehearsal: the payload is real, the write did not happen."
          status={run.economics ? `${run.economics.rehearsed} rehearsed · ${run.economics.manual_steps} for a person` : ""}
          className="grow scrolls"
        >
          <div className="tblwrap">
            <table className="tbl">
              <thead><tr><th>Step</th><th>Tier</th><th>System</th><th>Outcome</th><th>Detail</th></tr></thead>
              <tbody>
                {run.steps.map((s) => (
                  <tr key={s.key}>
                    <td className="mono">{s.key}</td>
                    <td>{s.tier}</td>
                    <td className="mono">{s.system}</td>
                    <td><Pill lamp={STATUS_LAMP[s.status] ?? "idle"}>{s.status.replace("_", " ").toLowerCase()}</Pill></td>
                    <td style={{ fontSize: 12.5 }}>
                      {s.detail}
                      {/* On the ABAP stack the write is half the change; where the change sits on
                          its route is the other half, and it is not an aside (ADR-0006). */}
                      {s.transport?.route?.length ? (
                        <div className="mut mono" style={{ fontSize: 11.5, marginTop: 4 }}>
                          {s.transport.request_id} · {s.transport.route.map((hop) => (
                            s.transport!.imported_into.includes(hop) || hop === s.transport!.route[0]
                              ? hop : `(${hop})`
                          )).join(" → ")}
                          {s.transport.in_production ? " · in production" : ` · next ${s.transport.next_hop}`}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {run.artefacts.map((a) => (
                  <tr key={a.key}>
                    <td className="mono">{a.key}</td>
                    <td>{a.tier}</td>
                    <td className="mut">—</td>
                    <td><Pill lamp="call">for a person</Pill></td>
                    <td style={{ fontSize: 12.5 }}>{a.human_step || a.kind}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {run.objections.length > 0 && (
            <>
              <p className="mut" style={{ marginTop: 14 }}>
                The auditor's objections. It holds READ_SYSTEM and HALT and nothing else, so it
                could not write one of these down — disagreement is the product, not a defect:
              </p>
              <ul className="mut" style={{ fontSize: 12.5 }}>
                {run.objections.map((o, i) => (
                  <li key={i}>
                    <span className="mono">{o.body.key}</span> — {o.body.finding}
                  </li>
                ))}
              </ul>
            </>
          )}

          {run.economics && (
            <p className="mut" style={{ marginTop: 12, fontSize: 12.5 }}>
              {run.economics.steps.A} step{run.economics.steps.A === 1 ? "" : "s"} this platform can
              write, {run.economics.manual_steps} a person must do by hand.
              Not priced, and not guessed at: {run.economics.not_priced.join(", ")}.
            </p>
          )}
        </Section>
      )}
    </>
  );
}
