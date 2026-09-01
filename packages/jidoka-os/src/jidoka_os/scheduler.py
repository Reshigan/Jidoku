"""Shift clock + cost-of-silence scheduling. Two ideas from the team-member model, made mechanical:
work is scheduled by shift phase, and speaking to a human is a scarce resource allocated by cost."""
import heapq, itertools
from dataclasses import dataclass, field
from enum import Enum

class Shift(str, Enum):
    NIGHT = "NIGHT"   # extract, diff, regression, forecast, evidence assembly
    DAY   = "DAY"     # human-facing: decisions, approvals, briefs

@dataclass(order=True)
class Task:
    sort_key: tuple = field(init=False, repr=False)
    cost_of_silence: int = 0      # what it costs the programme if this waits until tomorrow
    name: str = ""
    shift: Shift = Shift.NIGHT
    interrupts_human: bool = False
    seq: int = 0
    def __post_init__(self):
        self.sort_key = (-self.cost_of_silence, self.seq)

class Scheduler:
    def __init__(self, interruption_budget: int = 3):
        self._q: list[Task] = []
        self._seq = itertools.count()
        self.interruption_budget = interruption_budget
        self.interruptions_used = 0
        self.deferred: list[Task] = []   # everything that did not earn an interruption -> handover

    def submit(self, name, cost_of_silence=0, shift=Shift.NIGHT, interrupts_human=False):
        t = Task(cost_of_silence=cost_of_silence, name=name, shift=shift,
                 interrupts_human=interrupts_human, seq=next(self._seq))
        heapq.heappush(self._q, t)
        return t

    def run(self, shift: Shift) -> list[Task]:
        """Returns tasks executed this shift. Human interruptions are capped; the rest defer to handover."""
        ran, keep = [], []
        while self._q:
            t = heapq.heappop(self._q)
            if t.shift != shift:
                keep.append(t); continue
            if t.interrupts_human:
                if self.interruptions_used >= self.interruption_budget:
                    self.deferred.append(t); continue
                self.interruptions_used += 1
            ran.append(t)
        for t in keep:
            heapq.heappush(self._q, t)
        return ran

    def handover(self) -> dict:
        """What the night shift leaves for the morning: done, deferred, and what needs a person."""
        return {"deferred": [t.name for t in self.deferred],
                "interruptions_used": self.interruptions_used,
                "budget": self.interruption_budget}
