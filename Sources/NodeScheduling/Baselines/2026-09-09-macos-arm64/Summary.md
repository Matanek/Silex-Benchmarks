# Node scheduling results

All values are milliseconds per measured frame. Median absolute deviation
(MAD) is reported as a percentage of the median.

| Revision | Strategy | Median | Range | MAD |
|---|---:|---:|---:|---:|
| baseline | `nodes_static` | 26.093307 | 25.123070–26.826422 | 2.66% |
| pre-cache | `nodes_static` | 0.002065 | 0.002000–0.002380 | 3.15% |
| candidate | `nodes_static` | 0.002220 | 0.002110–0.002420 | 2.93% |
| baseline | `nodes_processing` | 27.099150 | 26.424284–27.726608 | 1.45% |
| pre-cache | `nodes_processing` | 0.037330 | 0.035335–0.040280 | 4.02% |
| candidate | `nodes_processing` | 0.037995 | 0.036245–0.043980 | 2.47% |
| baseline | `nodes_mixed` | 28.491919 | 25.813955–28.831074 | 1.19% |
| pre-cache | `nodes_mixed` | 0.034985 | 0.033265–0.037420 | 4.29% |
| candidate | `nodes_mixed` | 0.029835 | 0.027795–0.030385 | 1.84% |
| baseline | `nodes_moving` | 28.988466 | 27.365362–29.359960 | 1.28% |
| pre-cache | `nodes_moving` | 32.708520 | 32.442265–33.353443 | 0.80% |
| candidate | `nodes_moving` | 0.322875 | 0.317825–0.336235 | 1.38% |
| candidate | `ecs_static` | 0.000050 | 0.000045–0.000050 | 0.00% |
| candidate | `ecs_moving` | 0.157040 | 0.129290–0.185590 | 2.30% |

Opt-in processing and dirty synchronization reduce the static Node median by
11,754×. One thousand authored callbacks without component mutation cost
0.038 ms/frame, while a scene with ten percent moving Nodes costs
0.030 ms/frame.

The pre-cache revision exposed a class-ownership cliff when every Node changed:
rediscovering the parent object and its ECS transform for every synchronization
raised that path to 32.709 ms/frame. Resolving the spatial parent once at mount
reduces it by 101× to 0.323 ms/frame. The final all-moving object path is 89.8×
faster than the baseline and 2.06× the direct ECS query. Virtual dispatch and
object-to-ECS publication therefore retain a measurable premium, but the
nonlinear ownership cost is no longer part of the steady-state model.
