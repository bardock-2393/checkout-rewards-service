# Design Decisions

## Invariants I identified

- A cart produces at most one order, ever.
- No order line item can exceed the product's stock at the moment the order
  is committed.
- A coupon can be redeemed by at most one order.
- A coupon is never consumed by a checkout that doesn't fully succeed.
- A report is a pure read: calling it never changes totals, order count, or
  coupon state.
- Every paise figure traces back to integer inputs — no float ever touches
  a price, a discount, or a total.

Everything below is either enforcing one of these or explaining a case the
spec left open.

## Decision: Idempotent checkout via cart state, not an Idempotency-Key header

**Context:** A client can retry `POST /carts/{id}/checkout` after a timeout.
That retry must not create a second order or double-decrement stock.

**Options considered:**
- Option A: client sends an `Idempotency-Key` header, server caches
  responses per key.
- Option B: treat the cart itself as the idempotency key — a cart is either
  `open` or `checked_out`, and `checked_out` always points at exactly one
  order.

**Choice:** Option B.

**Why:** One cart → one checkout → one order is already the domain
invariant I have to enforce anyway (a cart can't be checked out twice). A
separate idempotency-key store would duplicate that same bookkeeping for no
extra benefit, since in this API a checkout request is already scoped to a
single cart id. I'd reach for Option A if checkout were a fire-and-forget
POST with no natural resource to key off of (e.g. "place an order" with the
cart contents in the body instead of a cart id in the URL).

**Consequences:** Retrying checkout on an already-checked-out cart returns
`200` with the existing order instead of an error — simpler for clients than
teaching them to interpret a 409 as "actually, you're fine." The limitation:
two genuinely different checkout *intents* can't share a cart id, but that's
not a real scenario here since a checked-out cart is dead anyway.

## Decision: Concurrency control via explicit per-resource `asyncio.Lock`

**Context:** Concurrent checkouts must not oversell inventory, and
concurrent redemptions must not double-spend a coupon.

**Options considered:**
- Option A: rely on Python's cooperative single-threaded event loop and just
  avoid `await` inside the critical section (true, but implicit — nothing
  stops someone adding an `await` later and silently breaking the
  guarantee).
- Option B: explicit `asyncio.Lock` per cart (serializes repeat/concurrent
  attempts on *that* cart) plus one global lock around the shared state
  (product stock, the order counter, coupons).
- Option C: a lock per product instead of one global lock.

**Choice:** Option B.

**Why:** Option A is real but fragile — it's an invariant enforced by
"don't write an await here," which is exactly the kind of thing that rots
silently. An explicit lock is something I can point at in a review and say
"this is where the invariant lives." Option C (per-product locks) would let
checkouts for different products run fully in parallel, but a single
checkout can touch multiple products at once, which means acquiring
multiple locks in a loop — and that's exactly how you build a deadlock. For
an in-memory store where the critical section is a few dict operations, one
global lock costs nothing measurable and removes the lock-ordering problem
entirely. Locks are always acquired cart-lock-first, then global-lock,
never the reverse, so there's no cycle.

**Consequences:** All shared-state mutation is strictly serialized, which
is fine at this scale but would become the bottleneck under real load — see
"Evolution to multiple instances" below.

## Decision: Validate everything, then commit everything, in one critical section

**Context:** A coupon must not be lost by a checkout that ultimately fails
on inventory, and inventory must not be partially decremented if a later
line item is out of stock.

**Options considered:**
- Option A: mutate as you go, roll back on failure.
- Option B: validate every line item and the coupon first, with zero
  mutation; only after everything passes, apply all mutations.

**Choice:** Option B.

**Why:** Rollback logic is where subtle bugs live — forgetting to undo one
of N mutations on one of M failure paths. Validate-then-commit means there's
nothing to roll back, because nothing is written until every precondition
has already passed. The whole thing runs inside one lock acquisition with no
`await` between validation and commit, so it's also naturally atomic.

**Consequences:** Checkout does two passes over the cart's line items
(validate, then mutate) instead of one — a cost that's irrelevant at cart-
sized N, but I'd reconsider for very large carts.

## Decision: Money as integer paise, discount floor-rounded

**Context:** "Calculate money without floating-point rounding errors" is an
explicit requirement, and discounts must never push a total negative.

**Options considered:**
- Option A: `Decimal` with a fixed scale.
- Option B: integers in the smallest currency unit (paise) throughout.

**Choice:** Option B.

**Why:** Prices are already whole paise at the source (there's no sub-paise
price), so there's no rounding to manage if I never introduce a fraction in
the first place. `Decimal` solves a problem I don't have here and drags
serialization/typing overhead into every layer.

**Rounding rule:** `discount = (subtotal_paise * percent_off) // 100`
(floored, never rounds up), `total = subtotal - discount`. Since
`percent_off` is always in `[0, 100]`, `discount <= subtotal` always holds,
so total can never go negative — that's enforced by construction, not by a
clamp.

## Decision: Coupon milestone semantics — one coupon per admin call, no backlog

**Context:** "Generate a coupon only if the configured milestone has been
reached and a coupon hasn't already been generated for that milestone" is
specified, but what happens if the admin is late and multiple milestones
have passed since the last call isn't.

**Options considered:**
- Option A: issue one coupon per skipped milestone (admin calls once after
  23 orders with n=5 → gets coupons for milestones 1-4 all at once).
- Option B: issue at most one coupon per call, for the highest unrewarded
  milestone, and treat all earlier skipped milestones as forfeited.

**Choice:** Option B.

**Why:** Option A risks an admin-side bug or a delayed cron turning into a
coupon-flooding incident — the spec gives no indication multiple coupons
per call is wanted, and "a coupon is generated only if... not already been
generated for that milestone" reads naturally as a singular check, not a
loop. Option B is the conservative reading and is trivial to change to A
later if the real requirement turns out to be "never miss a milestone."

**Consequences:** If nobody calls `/admin/coupons/generate` for a while,
earlier milestones are simply never rewarded. I'd flag this trade-off
explicitly to a PM rather than assume.

## Decision: Cart stores quantities only, not snapshotted prices

**Context:** Spec asks me to decide what happens when a product's price or
stock changes between add-to-cart and checkout.

**Options considered:**
- Option A: snapshot price into the cart item when it's added; honor that
  price at checkout regardless of later changes.
- Option B: cart stores only `product_id` + `quantity`; price and stock are
  always read live from the catalog, both when viewing the cart and at
  checkout.

**Choice:** Option B.

**Why:** Option A means `GET /cart` can show a price that's already stale
by the time the customer checks out, which is a worse customer experience
than Option B's alternative (the total can shift while the cart sits open,
but whatever `GET /cart` showed a second ago is exactly what checkout will
charge). It also avoids a whole class of "which price wins" bugs for carts
left open a long time.

