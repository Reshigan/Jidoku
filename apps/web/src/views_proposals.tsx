/* Intent an agent drafted, waiting for a person.

   The agent may write a draft and may not sign one — there is nowhere in a draft for a signature to
   go, and the server refuses one that arrives with a name in it. So this screen is where a draft
   becomes intent, and the one design decision on it is what a signature costs: a person reads what
   the record says and where its values came from, and the name that goes on it is the one they are
   signed in as. The request that signs carries no name at all.

   Whoever drafted a record cannot sign it, so the button is offered to everybody and the server
   answers. Hiding it would put the rule in the console, where it would be true only until somebody
   opened the API. */
import { useCallback, useEffect, useState } from "react";

import { ApiError, ProposalRow, Proposals, platform } from "./api";
import { Empty, Field, Modal, Pill, Section, Skeleton, useStillHere } from "./ui";

const LAMP = { pending: "call", signed: "run", rejected: "idle" } as const;

export function ProposalsView(props: {
  eid: string;
  onRefusal: (title: string, text: string) => void;
}) {
  const { eid, onRefusal } = props;
  const [out, setOut] = useState<Proposals | null>(null);
  const [rejecting, setRejecting] = useState<ProposalRow | null>(null);
  const [reason, setReason] = useState("");
  const stillHere = useStillHere(eid);

  const load = useCallback(() => {
    const was = eid;
    platform.proposals(eid)
      .then((p) => { if (stillHere(was)) setOut(p); })
      .catch((e) => {
        if (stillHere(was) && e instanceof ApiError && !e.notAvailable) {
          onRefusal("The proposals", e.detail);
        }
      });
  }, [eid, onRefusal, stillHere]);

  useEffect(load, [load]);

  const act = (p: Promise<unknown>, title: string) =>
    p.then(load).catch((e) => { if (e instanceof ApiError) onRefusal(title, e.detail); });

  if (!out) return <Skeleton rows={5} tall />;

  if (out.proposals.length === 0) {
    return (
      <Empty
        title="No agent has drafted anything for this engagement"
        body="A design pass posts drafts here. Nothing an agent authors is intent until a person signs it, so an empty list means nothing is waiting — not that nothing was authored elsewhere."
      />
    );
  }

  const pending = out.proposals.filter((r) => r.status === "pending");
  const resolved = out.proposals.filter((r) => r.status !== "pending");

  return (
    <>
      <Section
        title="Waiting for a person"
        note="Drafts an agent authored. Each carries where its values came from and no signature. Signing makes it intent, under your name, through the same gates a workbook upload passes — and the person who drafted a record cannot be the one who signs it."
        lamp={pending.length ? "call" : "run"}
        status={pending.length ? `${pending.length} to read` : "nothing waiting"}
      >
        {pending.length === 0 ? (
          <p className="mut">Every draft has been signed or declined.</p>
        ) : (
          <table className="tbl">
            <thead>
              <tr><th scope="col">Record</th><th scope="col">Tier</th><th scope="col">Values</th>
                <th scope="col">Came from</th><th scope="col">Drafted by</th><th scope="col" /></tr>
            </thead>
            <tbody>
              {pending.map((r) => (
                <tr key={r.key}>
                  <td className="mono">{r.key}</td>
                  <td>{r.record.tier}</td>
                  <td className="mono spec-req" title={JSON.stringify(r.record.intent, null, 2)}>
                    {JSON.stringify(r.record.intent)}
                  </td>
                  <td>{r.record.source?.workbook}</td>
                  <td>{r.proposed_by}</td>
                  <td>
                    <button className="primary"
                            onClick={() => act(platform.signProposal(eid, r.key), `Signing ${r.key}`)}>
                      Sign
                    </button>{" "}
                    <button onClick={() => { setRejecting(r); setReason(""); }}>Decline</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {resolved.length > 0 && (
        <Section
          title="Already answered"
          note="What was signed and what was declined, and by whom. A declined draft stays in the record; the drafter may propose it again."
          status={`${out.signed} signed · ${out.rejected} declined`}
        >
          <table className="tbl">
            <thead>
              <tr><th scope="col">Record</th><th scope="col">State</th><th scope="col">By</th>
                <th scope="col">Reason</th></tr>
            </thead>
            <tbody>
              {resolved.map((r) => (
                <tr key={r.key}>
                  <td className="mono">{r.key}</td>
                  <td><Pill lamp={LAMP[r.status]}>{r.status}</Pill></td>
                  <td>{r.resolved_by}</td>
                  <td className="mut">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {rejecting && (
        <Modal title={`Decline ${rejecting.key}`} onClose={() => setRejecting(null)}>
          <Field label="Why it is declined" value={reason} onChange={setReason} required textarea
                 hint="The drafter reads this to fix the record, and an auditor reads it to see what a signature was withheld for." />
          <div className="spec-actions">
            <button className="primary" onClick={() => {
              act(platform.rejectProposal(eid, rejecting.key, reason), `Declining ${rejecting.key}`);
              setRejecting(null);
            }}>
              Decline it
            </button>
            <button onClick={() => setRejecting(null)}>Cancel</button>
          </div>
        </Modal>
      )}
    </>
  );
}
