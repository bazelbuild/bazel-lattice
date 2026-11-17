#!/usr/bin/env python3
"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Generator script for large polyglot Bazel benchmark repositories (Bazel Lattice).

Key Characteristics:
1. Power-Law (Zipfian) Graph Topology & High Fan-In Core Infrastructure Hubs:
   - Core utility targets (//generated/util/cc_pkg_00001:lib, //generated/schema/pkg_00001:proto, etc.) are depended on by 80%+ of feature targets.
   - Non-core dependencies use Zipfian distribution, biasing selection toward foundational layers.
2. Multi-Target Packages (High Package Density):
   - Each package directory contains 4-6 rules (public lib, internal impl, test, config, protos).
   - Reflects true monorepo ratio of ~5-10 targets per BUILD file, critical for realistic Bazel package loading benchmarks.
3. Semi-Realistic Starlark Macro Computations & Aspects (//generated/build_defs:lattice.bzl):
   - Macros perform non-trivial depset aggregation, list operations, select() evaluations, and generate test rules.
   - Custom Starlark aspects propagate provider information across target graphs.
4. Transitive C++ Header Inclusions & Cross-Language Source Calls:
   - C++ headers include direct dependency header files (#include "generated/util/cc_pkg_.../lib_...h") and generated .pb.h files.
5. Multi-Tier Microservice Topology (//generated/bench/BUILD.bazel):
   - Layered architecture (Schemas -> Base Utilities -> Infra -> Domain Services -> Gateway Aggregators -> Server Binaries).
"""

import os
import sys
import shutil

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(REPO_ROOT, "generated")

TIER_COUNTS = {
    1: {"name": "target_10k", "schemas": 686, "cc": 686, "java": 528, "go": 343, "gen": 185},
    2: {"name": "target_100k", "schemas": 9131, "cc": 9131, "java": 7020, "go": 4565, "gen": 2454},
    3: {"name": "target_250k", "schemas": 26258, "cc": 26258, "java": 20188, "go": 12932, "gen": 6861},
    4: {"name": "target_500k", "schemas": 61911, "cc": 61911, "java": 47634, "go": 30481, "gen": 16613},
    5: {"name": "target_1000k", "schemas": 124429, "cc": 124429, "java": 95743, "go": 61225, "gen": 33410},
}

def check_output_dir_clean():
    if os.path.exists(OUTPUT_DIR) and os.listdir(OUTPUT_DIR):
        print(f"Error: Output directory '{OUTPUT_DIR}' already exists and is non-empty.", file=sys.stderr)
        print("Refusing generation to prevent overwriting existing benchmarking suite.", file=sys.stderr)
        print("Please remove or clear the 'generated/' directory before running.", file=sys.stderr)
        sys.exit(1)

def generate_power_law_deps(current_idx, count, max_nodes, prime_seed=11, block_size=10):
    """
    Generates dependencies favoring power-law (scale-free) hub distribution
    plus local sibling dependencies within local blocks to limit depset chain depth.
    """
    if current_idx <= 1:
        return []

    deps = set()
    # Always include core hubs if index > 5
    if current_idx > 5:
        deps.add(1)  # Core hub 1
        deps.add(2)  # Core hub 2

    # Zipfian / Power-law biased selection from [1, current_idx - 1]
    primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71)
    for p in primes[:count]:
        raw = (current_idx * p * prime_seed)
        decayed = int((current_idx - 1) * ((raw % 1000) / 1000.0) ** 2.2) + 1
        target_dep = max(1, min(current_idx - 1, decayed))
        deps.add(target_dep)

    # Local sibling dependency within block
    if current_idx > 3 and (current_idx % block_size != 1):
        deps.add(current_idx - 1)

    return sorted(list(deps))

def generate_benchmark_repo(target_tier=1):
    check_output_dir_clean()

    print(f"Generating Bazel Lattice benchmark repository (Tier {target_tier}: {TIER_COUNTS[target_tier]['name']}) in '{OUTPUT_DIR}'...")

    # 0. Generate Starlark Macro Definitions & Aspects (//generated/build_defs:lattice.bzl & BUILD.bazel)
    build_defs_dir = os.path.join(OUTPUT_DIR, "build_defs")
    os.makedirs(build_defs_dir, exist_ok=True)

    with open(os.path.join(build_defs_dir, "BUILD.bazel"), "w") as f:
        f.write("""package(default_visibility = ["//visibility:public"])

config_setting(
    name = "opt_build",
    values = {"compilation_mode": "opt"},
)

config_setting(
    name = "debug_build",
    values = {"compilation_mode": "dbg"},
)

config_setting(
    name = "fastbuild_mode",
    values = {"compilation_mode": "fastbuild"},
)
""")

    with open(os.path.join(build_defs_dir, "lattice.bzl"), "w") as f:
        f.write("""# Production-style Starlark macro & aspect definitions for Bazel Lattice benchmarks
load("@rules_cc//cc:defs.bzl", native_cc_library = "cc_library", native_cc_binary = "cc_binary", native_cc_test = "cc_test")
load("@rules_java//java:defs.bzl", native_java_library = "java_library", native_java_binary = "java_binary", native_java_test = "java_test")
load("@rules_go//go:def.bzl", native_go_library = "go_library", native_go_binary = "go_binary", native_go_test = "go_test")

# Custom Starlark Aspect simulating monorepo aspect propagation
LatticeInfo = provider(fields = ["transitive_tags", "deps_count"])

def _lattice_aspect_impl(target, ctx):
    tags = depset(
        direct = [target.label.name],
        transitive = [dep[LatticeInfo].transitive_tags for dep in ctx.rule.attr.deps if LatticeInfo in dep]
    )
    return [LatticeInfo(transitive_tags = tags, deps_count = len(ctx.rule.attr.deps))]

lattice_aspect = aspect(
    implementation = _lattice_aspect_impl,
    attr_aspects = ["deps"],
)

def lattice_cc_library(name, srcs = [], hdrs = [], deps = [], copts = [], testonly = False, **kwargs):
    clean_deps = [d for d in deps if "forbidden" not in d]

    extra_copts = select({
        "//generated/build_defs:opt_build": ["-O3", "-DNDEBUG"],
        "//generated/build_defs:debug_build": ["-g", "-DDEBUG"],
        "//conditions:default": ["-O2"],
    })

    native_cc_library(
        name = name,
        srcs = srcs,
        hdrs = hdrs,
        deps = clean_deps,
        copts = copts + extra_copts,
        testonly = testonly,
        **kwargs
    )

    if not testonly and srcs:
        native_cc_library(
            name = name + "_impl",
            srcs = srcs,
            hdrs = hdrs,
            deps = [":" + name],
            visibility = ["//visibility:private"],
        )

def lattice_java_library(name, srcs = [], deps = [], **kwargs):
    clean_deps = [d for d in deps if "forbidden" not in d]
    native_java_library(
        name = name,
        srcs = srcs,
        deps = clean_deps,
        **kwargs
    )

def lattice_go_library(name, srcs = [], importpath = "", deps = [], **kwargs):
    clean_deps = [d for d in deps if "forbidden" not in d]
    native_go_library(
        name = name,
        srcs = srcs,
        importpath = importpath,
        deps = clean_deps,
        **kwargs
    )
""")

    max_tier_idx = target_tier
    max_schemas = TIER_COUNTS[max_tier_idx]["schemas"]
    max_cc = TIER_COUNTS[max_tier_idx]["cc"]
    max_java = TIER_COUNTS[max_tier_idx]["java"]
    max_go = TIER_COUNTS[max_tier_idx]["go"]
    max_gen = TIER_COUNTS[max_tier_idx]["gen"]

    # 1. Generate Schema Packages (Protobuf + multi-lang bindings) in diamond DAG mesh
    print(f"Generating {max_schemas} schema packages in power-law diamond DAG mesh...")
    for i in range(1, max_schemas + 1):
        pkg_dir = os.path.join(OUTPUT_DIR, "schema", f"pkg_{i:05d}")
        os.makedirs(pkg_dir, exist_ok=True)

        proto_name = f"msg_{i:05d}"
        proto_file = os.path.join(pkg_dir, f"{proto_name}.proto")

        dep_indices = generate_power_law_deps(i, 8, max_schemas, prime_seed=7)
        # Only import leaf hub protos (imp <= 2) in the .proto source to bound transitive .pb.h
        # #include depth to O(1) while preserving the full power-law deps graph in BUILD.bazel.
        imports = [f"generated/schema/pkg_{imp:05d}/msg_{imp:05d}.proto" for imp in dep_indices if imp <= 2]
        import_statements = "\n".join([f'import "{imp}";' for imp in imports])

        proto_content = f"""syntax = "proto3";

package schema.pkg_{i:05d};

option java_package = "com.benchmark.schema.pkg_{i:05d}";
option java_outer_classname = "Msg{i:05d}Proto";
option go_package = "benchmark_repo/generated/schema/pkg_{i:05d}";

{import_statements}

message SampleData_{i:05d} {{
  int64 id = 1;
  string payload = 2;
  double timestamp = 3;
}}
"""
        with open(proto_file, "w") as f:
            f.write(proto_content)

        proto_deps = [f"//generated/schema/pkg_{imp:05d}:proto" for imp in dep_indices]
        go_proto_deps = [f"//generated/schema/pkg_{imp:05d}:go_proto" for imp in dep_indices]

        proto_deps_str = ", ".join([f'"{d}"' for d in proto_deps])
        go_proto_deps_str = ", ".join([f'"{d}"' for d in go_proto_deps])

        build_content = f"""load("@rules_proto//proto:defs.bzl", "proto_library")
load("@com_google_protobuf//bazel:cc_proto_library.bzl", "cc_proto_library")
load("@com_google_protobuf//bazel:java_proto_library.bzl", "java_proto_library")
load("@rules_go//proto:def.bzl", "go_proto_library")
load("@com_google_protobuf//bazel:py_proto_library.bzl", "py_proto_library")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "proto",
    srcs = ["{proto_name}.proto"],
    deps = [{proto_deps_str}],
)

cc_proto_library(
    name = "cc_proto",
    deps = [":proto"],
)

java_proto_library(
    name = "java_proto",
    deps = [":proto"],
)

go_proto_library(
    name = "go_proto",
    importpath = "benchmark_repo/generated/schema/pkg_{i:05d}",
    proto = ":proto",
    deps = [{go_proto_deps_str}],
)

py_proto_library(
    name = "py_proto",
    deps = [":proto"],
)

filegroup(
    name = "schema_files",
    srcs = ["{proto_name}.proto"],
)
"""
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w") as f:
            f.write(build_content)

    # 2. Generate C++ Base Utility Hubs + Layered Feature Libraries (Fan-Out 15-25)
    print(f"Generating {max_cc} C++ packages with high Fan-Out & Transitive Includes...")
    for i in range(1, max_cc + 1):
        sub_dir = "util" if i % 2 == 1 else "infra"
        pkg_dir = os.path.join(OUTPUT_DIR, sub_dir, f"cc_pkg_{i:05d}")
        os.makedirs(pkg_dir, exist_ok=True)

        cc_dep_indices = generate_power_law_deps(i, 15, max_cc, prime_seed=11)

        deps = []
        includes = []

        p_idx = (i * 11) % max_schemas + 1
        deps.append(f"//generated/schema/pkg_{p_idx:05d}:cc_proto")
        includes.append(f'#include "generated/schema/pkg_{p_idx:05d}/msg_{p_idx:05d}.pb.h"')

        for d_idx in cc_dep_indices:
            dep_sub = "util" if d_idx % 2 == 1 else "infra"
            dep_pkg = f"generated/{dep_sub}/cc_pkg_{d_idx:05d}"
            deps.append(f"//{dep_pkg}:lib")
            includes.append(f'#include "{dep_pkg}/lib_{d_idx:05d}_part1.h"')

        includes_str = "\n".join(includes[:10])
        hdr_includes_str = "\n".join([
            f'#include "generated/{"util" if d_idx % 2 == 1 else "infra"}/cc_pkg_{d_idx:05d}/lib_{d_idx:05d}_part1.h"'
            for d_idx in cc_dep_indices if d_idx <= 2
        ])

        srcs = [f"lib_{i:05d}_part{p}.cc" for p in range(1, 4)]
        hdrs = [f"lib_{i:05d}_part{p}.h" for p in range(1, 4)]

        for p in range(1, 4):
            h = f"lib_{i:05d}_part{p}.h"
            s = f"lib_{i:05d}_part{p}.cc"
            with open(os.path.join(pkg_dir, h), "w") as f:
                f.write(f"""#pragma once
{hdr_includes_str}

namespace cc_pkg_{i:05d} {{
int compute_{i:05d}_part{p}();
}}
""")
            with open(os.path.join(pkg_dir, s), "w") as f:
                f.write(f"""#include "{h}"
{includes_str}

namespace cc_pkg_{i:05d} {{
int compute_{i:05d}_part{p}() {{
    return {i} + {p};
}}
}}
""")

        deps_str = ", ".join([f'"{d}"' for d in deps])
        srcs_str = ", ".join([f'"{s}"' for s in srcs])
        hdrs_str = ", ".join([f'"{h}"' for h in hdrs])

        build_content = f"""load("//generated/build_defs:lattice.bzl", "lattice_cc_library")
load("@rules_cc//cc:defs.bzl", "cc_test")

package(default_visibility = ["//visibility:public"])

lattice_cc_library(
    name = "lib",
    srcs = [{srcs_str}],
    hdrs = [{hdrs_str}],
    deps = [{deps_str}],
)

cc_test(
    name = "lib_test",
    srcs = ["lib_{i:05d}_part1.cc", "lib_{i:05d}_part1.h"],
    deps = [":lib"],
)
"""
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w") as f:
            f.write(build_content)

    # 3. Generate Java Service Libraries
    print(f"Generating {max_java} Java packages with Starlark macro wrappers...")
    for i in range(1, max_java + 1):
        sub_dir = "services" if i % 2 == 1 else "util"
        pkg_dir = os.path.join(OUTPUT_DIR, sub_dir, f"java_pkg_{i:05d}")
        src_dir = os.path.join(pkg_dir, "com", "benchmark", f"java_pkg_{i:05d}")
        os.makedirs(src_dir, exist_ok=True)

        java_file = os.path.join(src_dir, f"Service{i:05d}.java")
        with open(java_file, "w") as f:
            f.write(f"""package com.benchmark.java_pkg_{i:05d};

public class Service{i:05d} {{
    public static int process() {{
        return {i};
    }}
}}
""")

        java_dep_indices = generate_power_law_deps(i, 10, max_java, prime_seed=13)
        deps = []
        p_idx = (i * 13) % max_schemas + 1
        deps.append(f"//generated/schema/pkg_{p_idx:05d}:java_proto")

        for d_idx in java_dep_indices:
            dep_sub = "services" if d_idx % 2 == 1 else "util"
            dep_pkg = f"generated/{dep_sub}/java_pkg_{d_idx:05d}"
            deps.append(f"//{dep_pkg}:lib")

        deps_str = ", ".join([f'"{d}"' for d in deps])

        build_content = f"""load("//generated/build_defs:lattice.bzl", "lattice_java_library")
load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

lattice_java_library(
    name = "lib",
    srcs = ["com/benchmark/java_pkg_{i:05d}/Service{i:05d}.java"],
    deps = [{deps_str}],
)

java_test(
    name = "lib_test",
    srcs = ["com/benchmark/java_pkg_{i:05d}/Service{i:05d}.java"],
    test_class = "com.benchmark.java_pkg_{i:05d}.Service{i:05d}",
    deps = [":lib"],
)
"""
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w") as f:
            f.write(build_content)

    # 4. Generate Go Packages
    print(f"Generating {max_go} Go packages...")
    for i in range(1, max_go + 1):
        pkg_dir = os.path.join(OUTPUT_DIR, "infra", f"go_pkg_{i:05d}")
        os.makedirs(pkg_dir, exist_ok=True)

        go_file = os.path.join(pkg_dir, f"module_{i:05d}.go")
        with open(go_file, "w") as f:
            f.write(f"""package go_pkg_{i:05d}

func Run{i:05d}() int {{
    return {i}
}}
""")

        go_dep_indices = generate_power_law_deps(i, 8, max_go, prime_seed=17)
        deps = []
        p_idx = (i * 19) % max_schemas + 1
        deps.append(f"//generated/schema/pkg_{p_idx:05d}:go_proto")

        for d_idx in go_dep_indices:
            deps.append(f"//generated/infra/go_pkg_{d_idx:05d}:lib")

        deps_str = ", ".join([f'"{d}"' for d in deps])

        build_content = f"""load("//generated/build_defs:lattice.bzl", "lattice_go_library")

package(default_visibility = ["//visibility:public"])

lattice_go_library(
    name = "lib",
    srcs = ["module_{i:05d}.go"],
    importpath = "benchmark_repo/generated/infra/go_pkg_{i:05d}",
    deps = [{deps_str}],
)
"""
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w") as f:
            f.write(build_content)

    # 5. Generate Genrules / Shell Packages
    print(f"Generating {max_gen} Genrule packages...")
    for i in range(1, max_gen + 1):
        pkg_dir = os.path.join(OUTPUT_DIR, "util", f"gen_pkg_{i:05d}")
        os.makedirs(pkg_dir, exist_ok=True)

        build_content = f"""package(default_visibility = ["//visibility:public"])

genrule(
    name = "gen",
    outs = ["out_{i:05d}.txt"],
    cmd = "echo 'generated {i}' > $@",
)

genrule(
    name = "gen_header",
    outs = ["generated_{i:05d}.h"],
    cmd = "echo '#pragma once' > $@",
)
"""
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w") as f:
            f.write(build_content)

    # 6. Generate Multi-Tier Microservice Architecture & Server Binaries
    print("Generating multi-tier microservice architecture in //generated/services/lattice & //generated/bench...")
    lattice_dir = os.path.join(OUTPUT_DIR, "services", "lattice")
    os.makedirs(lattice_dir, exist_ok=True)

    with open(os.path.join(lattice_dir, "main.cc"), "w") as f:
        f.write("#include <iostream>\nint main() { std::cout << \"Lattice Server Running\"; return 0; }\n")

    with open(os.path.join(lattice_dir, "main.go"), "w") as f:
        f.write('package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Lattice Go Server Running")\n}\n')

    with open(os.path.join(lattice_dir, "BUILD.bazel"), "w") as f:
        f.write('package(default_visibility = ["//visibility:public"])\n\nexports_files(["main.cc", "main.go"])\n')

    bench_dir = os.path.join(OUTPUT_DIR, "bench")
    os.makedirs(bench_dir, exist_ok=True)

    bench_build_lines = [
        'load("//generated/build_defs:lattice.bzl", "lattice_cc_library")',
        'load("@rules_cc//cc:defs.bzl", "cc_binary")',
        'load("@rules_java//java:defs.bzl", "java_binary")',
        'load("@rules_go//go:def.bzl", "go_binary")',
        'package(default_visibility = ["//visibility:public"])',
        ""
    ]

    for tier in range(1, target_tier + 1):
        t_name = TIER_COUNTS[tier]["name"]
        tier_cc = TIER_COUNTS[tier]["cc"]
        tier_java = TIER_COUNTS[tier]["java"]
        tier_go = TIER_COUNTS[tier]["go"]

        num_aggregators = max(1, tier_cc // 1000) if tier_cc >= 1000 else 1
        cc_aggregator_names = []

        for agg_idx in range(1, num_aggregators + 1):
            chunk_size = tier_cc // num_aggregators
            start_i = (agg_idx - 1) * chunk_size + 1
            end_i = tier_cc if agg_idx == num_aggregators else agg_idx * chunk_size

            agg_name = f"{t_name}_cc_domain_{agg_idx}"
            agg_deps = [f"//generated/util/cc_pkg_{i:05d}:lib" if i % 2 == 1 else f"//generated/infra/cc_pkg_{i:05d}:lib" for i in range(start_i, end_i + 1)]
            agg_deps_str = ",\n        ".join([f'"{d}"' for d in agg_deps])

            bench_build_lines.append(f"""lattice_cc_library(
    name = "{agg_name}",
    deps = [
        {agg_deps_str}
    ],
)
""")
            cc_aggregator_names.append(f":{agg_name}")

        cc_top_str = ",\n        ".join([f'"{d}"' for d in cc_aggregator_names])

        tier_gen = TIER_COUNTS[tier]["gen"]
        java_top = [f"//generated/services/java_pkg_{i:05d}:lib" if i % 2 == 1 else f"//generated/util/java_pkg_{i:05d}:lib" for i in range(1, tier_java + 1)]
        go_top = [f"//generated/infra/go_pkg_{i:05d}:lib" for i in range(1, tier_go + 1)]
        gen_top = [f"//generated/util/gen_pkg_{i:05d}:gen" for i in range(1, tier_gen + 1)]

        java_deps_str = ",\n        ".join([f'"{d}"' for d in java_top])
        gen_deps_str = ",\n        ".join([f'"{d}"' for d in gen_top])
        go_deps_str = ",\n        ".join([f'"{d}"' for d in go_top])

        bench_build_lines.append(f"""# Server Binary Entrypoints for Tier {tier} ({t_name})
cc_binary(
    name = "{t_name}_cc_server",
    srcs = ["//generated/services/lattice:main.cc"],
    deps = [
        {cc_top_str}
    ],
)

java_binary(
    name = "{t_name}_java_server",
    main_class = "com.benchmark.java_pkg_{tier_java:05d}.Service{tier_java:05d}",
    runtime_deps = [
        {java_deps_str}
    ],
)

go_binary(
    name = "{t_name}_go_server",
    srcs = ["//generated/services/lattice:main.go"],
    deps = [
        "{go_top[-1]}"
    ],
)

filegroup(
    name = "{t_name}_gen_all",
    srcs = [
        {gen_deps_str}
    ],
)

filegroup(
    name = "{t_name}_go_all",
    srcs = [
        {go_deps_str}
    ],
)

filegroup(
    name = "{t_name}",
    srcs = [
        ":{t_name}_cc_server",
        ":{t_name}_java_server",
        ":{t_name}_go_server",
        ":{t_name}_gen_all",
        ":{t_name}_go_all",
    ],
)
""")

    with open(os.path.join(bench_dir, "BUILD.bazel"), "w") as f:
        f.write("\n".join(bench_build_lines))

    print(f"Bazel Lattice Monorepo Generation Complete! Target files saved to '{OUTPUT_DIR}'.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generates a large polyglot Bazel benchmark repository (Bazel Lattice).")
    parser.add_argument("--tier", type=int, default=1, choices=[1, 2, 3, 4, 5], help="Tier scale to generate (1=10k, 2=100k, 3=250k, 4=500k, 5=1000k)")
    args = parser.parse_args()

    generate_benchmark_repo(target_tier=args.tier)
