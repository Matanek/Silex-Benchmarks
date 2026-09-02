# Rejected semantic-function cache

This capture measures Silex commit `74e7794c2af6f80cd32cb823fbbc78e35742b163`.
That candidate stored one private binary artifact for the current package graph
and relocated reusable typed functions into a different entry.

The candidate was rejected and reverted by Silex commit
`244f9aecf5a6630c7d790041dbcae19c131ee00e`. It reused a median of 744 package
functions in both cached profiles, with about 4 ms spent reading the artifact
and less than 1 ms relocating functions, but it did not avoid the dominant
global semantic preparation. Compared with the Part 03 capture, median wall
time changed from 1.33 s to 1.37 s for `shared_packages` and from 1.33 s to
1.38 s for `entry_modified`.

The experiment is retained as negative evidence for choosing a coarser package
interface or fragment boundary. Its cache representation is not present in the
current compiler.
