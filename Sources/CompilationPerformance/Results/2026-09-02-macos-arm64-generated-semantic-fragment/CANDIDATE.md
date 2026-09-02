# Generated package semantic fragment candidate

This capture evaluates Silex
`33d21d703b0ac6c4fe73a71d4a951874de87f4b2` against the accepted bounded-cache
capture on the same corpus and package commits.

The package fragment is private, binary, and stored in the one disposable root
cache. It contains only generated semantic functions with stable package-source
identities and relocatable references. Source functions, project extensions,
entry-dependent specializations, and ambiguous references remain misses. Each
run replaces the fragment with the current package working set; it does not
merge an unbounded history of entries.

The shared-package median falls from `1.44 s` to `1.13 s` (`-21.53%`) and the
entry-modified median from `1.38 s` to `1.09 s` (`-21.01%`). Cold compilation
remains `1.40 s` without tracing and `1.41 s` with tracing, while the exact hit
remains `0.01 s`.

On both incremental profiles the median semantic phase is about `128 ms`, down
from about `449 ms` on the no-cache profile. The fragment reuses `1,734`
generated functions, misses `52`, and stores `1,749`; `15` ambiguous
relocations fall back safely. Median cache work is about `10 ms` to read,
`2.3 ms` to relocate, and `10.8 ms` to replace the current fragment, with about
`7.4 MB` read and written.

The maximum one-root cache is `342.8 MiB`. This is above the `320 MiB` rolling
history reserve because the complete current working set is admitted, as
required; it does not establish a new fixed quota or a cumulative package
cache.

`GFX` and `GFX.Application` had unrelated uncommitted changes in their shared
checkouts when this capture was made. The campaign therefore used temporary
clean local clones at their recorded HEADs. All other packages were linked
read-only from their clean checkouts. The runner records every package as clean,
and its comparison gate accepts this capture against the bounded-cache baseline.

This candidate is a measurable partial gain, not completion of Part 04: the
Spec target requires the two incremental profiles to be at least twice as fast
as a full miss. The remaining work is dominated by source-function analysis,
entry-dependent specializations, lowering, and linking rather than package
semantic preparation.
