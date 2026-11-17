> [!NOTE]
> This is not an officially supported Google product.
>
> Eligibility for the [Google Open Source Software Vulnerability Rewards
> Program](https://bughunters.google.com/open-source-security) is determined by
> the [Google Open Source Software Vulnerability Reward Program
> Rules](https://bughunters.google.com/about/rules/open-source/google-open-source-software-vulnerability-reward-program-rules).

# Bazel Lattice

**Bazel Lattice** is an synthetic monorepo benchmark repository generator
designed to simulate large-scale Bazel configuration graphs, dependency
networks, and build performance dynamics.

## Features & Topology

- **Power-Law (Zipfian) Dependency Graph**: Simulates semi-realistic monorepo
  target distribution with central hub libraries and core proto schemas.
- **Multi-Target Package Density**: 4–6 targets per package (`:lib`,
  `:lib_impl`, `:lib_test`, `filegroup`).
- **Custom Starlark Macros & Aspects**: Features macro rules with `select()`
  configurations (`:opt_build`, `:debug_build`, `:fastbuild_mode`) and Starlark
  propagation aspects (`LatticeInfo`).
- **Transitive Header Inclusions**: Deep multi-tier C++ inclusion cascades
  across generated components.
- **Isolated Build Output**: All generated packages reside under the git-ignored
  `generated/` subfolder.
- **Clean Generator Directives**: Enforces execution refusal if `generated/` is
  non-empty.

## Target Scale Tiers

| Tier Flag | Approximate Targets |
| :--- | :--- |
| `--tier 1` | ~10,000 targets |
| `--tier 2` | ~50,000 targets |
| `--tier 3` | ~100,000 targets |
| `--tier 4` | ~500,000 targets |
| `--tier 5` | ~1,000,000 targets |

## Example Usage

```bash
# Generate Tier 1 benchmark repository (~10k targets)
python3 generate_repo.py --tier 1
```

The generated files can be found under `//generated/bench`.
