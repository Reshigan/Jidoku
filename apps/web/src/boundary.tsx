/* One panel throwing must not take the console with it.
   Observed, not theorised: when a view hit data it did not expect, React unmounted the whole tree
   — including the andon rail — and the screen went blank with no way back. On a console whose
   entire job is to tell an operator the state of a customer's systems, a blank screen is the
   worst possible failure: it says nothing, and it says it silently.

   This does not hide the fault. It contains it to the panel that caused it, names it in the
   panel's own place, and leaves every other panel and the rail working. */
import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { where: string; children: ReactNode };
type State = { err: Error | null };

export class Boundary extends Component<Props, State> {
  state: State = { err: null };

  static getDerivedStateFromError(err: Error): State {
    return { err };
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    // The console is read by operators, not developers, so the screen gets a sentence and the
    // devtools get the stack. Swallowing it entirely would make this a way to hide defects.
    console.error(`${this.props.where} failed to render`, err, info.componentStack);
  }

  render() {
    if (!this.state.err) return this.props.children;
    return (
      <section className="sec">
        <div className="sec-head"><h2>{this.props.where} could not be shown</h2></div>
        <div className="body">
          <p className="mut">
            This panel hit something it did not expect and has stopped rather than showing you
            something wrong. Everything else on this screen is still live, and nothing about the
            engagement has changed — the ledger is the record, and it is untouched.
          </p>
          {/* The fault in the platform's own words, as every refusal here is. */}
          <p className="verbatim" style={{ marginTop: 12 }}>{String(this.state.err.message || this.state.err)}</p>
        </div>
      </section>
    );
  }
}
