"""Run all benchmarks and generate reports.

CLI entry point for executing the complete medical OCR benchmark suite
against all available golden datasets.
"""

import os
import sys
import json
from datetime import datetime, timezone

import click

# Ensure the project root is on the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@click.command()
@click.option(
    "--output-dir",
    default="results",
    help="Output directory for reports",
)
@click.option(
    "--format",
    "fmt",
    default="markdown",
    type=click.Choice(["markdown", "json", "html"]),
    help="Report output format",
)
@click.option(
    "--golden-dir",
    default="data/golden",
    help="Golden dataset directory",
)
@click.option(
    "--benchmarks",
    multiple=True,
    default=[],
    help="Specific benchmarks to run (default: all). Can be repeated.",
)
@click.option(
    "--datasets",
    multiple=True,
    default=[],
    help="Specific datasets to use (default: all). Can be repeated.",
)
@click.option(
    "--warmup-runs",
    default=3,
    type=int,
    help="Number of warmup iterations for latency profiling",
)
@click.option(
    "--benchmark-runs",
    default=10,
    type=int,
    help="Number of measured iterations for latency profiling",
)
def main(output_dir, fmt, golden_dir, benchmarks, datasets, warmup_runs, benchmark_runs):
    """Run all benchmarks in the suite.

    Executes OCR, correction, and PHI benchmarks against golden datasets
    and generates a formatted report.
    """
    click.echo(click.style("🏥 Medical OCR Benchmark Suite", fg="cyan", bold=True))
    click.echo(f"   Output directory: {output_dir}")
    click.echo(f"   Report format:     {fmt}")
    click.echo(f"   Golden directory:  {golden_dir}")
    click.echo("")

    # Validate golden directory
    if not os.path.isdir(golden_dir):
        click.echo(click.style(
            f"ERROR: Golden dataset directory not found: {golden_dir}",
            fg="red",
        ))
        sys.exit(1)

    # Discover available datasets
    from benchmarks.datasets.golden import GoldenDataset
    loader = GoldenDataset(dataset_dir=golden_dir)
    available_datasets = loader.list_datasets()

    if not available_datasets:
        click.echo(click.style(
            "ERROR: No golden datasets found in golden directory.",
            fg="red",
        ))
        sys.exit(1)

    # Filter datasets if --datasets specified
    if datasets:
        target_datasets = [d for d in datasets if d in available_datasets]
        missing = set(datasets) - set(available_datasets)
        if missing:
            click.echo(click.style(
                f"WARNING: Unknown datasets skipped: {', '.join(sorted(missing))}",
                fg="yellow",
            ))
    else:
        target_datasets = available_datasets

    click.echo(f"   Datasets:          {', '.join(target_datasets)}")
    click.echo("")

    # Initialize benchmark runner
    from benchmarks.core.runner import BenchmarkRunner
    from benchmarks.core.reporter import BenchmarkReporter

    config = {
        "golden_dir": golden_dir,
        "output_dir": output_dir,
        "warmup_runs": warmup_runs,
        "benchmark_runs": benchmark_runs,
    }

    # Save temporary config
    config_path = os.path.join(output_dir, "benchmark_config.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    runner = BenchmarkRunner(config_path=config_path)

    # Run benchmarks
    if benchmarks:
        all_results = []
        for bench_name in benchmarks:
            for dataset_name in target_datasets:
                click.echo(f"   Running: {bench_name} on {dataset_name}...", nl=False)
                try:
                    result = runner.run_single(bench_name, dataset_name)
                    all_results.append(result)
                    status = result.get("metrics", {}).get("status", "success")
                    if status == "error" or "error" in result.get("metrics", {}):
                        click.echo(click.style(" ❌", fg="red"))
                    else:
                        click.echo(click.style(" ✅", fg="green"))
                except (ValueError, ImportError, FileNotFoundError) as exc:
                    click.echo(click.style(f" ❌ {exc}", fg="red"))
                    all_results.append({
                        "benchmark_name": bench_name,
                        "dataset": dataset_name,
                        "metrics": {"error": str(exc)},
                        "metadata": {},
                    })

        summary = runner._suite.summary()
    else:
        click.echo("   Running all benchmarks...", nl=False)
        all_results = []
        for dataset_name in target_datasets:
            for bench_name in sorted(runner.benchmarks.keys()):
                click.echo("")
                click.echo(f"   → {bench_name} on {dataset_name}...", nl=False)
                try:
                    result = runner.run_single(bench_name, dataset_name)
                    all_results.append(result)
                    status = result.get("metrics", {}).get("status", "success")
                    if status == "error" or "error" in result.get("metrics", {}):
                        click.echo(click.style(" ❌", fg="red"))
                    else:
                        click.echo(click.style(" ✅", fg="green"))
                except (ValueError, ImportError, FileNotFoundError) as exc:
                    click.echo(click.style(f" ❌ {exc}", fg="red"))
                    all_results.append({
                        "benchmark_name": bench_name,
                        "dataset": dataset_name,
                        "metrics": {"error": str(exc)},
                        "metadata": {},
                    })

        summary = runner._suite.summary()

    click.echo("")

    # Compose final results
    final_results = {
        "suite_name": "medical-ocr-benchmark-suite",
        "config": config,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "results": all_results,
        "summary": summary,
    }

    # Generate report
    reporter = BenchmarkReporter(final_results)
    output_path = os.path.join(output_dir, "benchmark_report")

    saved_path = reporter.save(output_path, format=fmt)

    click.echo(click.style("📊 Report generated:", fg="cyan", bold=True))
    click.echo(f"   Location: {saved_path}")
    click.echo("")

    # Print quick summary
    metrics_summary = summary.get("metrics_summary", {})
    if metrics_summary:
        click.echo(click.style("📈 Quick Summary:", fg="cyan", bold=True))
        for metric_name, stats in sorted(metrics_summary.items()):
            if isinstance(stats, dict) and "mean" in stats:
                click.echo(
                    f"   {metric_name}: mean={stats['mean']}, "
                    f"median={stats['median']}, stdev={stats['stdev']}"
                )
        click.echo("")

    click.echo(click.style("Done!", fg="green", bold=True))


if __name__ == "__main__":
    main()
