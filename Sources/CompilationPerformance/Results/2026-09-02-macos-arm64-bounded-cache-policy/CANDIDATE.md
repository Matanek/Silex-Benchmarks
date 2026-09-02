# Bounded cache policy candidate

This capture measures the net Part 04 compiler candidate at Silex commit
`244f9aecf5a6630c7d790041dbcae19c131ee00e`. The later documentation-only
commit does not change the measured binary.

The campaign deliberately creates several distinct 35 MiB linked outputs in
one compiler session. Their combined current working set reaches 336.2 MiB,
which is larger than the 320 MiB rolling history reserve. All current artifacts
remain admitted: the reserve is not a compilation quota. Unit stress coverage
separately proves that a later small working set evicts this historical peak.

The cache policy itself does not improve a frontend miss. Median
`shared_packages` and `entry_modified` times remain 1.44 s and 1.38 s, while an
exact hit remains 0.01 s. The rejected semantic-function experiment in the
neighboring result directory explains why the first attempted package
representation was not retained.
