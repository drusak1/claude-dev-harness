# Approach-class taxonomy

An **approach-class** is the load-bearing axis of a change — *what kind of move
it is*, not which file it touches. It is the unit the N-refute counter
aggregates on (`docs/DISCIPLINES.md` rule 2, rule 6).

The test for a good class tag: **if two attempts share a class, refuting one
should make you meaningfully less optimistic about the other.** If it doesn't,
they belong in different classes. If it does and you tagged them differently,
you have hidden a grind from the counter.

Add classes as you meet them. Keep them project-agnostic where you can — the
ledger is cross-project, and the compounding value is recognising that
`retry-at-call-site` failed in the worker before you try it in the API.

## Seed classes

| class | the move | typical objective |
|---|---|---|
| `caching` | store a computed result to avoid recomputing | cut latency / load |
| `batching` | collapse N calls into one | cut round-trips, N+1 |
| `indexing` | change the data's access structure | cut query time |
| `retry-at-call-site` | wrap a flaky call in retry/backoff | raise success rate |
| `timeout-tuning` | change deadlines/limits | stop cascading stalls |
| `input-validation` | reject bad data at a boundary | stop a class of errors |
| `schema-change` | change the data model itself | make bad states unrepresentable |
| `concurrency-model` | change how work is scheduled/parallelised | throughput |
| `state-relocation` | move state (client<->server, memory<->store) | consistency, latency |
| `dependency-swap` | replace a library/service | escape a limitation |
| `dependency-upgrade` | move to a newer version | pick up a fix |
| `config-tuning` | change knobs without changing code | quick win |
| `algorithm-change` | different algorithm, same interface | complexity class |
| `interface-redesign` | change the contract between components | remove a whole failure mode |
| `observability` | add measurement (not a fix) | locate the real cause |
| `requirement-change` | change what we are asked to deliver | dissolve the problem |

## Domain classes: backend (Python / API)

| class | the move | typical objective |
|---|---|---|
| `query-shape` | change what the ORM/SQL asks for (joins, eager loading, projection) | cut DB time, kill N+1 |
| `transaction-boundary` | move where a transaction opens/commits | consistency, lock contention |
| `serialization` | change what crosses the wire (fields, pagination, compression) | payload size, CPU |
| `async-offload` | move work out of the request path (queue, background task) | p99, timeouts |
| `connection-pooling` | change pool sizes / lifetimes | saturation under load |
| `idempotency` | make a handler safe to repeat | correctness under retry |
| `auth-boundary` | change where identity is resolved and enforced | security, coupling |

## Domain classes: frontend (React)

| class | the move | typical objective |
|---|---|---|
| `render-scope` | narrow what re-renders (memo, split state, selectors) | dropped frames, jank |
| `state-colocation` | move state up/down or out to a store | prop drilling, stale UI |
| `data-fetching-strategy` | change when/where data is fetched (server, route loader, client) | waterfalls, TTI |
| `cache-invalidation` | change how client cache is keyed/invalidated | stale data, refetch storms |
| `bundle-split` | change what ships in the initial bundle | load time |
| `perceived-latency` | change what the user sees while waiting (skeleton, optimistic UI) | **the requirement, not the speed** |
| `effect-lifecycle` | change effect deps/cleanup | double-fire, leaks, races |

## Domain classes: agents (Python / LLM)

The grind risk is highest here, and the counter only works if these stay
distinct. **`prompt-edit` is one class, not one class per prompt.** Rewording the
system prompt four times is four attempts at the same idea — that is precisely
what the N-refute gate must see.

| class | the move | typical objective |
|---|---|---|
| `prompt-edit` | change wording/structure/examples in a prompt | steer behaviour |
| `context-composition` | change what goes into context and in what order | relevance, distraction |
| `tool-redesign` | change a tool's signature, granularity or description | correct tool choice |
| `control-flow` | change orchestration (loop, router, plan-then-act, multi-agent) | reliability of multi-step work |
| `model-swap` | different model or reasoning-effort tier | capability vs cost |
| `decoding-params` | temperature, sampling, max tokens | consistency |
| `output-contract` | enforce structure (schema, typed output, validators) | parse failures |
| `guardrail-retry` | validate and retry on failure | success rate |
| `memory-strategy` | what persists between turns/sessions and how it is recalled | continuity |
| `eval-harness` | build/extend the measurement itself (not a fix) | **be able to tell better from worse** |

Two notes specific to agent work:

- **`eval-harness` before anything else.** Agent changes are the easiest in all
  of software to fool yourself about: the output reads better, so the change
  worked. Without a scored eval set, every row in this domain is `descriptive`
  by definition, and discipline 1 blocks the build. This is a feature.
- **`prompt-edit` blocking is the point.** When three prompt edits refute, the
  gate forces the question the domain most needs asked: is this a prompting
  problem at all, or is it context, tools, control flow, or the model?

## Note on `observability` and `requirement-change`

These two are the usual exits when a class gets blocked.

`observability` is legitimate as its own approach — "we cannot fix this because
we cannot see it" is a real hypothesis with a real test. It is not a fix, so its
objective must be stated as *what the measurement will decide*, not "add logs".

`requirement-change` is the strongest move available and the most often skipped.
Three refuted classes on "make this page load in 200ms" may mean the page does
not need to load in 200ms — it needs to *appear* to. Rule 7 exists to make you
consider this before the fourth attempt, not after the fortieth.
