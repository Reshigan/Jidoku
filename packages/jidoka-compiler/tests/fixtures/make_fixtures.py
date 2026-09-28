"""Build the mobilisation-pack fixtures: the real pack's shape, invented values.

The pack itself is client material and is never committed. What the tests need is its *shape* — a
three-row banner above the header, a task register with a dependency column, gates with named
approvers, a KT tracker and a deliverables register under different headers, decisions with no
declared type, boundary conditions with consequences, and an alignment matrix. All of that is here.
"""
from openpyxl import Workbook

BANNER = ["Fixture — invented values, same shape as a real mobilisation pack"]
NOTE = ["Yellow columns maintained by the PM."]
FOOT = ["ACME · FIXTURE-001 v1.0 · 1 Oct – 1 Dec 2026"]


def sheet(wb, name, header, rows):
    ws = wb.create_sheet(name)
    ws.append(BANNER); ws.append(NOTE); ws.append(FOOT); ws.append([])
    ws.append(header)
    for r in rows:
        ws.append(r)


wb = Workbook(); wb.remove(wb.active)
ws = wb.create_sheet("Summary"); ws.append(BANNER); ws.append(["A view, not a register."])

sheet(wb, "Tasks",
      ["ID", "Week", "Owner", "Task", "Gate/Control", "Due", "Depends on", "Status", "Note"],
      [["T-001", "B1", "PM", "Access check for all consultants", "DP-B01", "1 Oct", "",
        "Not started", ""],
       ["T-002", "B1", "Lead", "Take the baseline extract", "G1", "3 Oct", "T-001",
        "In progress", ""],
       ["T-003", "B2", "Lead", "Load the picklist option set", "G2", "10 Oct", "T-002; T-001",
        "Complete", ""]])

sheet(wb, "Gates", ["Gate", "Name", "Date", "Criteria", "Evidence", "Approver", "Passed"],
      [["G1", "Baseline accepted", "Fri 9 Oct", "Baseline extract taken and accepted",
        "Baseline manifest; profiling report", "Lead + client IT owner", ""],
       ["G2", "Foundation signed", "Fri 23 Oct", "Foundation objects verified in QAL",
        "Verification report", "Client IT owner", ""],
       ["G3", "Hypercare entry", "week 8", "Support model accepted", "Signed RACI",
        "Client IT owner", ""]])

# A second register in the same sheet, under its own header, after a blank row and a caption —
# exactly as the real pack writes its one-way doors below its gates.
ws = wb["Gates"]
ws.append([])
ws.append(["One-way doors"])
ws.append(["#", "Door", "When", "Control", "Approver", "Executed"])
ws.append(["D1", "Foundation freeze", "Fri 16 Oct", "Design authority sign-off", "Lead", ""])
ws.append(["D2", "Production data load", "Sat 28 Nov", "Two-person rule",
           "Load lead + client IT", ""])

sheet(wb, "Decisions", ["DP", "Decision", "Owner", "GONXT position", "Due", "Status"],
      [["DP-B01", "Which legal entities are in scope", "Client IT owner",
        "The four trading entities only", "3 Oct", "Open"],
       ["DP-B02", "Pay frequency for monthly staff", "Client payroll",
        "Monthly, last working day", "10 Oct", "Open"]])

sheet(wb, "Conditions", ["#", "Condition", "By", "Consequence if it fails"],
      [["1", "DEV and QAL instances provisioned", "1 Oct",
        "Week 1 cannot start; day-for-day slip"],
       ["2", "Legacy read-only access granted", "1 Oct",
        "No baseline extract; G1 cannot pass"]])

sheet(wb, "KT Tracker", ["#", "Week", "With", "Competence check", "Evidence", "Status",
                         "Signed by / date"],
      [["K1", "B1", "Lead", "Explains why the baseline extract is taken first",
        "Verbal check + screenshot", "Not started", ""]])

sheet(wb, "Deliverables", ["#", "Deliverable", "Draft due", "Validated by", "Accepted by",
                           "Final due", "Status"],
      [["D1", "Support model and RACI", "9 Oct", "Walkthrough with the IT owner",
        "Client IT owner", "27 Nov", "Not started"],
       ["D2", "Configuration workbook", "25 Oct", "Design authority review", "Lead", "8 Jan",
        "Not started"]])

wb.save("packages/jidoka-compiler/tests/fixtures/mobilisation_plan.xlsx")

wb = Workbook(); wb.remove(wb.active)
sheet(wb, "Data Ownership",
      ["Data domain", "Owner (system of record)", "Consumers", "Alignment note"],
      [["Employment and job information", "EC", "All modules, ECC, Analytics",
        "One writer; everyone else reads"],
       ["Pay components", "EC Payroll", "EC; Analytics", "Codes agreed at G2"]])
sheet(wb, "Interlocks",
      ["ID", "Source", "Target", "What flows / logic", "Failure mode if not held", "Ctrl", "Week"],
      [["I-01", "EC", "ECP", "Employee master replication",
        "Payroll runs against stale master data", "G2", "B2"],
       ["I-02", "Picklists", "EC", "Option set codes",
        "Fields reject values that look valid in the workbook", "G2", "B2"]])
wb.save("packages/jidoka-compiler/tests/fixtures/alignment_matrix.xlsx")
print("written")
