"""FilmCrew's Production Engine — the pipeline and the contract lifecycle.

The domain knowledge FilmCrew owns: a production moves through stages, roles
are cast, and a contract passes through states before anyone is actually paid.

Two rules carry the design, and both are about **not crediting work that has
not happened**:

* **Stages and contract states only move forward, one step at a time.** A
  production cannot jump from drafting to wrapped, and a contract cannot skip
  from offered to paid. Skipping is how a creator ends up credited for work
  nobody delivered.
* **The credit fires on `paid`, not on `hired`.** An offer can be withdrawn and
  a shoot can collapse; money changing hands is the first moment the work is
  evidenced. This is a real correction made in the app being modelled — it
  originally credited on hire.

FilmCrew publishes `hire.completed` and holds **no reference to FrameVault**.
It does not import it, call it, or know it exists.
"""

#: A production moves along this line, one step at a time.
STAGES = ("drafting", "open", "in_production", "wrapped")

#: A contract does the same. `paid` is terminal and is the only state that
#: credits anybody.
CONTRACT_STATES = ("offered", "accepted", "delivered", "paid")


class PipelineError(Exception):
    """Raised when a transition would skip a step or reverse one."""


def _advance(current, sequence, what):
    if current not in sequence:
        raise PipelineError(f"Unknown {what} '{current}'.")
    index = sequence.index(current)
    if index == len(sequence) - 1:
        raise PipelineError(f"'{current}' is the final {what}; there is nothing after it.")
    return sequence[index + 1]


class Contract:
    """One agreement between a production and a person.

    Money is held in **integer minor units** (pence, cents). Floating-point
    money accumulates rounding error, and a fee that is a hundredth of a penny
    wrong is a fee somebody eventually notices.
    """

    __slots__ = ("id", "production_id", "role", "creator", "fee_cents", "state", "history")

    def __init__(self, id, production_id, role, creator, fee_cents=0):
        self.id = id
        self.production_id = production_id
        self.role = role
        self.creator = creator
        self.fee_cents = int(fee_cents)
        self.state = "offered"
        self.history = ["offered"]

    @property
    def is_paid(self):
        return self.state == "paid"

    def advance(self):
        self.state = _advance(self.state, CONTRACT_STATES, "contract state")
        self.history.append(self.state)
        return self.state

    def describe(self):
        return f"{self.creator} as {self.role} ({self.state})"

    def __repr__(self):
        return f"<Contract {self.describe()}>"


class Production:
    """One production, its roles and its contracts."""

    __slots__ = ("id", "title", "stage", "roles", "contracts")

    def __init__(self, id, title):
        self.id = id
        self.title = title
        self.stage = "drafting"
        self.roles = {}
        self.contracts = {}

    def advance(self):
        self.stage = _advance(self.stage, STAGES, "stage")
        return self.stage

    def describe(self):
        return f"{self.title} [{self.stage}] — {len(self.contracts)} contract(s)"

    def __repr__(self):
        return f"<Production {self.describe()}>"


class ProductionEngine:
    """Productions, casting and contracts — publishing as it goes.

    Every state change is announced. Nothing here knows who listens, which is
    exactly what makes FrameVault's reputation work possible without FilmCrew
    depending on it.
    """

    def __init__(self, bus=None, space_id="", source="filmcrew"):
        self.bus = bus
        self.space_id = space_id
        self.source = source
        self.productions = {}
        self._sequence = 0

    def _next_id(self, prefix):
        self._sequence += 1
        return f"{prefix}-{self._sequence:04d}"

    def _publish(self, kind, subject_id, payload):
        if self.bus is None:
            return None
        return self.bus.publish(self.space_id, kind, subject_id, payload, source=self.source)

    # -- productions -------------------------------------------------------

    def create_production(self, title):
        production = Production(self._next_id("PRD"), title)
        self.productions[production.id] = production
        self._publish("production.created", production.id, {"title": title})
        return production

    def advance_production(self, production_id):
        production = self._require(production_id)
        stage = production.advance()
        self._publish("production.staged", production_id,
                      {"title": production.title, "stage": stage})
        return stage

    def post_role(self, production_id, role, fee_cents=0):
        production = self._require(production_id)
        if production.stage == "drafting":
            raise PipelineError(
                "A production must be open before roles are posted — "
                "casting a draft credits people for work that may never start.")
        production.roles[role] = {"fee_cents": int(fee_cents), "filled": False}
        self._publish("role.posted", production_id,
                      {"title": production.title, "role": role, "fee_cents": int(fee_cents)})
        return production.roles[role]

    # -- casting and contracts ---------------------------------------------

    def offer(self, production_id, role, creator):
        """Offer a role. Announced, but credits nobody — an offer can be
        withdrawn."""
        production = self._require(production_id)
        if role not in production.roles:
            raise PipelineError(f"No such role '{role}' on {production.title}.")
        if production.roles[role]["filled"]:
            raise PipelineError(f"'{role}' is already filled.")

        contract = Contract(self._next_id("CON"), production_id, role, creator,
                            production.roles[role]["fee_cents"])
        production.contracts[contract.id] = contract
        production.roles[role]["filled"] = True

        self._publish("role.cast", contract.id,
                      {"creator": creator, "role": role, "production": production.title})
        return contract

    def advance_contract(self, production_id, contract_id):
        """Move a contract one state forward, publishing as it goes.

        `paid` is the only state that credits anyone. Everything before it is
        an intention.
        """
        production = self._require(production_id)
        contract = production.contracts.get(contract_id)
        if contract is None:
            raise PipelineError(f"No such contract '{contract_id}'.")

        state = contract.advance()
        payload = {
            "creator": contract.creator,
            "role": contract.role,
            "production": production.title,
            "production_id": production_id,
            "fee_cents": contract.fee_cents,
            "state": state,
        }

        if state == "paid":
            # The moment the work is evidenced. Anyone listening credits now,
            # and not a step earlier.
            self._publish("hire.completed", contract.id, payload)
        else:
            self._publish("contract.advanced", contract.id, payload)
        return state

    def pay(self, production_id, contract_id):
        """Run a contract all the way to paid."""
        while True:
            state = self.advance_contract(production_id, contract_id)
            if state == "paid":
                return state

    # -- reading -----------------------------------------------------------

    def _require(self, production_id):
        production = self.productions.get(production_id)
        if production is None:
            raise PipelineError(f"No such production '{production_id}'.")
        return production

    def contracts_for(self, creator):
        return [c for p in self.productions.values()
                for c in p.contracts.values() if c.creator == creator]

    def unfilled_roles(self, production_id):
        production = self._require(production_id)
        return [r for r, info in production.roles.items() if not info["filled"]]

    def payroll_cents(self, production_id):
        """What this production has actually paid out, in minor units."""
        production = self._require(production_id)
        return sum(c.fee_cents for c in production.contracts.values() if c.is_paid)

    def summary(self, production_id):
        production = self._require(production_id)
        contracts = list(production.contracts.values())
        return {
            "title": production.title,
            "stage": production.stage,
            "roles": len(production.roles),
            "unfilled": len(self.unfilled_roles(production_id)),
            "contracts": len(contracts),
            "paid": sum(1 for c in contracts if c.is_paid),
            "payroll_cents": self.payroll_cents(production_id),
        }
