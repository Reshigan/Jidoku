/* 11 · Documents — the project pack, projected rather than written.

   Every other document tool in this industry is an editor: someone types the solution design, and
   from that moment it is a claim about the system rather than a reading of it. This screen has no
   editor and will not grow one. What it shows is generated from signed IR, the decision register
   and the ledger at the moment you ask for it, which is why the only control on the page is the one
   that asks again.

   The renderer below is deliberately small. The server sends Markdown because Markdown is the
   document, and a Markdown library would be a runtime dependency added to display text the platform
   itself wrote in a format it controls. */
import { useEffect, useMemo, useState } from "react";
import { ApiError, platform } from "./api";
import { Empty, Section, Skeleton } from "./ui";
import "./views_document.css";

type Doc = { id: string; title: string };

/** Inline spans: `code`, **bold**, *italic*. Split on the delimiters rather than replacing into
    HTML, so nothing the ledger holds can be interpreted as markup. */
function inline(text: string, keyBase: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    const k = `${keyBase}-${i}`;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={k}>{p.slice(1, -1)}</code>;
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={k}>{p.slice(2, -2)}</strong>;
    return <span key={k}>{p}</span>;
  });
}

const isRule = (l: string) => /^\|[\s|:-]+\|$/.test(l.trim());
const cells = (l: string) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

/** Markdown as the server writes it: headings, tables, bullets, blockquotes, emphasis. Not a
    general parser — a reader for one known producer, which is why it can be this short. */
function Markdown({ text }: { text: string }) {
  const out: JSX.Element[] = [];
  const lines = text.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const k = `l${i}`;

    if (!line.trim()) continue;

    if (line.startsWith("|") && isRule(lines[i + 1] ?? "")) {
      const head = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].startsWith("|")) rows.push(cells(lines[i++]));
      i--;
      out.push(
        /* Tables scroll inside themselves. A config book on a 15-object engagement is wider than
           the panel, and a page that scrolls sideways loses the andon rail. */
        <div className="doc-tablewrap" key={k}>
          <table className="doc-table">
            <thead><tr>{head.map((h, j) => <th key={j}>{inline(h, `${k}h${j}`)}</th>)}</tr></thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => <td key={ci}>{inline(c, `${k}r${ri}c${ci}`)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const Tag = (["h1", "h2", "h3", "h4"] as const)[h[1].length - 1];
      out.push(<Tag className={`doc-${Tag}`} key={k}>{inline(h[2], k)}</Tag>);
      continue;
    }

    if (line.startsWith("---")) { out.push(<hr className="doc-rule" key={k} />); continue; }

    if (line.startsWith("> ")) {
      out.push(<p className="doc-lede" key={k}>{inline(line.slice(2), k)}</p>);
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(lines[i++].slice(2));
      i--;
      out.push(
        <ul className="doc-list" key={k}>
          {items.map((it, j) => <li key={j}>{inline(it, `${k}i${j}`)}</li>)}
        </ul>,
      );
      continue;
    }

    /* A whole line in italics is the generator saying something about itself — a not-generated
       note, the provenance footer. Marked so it never reads as content of the document. */
    const meta = /^\*(.+)\*$/.exec(line.trim());
    if (meta) { out.push(<p className="doc-meta" key={k}>{inline(meta[1], k)}</p>); continue; }

    out.push(<p className="doc-p" key={k}>{inline(line, k)}</p>);
  }
  return <>{out}</>;
}

export function DocumentsView(props: { eid: string | null; onRefusal: (t: string, x: string) => void }) {
  const { eid, onRefusal } = props;
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [pick, setPick] = useState<string>("config-rationale");
  const [text, setText] = useState<string | null>(null);
  const [stamp, setStamp] = useState<string>("");

  useEffect(() => {
    if (!eid) return;
    let live = true;
    platform.documents(eid)
      .then((r) => { if (live) setDocs(r.documents); })
      .catch((e) => { if (live && e instanceof ApiError && !e.notAvailable) onRefusal("Documents", e.detail); });
    return () => { live = false; };
  }, [eid, onRefusal]);

  useEffect(() => {
    if (!eid) return;
    let live = true;
    setText(null);
    platform.document(eid, pick)
      .then((t) => { if (live) { setText(t); setStamp(new Date().toLocaleTimeString()); } })
      .catch((e) => {
        if (!live || !(e instanceof ApiError)) return;
        /* A document that is not there yet is an empty state, not a refusal — the modal is
           reserved for the server saying no, in its own words. */
        if (e.notAvailable) { setText(""); return; }
        onRefusal("Documents", e.detail);
      });
    return () => { live = false; };
  }, [eid, pick, onRefusal]);

  const title = useMemo(() => docs?.find((d) => d.id === pick)?.title ?? "", [docs, pick]);

  if (!eid) return <Empty title="No engagement" body="Choose an engagement to read its documents." />;

  return (
    <Section
      title="Documents"
      note={title}
      status={stamp ? `projected ${stamp}` : ""}
      className="grow scrolls"
      actions={
        <div className="doc-tabs" role="tablist" aria-label="Documents">
          {(docs ?? []).map((d) => (
            <button
              key={d.id}
              role="tab"
              aria-selected={d.id === pick}
              className="doc-tab"
              data-on={d.id === pick}
              onClick={() => setPick(d.id)}
            >
              {d.id.replace(/-/g, " ")}
            </button>
          ))}
        </div>
      }
    >
      {/* Said once, at the top, because the reader's first question about a generated document is
          whether a person wrote it and whether it is current. */}
      <p className="doc-provenance">
        Nothing on this page was authored. Every line is read from this engagement's signed intent,
        decision register and ledger when you open it — a document that could disagree with the
        system cannot be produced here.
      </p>
      {text === null ? <Skeleton rows={8} tall />
        : text === "" ? <Empty title="Nothing to project yet"
                               body="This document reads from the engagement's signed intent and ledger. Once there is intent to read, it appears here." />
        : <article className="doc"><Markdown text={text} /></article>}
    </Section>
  );
}