**Consequences:** A customer who stares at an open cart for a long time
without refreshing could be surprised at checkout. Out of scope for this
exercise, but the real fix is a `price_changed` flag surfaced on `GET
/cart` if the price moved since a client last fetched it.

## Decision: Typed error hierarchy with stable error codes

**Context:** "Return errors that are distinguishable and useful to an API
client."

**Options considered:**
- Option A: a generic `HTTPException(status_code, detail=str)` per failure
  site.
- Option B: an `AppError` class hierarchy (`OutOfStockError`,
  `InvalidCouponError`, etc.) mapped once, centrally, to
  `{"error": CODE, "message": ...}`.

**Choice:** Option B.

**Why:** A client integrating against this API needs to branch on *why* a
request failed (show "out of stock" vs. "cart already placed" differently),
and a string `detail` message is not a contract — it can change wording
without warning. A `CODE` is. Centralizing the mapping in one exception
handler also means every service function just raises a typed error and
never thinks about HTTP status codes.

**Consequences:** Request-shape validation (e.g. a non-positive quantity)
still goes through FastAPI/Pydantic's native `422` response, which has a
different shape (`{"detail": [...]}`). I deliberately didn't unify these —
schema validation and domain validation are different layers, and forcing
Pydantic's errors into my custom shape would mean fighting the framework for
no real client benefit.

## Decision: Stack — Python + FastAPI over Node/TypeScript

**Context:** The job posting and this org's stated default is TypeScript/
Node.js; the assignment explicitly says use whatever you're comfortable
with.

**Options considered:** Node/Express/TypeScript vs. Python/FastAPI.

**Choice:** FastAPI.

**Why:** It's what I use daily in production right now, including the
exact pattern this exercise needs — async request handlers, Pydantic
request validation, and locking around shared async state. I'd rather hand
in code I can defend line-by-line under follow-up questioning than code in
a stack I'd have to re-derive idioms for under a time box.

