#!/usr/bin/env python3
"""Resume the continuity experiment using historical result paths.

Importing this module is side-effect free. Executing it intentionally reads and
rewrites the historical JSONL paths as sessions complete.
"""

import json

RESUME_CONDITIONS = ("naked", "compressed", "clamped", "naive")


def main():
    """Run at most ten unfinished historical continuity sessions."""
    # Load existing results before the experiment dependencies so progress is
    # visible promptly when this runner is executed directly.
    existing_results = []
    existing_summaries = []
    with open("results/lpci_rigorous.jsonl") as f:
        for line in f:
            existing_results.append(json.loads(line))
    with open("results/lpci_rigorous_summary.jsonl") as f:
        for line in f:
            existing_summaries.append(json.loads(line))

    done = {
        (summary["topic"], summary["condition"], summary["replication"])
        for summary in existing_summaries
    }
    print(f"Already completed: {len(done)} sessions, {len(existing_results)} rows")

    # Keep heavy experiment imports off the module-import path.
    from continuity_experiment import (
        TOPICS,
        compute_te_from_embeddings,
        run_session,
    )
    import numpy as np

    conditions = RESUME_CONDITIONS
    n_replications = 5
    total_sessions = len(TOPICS) * len(conditions) * n_replications

    all_results = list(existing_results)
    session_summaries = list(existing_summaries)

    ran = 0
    max_new = 10

    for topic_name, topic_data in TOPICS.items():
        for condition in conditions:
            for rep in range(1, n_replications + 1):
                if (topic_name, condition, rep) in done:
                    continue
                if ran >= max_new:
                    break

                ran += 1
                print(
                    f"\n--- Resume {ran}/{max_new}: "
                    f"{topic_name} | {condition} | rep {rep} ---"
                )

                try:
                    results = run_session(
                        topic_name=topic_name,
                        topic_data=topic_data,
                        condition=condition,
                        replication=rep,
                    )
                    all_results.extend(results)

                    te_result = compute_te_from_embeddings(results)

                    probes = [
                        result
                        for result in results
                        if result["turn_type"].startswith("probe")
                    ]
                    recall_rates = [
                        result.get("probe_recall_rate")
                        for result in probes
                        if "probe_recall_rate" in result
                    ]
                    resistance = [
                        result.get("probe_resistance_score")
                        for result in probes
                        if "probe_resistance_score" in result
                    ]
                    false_claim = [
                        result.get("probe_false_claim_corrected")
                        for result in probes
                        if "probe_false_claim_corrected" in result
                    ]

                    summary = {
                        "topic": topic_name,
                        "condition": condition,
                        "replication": rep,
                        "final_scaffold_tokens": results[-1]["scaffold_tokens"],
                        "mean_recall": (
                            round(
                                np.mean(
                                    [rate for rate in recall_rates if rate is not None]
                                ),
                                3,
                            )
                            if recall_rates
                            else None
                        ),
                        "mean_resistance": (
                            round(
                                np.mean(
                                    [score for score in resistance if score is not None]
                                ),
                                3,
                            )
                            if resistance
                            else None
                        ),
                        "false_claim_caught": false_claim[0] if false_claim else None,
                        **te_result,
                    }
                    session_summaries.append(summary)

                    print(
                        f"  -> historical TE={te_result['te']:.4f} | "
                        "scaffold_drift="
                        f"{te_result.get('mean_scaffold_drift', 0):.3f} | "
                        f"recall={summary.get('mean_recall', '—')}"
                    )

                except Exception as exc:
                    print(f"  ERROR: {exc}")
                    import traceback

                    traceback.print_exc()

                # Preserve the incremental JSONL write pattern of the original
                # runner and the immutable provenance filenames.
                with open("results/lpci_rigorous.jsonl", "w") as f:
                    for result in all_results:
                        row = {
                            key: value
                            for key, value in result.items()
                            if "embedding" not in key
                        }
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")

                with open("results/lpci_rigorous_summary.jsonl", "w") as f:
                    for summary in session_summaries:
                        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

            if ran >= max_new:
                break
        if ran >= max_new:
            break

    print(f"\n{'=' * 70}")
    print(
        f"Done. Ran {ran} new sessions. "
        f"Total: {len(session_summaries)} of {total_sessions} sessions complete."
    )
    print(f"Results: results/lpci_rigorous.jsonl ({len(all_results)} rows)")
    print(
        "Summary: results/lpci_rigorous_summary.jsonl "
        f"({len(session_summaries)} sessions)"
    )


if __name__ == "__main__":
    main()
