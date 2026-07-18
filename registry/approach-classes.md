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

## Note on `observability` and `requirement-change`

These two are the usual exits when a class gets blocked.

`observability` is legitimate as its own approach — "we cannot fix this because
we cannot see it" is a real hypothesis with a real test. It is not a fix, so its
objective must be stated as *what the measurement will decide*, not "add logs".

`requirement-change` is the strongest move available and the most often skipped.
Three refuted classes on "make this page load in 200ms" may mean the page does
not need to load in 200ms — it needs to *appear* to. Rule 7 exists to make you
consider this before the fourth attempt, not after the fortieth.