**Consequences:** None functionally — the assignment is explicit that stack
choice doesn't matter for evaluation.

## Transaction / concurrency / idempotency strategy, summarized

- **Idempotency:** cart state (`open` → `checked_out`) is the idempotency
  key for checkout; repeat requests return the original order.
- **Concurrency:** per-cart lock + one global lock, acquired in a fixed
  order, guarding a validate-then-commit critical section with no `await`
  inside it.
- **Transactions:** there's no database, so "transaction" means "everything
  that must be atomic happens inside one lock acquisition." Nothing is
  written until every precondition (stock for every line, coupon validity)
  has already passed.

## What's implemented vs. intentionally deferred

**Implemented:** cart CRUD, live pricing, all-or-nothing inventory
validation, idempotent checkout, coupon milestone generation and
concurrency-safe single redemption, admin reporting, 18 tests including two
real concurrency races.

**Deferred (out of scope for a 4-6 hour exercise):**
- Auth/authz — the spec explicitly says not required; admin endpoints are
  unguarded and would need an auth layer before being real.
- A real payment gateway — checkout treats inventory+coupon success as
  payment success. I didn't build even a fake payment abstraction, since
  there's nothing for it to abstract over yet with no real gateway in play;
  I'd introduce one the moment a second "payment provider" needs to exist.
- Persistence — in-memory store means a restart loses all state. Explicitly
  allowed by the spec.
- Cart expiry/TTL — carts live forever in memory; a real system would want
  to reap abandoned ones.
- Multiple coupons per order, partial redemption, or percentage stacking —
  the spec describes a single optional coupon per checkout, so I didn't
  generalize beyond that.

## Evolution to multiple instances and a production database

The lock-based design only works within a single process — `asyncio.Lock`
is memory-local, so two instances behind a load balancer would each enforce
the invariant independently and still oversell/double-redeem across
instances. Moving to a real database, I'd replace the in-process locks with:

- Product stock: a single `UPDATE products SET stock = stock - :qty WHERE
  id = :id AND stock >= :qty` guarded by the row's natural atomicity (or
  `SELECT ... FOR UPDATE` if the decrement needs to happen alongside other
  writes in the same transaction) — the database becomes the lock.
- Coupon redemption: `UPDATE coupons SET status = 'redeemed' WHERE code =
  :code AND status = 'available'`, and check the row count affected — if
  zero, someone else already redeemed it. This is the DB equivalent of my
  in-memory "check status, then mutate" but it's atomic without any
  app-level lock at all.
- Checkout idempotency: a unique constraint on `cart_id` in the `orders`
  table turns a duplicate insert into a constraint violation I catch and
  convert into "return the existing order" — same semantics as today, just
  enforced by the database instead of in-process state.
- Order counter / milestone tracking: a single-row counters table updated
  inside the same transaction as order insertion, so the milestone check
  and the order creation commit or roll back together.

None of this needs a distributed lock (Redis, etc.) — row-level locking in
a relational database already gives the same guarantees a single-process
`asyncio.Lock` gives today, and it works across any number of instances.

## How I used AI tools

I used an AI coding assistant to scaffold the FastAPI project layout and
iterate on the error-handling boilerplate faster than typing it by hand. One
concrete thing I pushed back on: its first pass at the concurrency problem
reached for a Redis-backed distributed lock "to be safe for production."
I rejected that — this is a single-process in-memory store for a 4-6 hour
exercise, and pulling in Redis would've added an external dependency, a new
failure mode (what happens when Redis is unreachable?), and ops surface
area that has nothing to do with what's actually being evaluated here. I
kept the explicit `asyncio.Lock` design instead and wrote the "evolution to
multiple instances" section above specifically because that's the honest
answer to when a distributed lock *would* become necessary — not before
there's a second process.

## What I'd look at first with two more hours

1. Cart TTL/expiry, so abandoned carts don't hold stock hostage indefinitely
   (right now nothing reserves stock until checkout, so this is a minor
   correctness gap, not a blocker).
2. An OpenAPI/Postman export generated from the live schema (FastAPI already
   serves one at `/openapi.json` — I'd just check it in and link it from the
   README).
3. A `price_changed` signal on `GET /cart` so a client can tell the customer
   their total moved since they last looked, instead of only finding out at
   checkout.
4. Load-test the global lock under more concurrent carts than I tested here
   (I tested up to 6) to get a feel for where it'd actually start to bite.
