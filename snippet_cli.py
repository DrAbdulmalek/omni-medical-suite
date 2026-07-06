#!/usr/bin/env python3
"""
snippet_cli.py — Command Line Interface for OCR Snippet Training
==================================================================
CLI tool for batch processing, review, and training data management.

Usage:
    # Process an image
    python snippet_cli.py process document.jpg

    # Review pending snippets
    python snippet_cli.py review

    # Auto-correct text
    python snippet_cli.py correct "الشثل الدماغي"

    # Show statistics
    python snippet_cli.py stats

    # Export training data
    python snippet_cli.py export training_data.json

    # Batch correct from file
    python snippet_cli.py batch-correct corrections.csv

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import argparse
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict

from ocr_snippet_trainer import OCRSnippetTrainer


def cmd_process(args):
    """Process an image into snippets."""
    trainer = OCRSnippetTrainer()

    image_path = args.image
    method = args.method or "contour"
    engine = args.engine or "auto"

    print(f"Processing: {image_path}")
    print(f"Method: {method} | Engine: {engine}")
    print("-" * 50)

    try:
        snippets = trainer.process_image(image_path, method, engine)

        print(f"\n✅ Created {len(snippets)} snippets:")
        for i, s in enumerate(snippets):
            status = "✓" if s.is_reviewed else "○"
            print(f"  {status} [{i+1}] {s.id}")
            print(f"      OCR:    {s.ocr_text[:60]}...")
            print(f"      Conf:   {s.confidence:.2%} | Engine: {s.engine}")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        trainer.close()

    return 0


def cmd_review(args):
    """Interactive review of pending snippets."""
    trainer = OCRSnippetTrainer()

    snippets = trainer.get_review_queue(limit=args.limit or 50)

    if not snippets:
        print("✅ No pending snippets to review!")
        trainer.close()
        return 0

    print(f"\n📋 {len(snippets)} snippets pending review")
    print("=" * 60)
    print("Commands: [c]orrect | [s]kip | [q]uit | [a]ccept as-is")
    print("=" * 60)

    reviewed = 0
    for snippet in snippets:
        print(f"\n[{reviewed+1}/{len(snippets)}] ID: {snippet.id}")
        print(f"Confidence: {snippet.confidence:.2%} | Engine: {snippet.engine}")
        print(f"OCR Text: {snippet.ocr_text}")

        if snippet.corrected_text != snippet.ocr_text:
            print(f"Auto-corrected: {snippet.corrected_text}")

        # Get suggestions
        suggestions = trainer.learner.get_suggestions(snippet.ocr_text)
        if suggestions:
            print("💡 Suggestions:")
            for s in suggestions[:3]:
                print(f"   '{s['word']}' → '{s['suggestion']}' ({s['confidence']:.0%})")

        # User input
        while True:
            try:
                action = input("\nAction [c/s/q/a]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting...")
                break

            if action == 'q':
                break
            elif action == 's':
                break
            elif action == 'a':
                result = trainer.submit_correction(snippet.id, snippet.ocr_text)
                print(f"✓ Marked as correct")
                reviewed += 1
                break
            elif action == 'c':
                corrected = input("Enter corrected text: ").strip()
                if corrected:
                    result = trainer.submit_correction(snippet.id, corrected)
                    patterns = result.get("patterns_learned", 0)
                    print(f"✓ Saved! Patterns learned: {patterns}")
                    reviewed += 1
                break
            else:
                print("Invalid command. Use: c=correct, s=skip, q=quit, a=accept")

        if action == 'q':
            break

    print(f"\n📊 Reviewed {reviewed} snippets")
    trainer.close()
    return 0


def cmd_correct(args):
    """Auto-correct a text string."""
    trainer = OCRSnippetTrainer()

    text = args.text
    result = trainer.auto_correct(text)

    print(f"Original:  {result['original']}")
    print(f"Corrected: {result['corrected']}")
    print(f"Changes:   {result['correction_count']}")

    if result['corrections']:
        print("\nDetails:")
        for c in result['corrections']:
            print(f"  • {c['type']}: '{c.get('original', c.get('pattern', '?'))}' → '{c.get('corrected', c.get('replacement', '?'))}'")

    trainer.close()
    return 0


def cmd_stats(args):
    """Show database statistics."""
    trainer = OCRSnippetTrainer()
    stats = trainer.get_stats()

    print("\n" + "=" * 50)
    print("📊 OCR Snippet Training Statistics")
    print("=" * 50)
    print(f"Total Snippets:        {stats['total_snippets']}")
    print(f"Reviewed:              {stats['reviewed_snippets']}")
    print(f"Correct (no change):   {stats['correct_snippets']}")
    print(f"Pending Review:        {stats['total_snippets'] - stats['reviewed_snippets']}")
    print(f"Total Patterns:        {stats['total_patterns']}")
    print(f"Auto-promoted:         {stats['promoted_patterns']}")
    print(f"Avg Confidence:        {stats['avg_confidence_after_review']:.1%}")
    print("=" * 50)

    # Show top patterns
    patterns = trainer.learner.db.get_all_patterns(promoted_only=False)
    if patterns:
        print("\n🔝 Top Learned Patterns:")
        for p in patterns[:10]:
            status = "✓" if p.is_auto_promoted else "○"
            print(f"  {status} '{p.original_pattern}' → '{p.corrected_pattern}' "
                  f"({p.frequency}×, {p.confidence_score:.0%})")

    trainer.close()
    return 0


def cmd_export(args):
    """Export training data."""
    trainer = OCRSnippetTrainer()

    output_path = args.output
    fmt = args.format or "json"

    count = trainer.export_training_data(output_path, format=fmt)

    print(f"✅ Exported {count} training examples to {output_path}")
    trainer.close()
    return 0


def cmd_batch_correct(args):
    """Batch apply corrections from a CSV file."""
    trainer = OCRSnippetTrainer()

    csv_path = args.file

    print(f"Reading corrections from: {csv_path}")

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            applied = 0
            for row in reader:
                snippet_id = row.get('snippet_id', row.get('id', ''))
                corrected = row.get('corrected_text', row.get('corrected', ''))

                if snippet_id and corrected:
                    result = trainer.submit_correction(snippet_id, corrected)
                    if result.get("success"):
                        applied += 1
                        print(f"✓ {snippet_id}: {result['patterns_learned']} patterns")

        print(f"\n✅ Applied {applied} corrections")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        trainer.close()

    return 0


def cmd_list(args):
    """List snippets."""
    trainer = OCRSnippetTrainer()

    if args.unreviewed:
        snippets = trainer.get_review_queue(limit=args.limit or 100)
    else:
        # Get all snippets for an image
        if args.image_hash:
            snippets = trainer.db.get_snippets_by_image(args.image_hash)
        else:
            print("Use --image-hash or --unreviewed")
            trainer.close()
            return 1

    print(f"\n📋 {len(snippets)} snippets:")
    print("-" * 80)

    for s in snippets:
        status = "✓" if s.is_reviewed else "○"
        text = s.corrected_text if s.is_reviewed else s.ocr_text
        print(f"{status} {s.id} | {s.confidence:.0%} | {text[:50]}...")

    trainer.close()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="OCR Snippet Training CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python snippet_cli.py process document.jpg
  python snippet_cli.py review --limit 20
  python snippet_cli.py correct "الشثل الدماغي"
  python snippet_cli.py stats
  python snippet_cli.py export training_data.json
  python snippet_cli.py list --unreviewed --limit 10
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # Process
    process_parser = subparsers.add_parser('process', help='Process an image')
    process_parser.add_argument('image', help='Image file path')
    process_parser.add_argument('--method', choices=['contour', 'projection', 'line'],
                                help='Segmentation method')
    process_parser.add_argument('--engine', choices=['auto', 'easyocr', 'tesseract', 'paddleocr'],
                                help='OCR engine')

    # Review
    review_parser = subparsers.add_parser('review', help='Interactive review')
    review_parser.add_argument('--limit', type=int, help='Max snippets to review')

    # Correct
    correct_parser = subparsers.add_parser('correct', help='Auto-correct text')
    correct_parser.add_argument('text', help='Text to correct')

    # Stats
    subparsers.add_parser('stats', help='Show statistics')

    # Export
    export_parser = subparsers.add_parser('export', help='Export training data')
    export_parser.add_argument('output', help='Output file path')
    export_parser.add_argument('--format', choices=['json', 'csv'], default='json')

    # Batch correct
    batch_parser = subparsers.add_parser('batch-correct', help='Batch corrections from CSV')
    batch_parser.add_argument('file', help='CSV file with corrections')

    # List
    list_parser = subparsers.add_parser('list', help='List snippets')
    list_parser.add_argument('--unreviewed', action='store_true', help='Only unreviewed')
    list_parser.add_argument('--image-hash', help='Filter by image hash')
    list_parser.add_argument('--limit', type=int, default=100)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        'process': cmd_process,
        'review': cmd_review,
        'correct': cmd_correct,
        'stats': cmd_stats,
        'export': cmd_export,
        'batch-correct': cmd_batch_correct,
        'list': cmd_list,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
