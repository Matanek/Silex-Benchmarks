# Six-family final qualification

The public consumer `ModelQualification.sx` compares five complete MSE/AdamW
steps per model using the six ResidentSteps fixtures, seeds 481/482 and asymmetric
inputs. Epsilon 0.01 and absolute CPU tolerance 2e-5 are fixed before execution.
Two initial eager steps precede preparation; three hot steps use prepared forward
or TrainingStep on MLP, and explicit eager after state-preserving rejection on
CNN, SimpleRNN, GRU, LSTM and Transformer. A repeated GPU eager run checks
bit-exact determinism. Every step compares output/loss before update, all weights,
gradients, moments, counters, names, shapes, trainability, training mode and
optimizer hyperparameters. GPU arms agree exactly; CPU is independently evolved.
All GPU buffers, active/cached/allocated bytes return to zero after each arm.

The diagnostic control changes only the GPU LayerNorm shifted-sqrt branch back
to add then sqrt. The original bytes are restored in finally and all Tensor
module fingerprints are checked. Complete eager states remain identical;
Transformer uses 1278 passes/1290 submissions instead of 1284/1296 for three hot
steps. The other five families retain identical counts. MLP keeps 252 passes:
eager 252 submissions, prepared forward 240, TrainingStep 57.

Debug and Release agree exactly on 119420 printed scalar observations. The
unchanged cross-entropy ResidentSteps witness also passes both modes with its
original epsilon 1e-4 and absolute/relative2e-5 tolerance. The prior 470-test/112-source
and six-target composition proofs are reusable because every Tensor module/test
fingerprint remains unchanged. Host runtime evidence is macOS arm64/Metal only;
six target composition is a separate proof. No new timing or performance gain
is inferred from this final correctness and command-count confrontation.

Run `python3 Verify.py` to recompute comparisons, expected counts, independent
CPU checks and sealed source/proof hashes without requiring GPU hardware.
Source baselines identify the prior repository commits; source snapshots pin the
new consumer and unchanged modules exactly. The enclosing benchmark commit owns
this complete source-and-evidence slice.
