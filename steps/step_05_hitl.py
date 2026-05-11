#!/usr/bin/env python
"""
Step 5: Human-in-the-loop component labeling
Interactively label PCA components using Ollama and manual review
"""

import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import ollama

# Constants
ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"

PROMPT_TEMPLATE = """These votes load positively on a latent dimension in Congressional voting behavior:
{positive}

These votes load negatively on the same dimension:
{negative}

In one short phrase, what interest or value distinction might this dimension represent?
Be specific about whose interests are on each side. Do not use party labels.
Respond with only the candidate phrase, no explanation."""


def load_component_labels():
    """Load component labels from output/component_labels.json"""
    labels_path = OUTPUT_DIR / "component_labels.json"
    if not labels_path.exists():
        print(f"Error: {labels_path} not found")
        sys.exit(1)
    with open(labels_path, 'r') as f:
        return json.load(f)


def load_loadings(chamber):
    """Load loadings CSV for a given chamber"""
    loadings_path = OUTPUT_DIR / f"loadings_{chamber}.csv"
    if not loadings_path.exists():
        print(f"Error: {loadings_path} not found")
        sys.exit(1)
    return pd.read_csv(loadings_path)


def get_top_votes(loadings_df, component_idx, direction, top_n=10):
    """
    Get top N votes for a component in a given direction.
    Returns list of formatted strings: "[category] question"
    """
    if direction == 'pos':
        filtered = loadings_df[
            (loadings_df['component_idx'] == component_idx) &
            (loadings_df['direction'] == 'pos')
        ].sort_values('loading', ascending=False).head(top_n)
    else:  # 'neg'
        filtered = loadings_df[
            (loadings_df['component_idx'] == component_idx) &
            (loadings_df['direction'] == 'neg')
        ].sort_values('loading', ascending=True).head(top_n)

    formatted = []
    for idx, row in filtered.iterrows():
        formatted.append(f"[{row['category']}] {row['question']}")
    return formatted


def get_candidate_label(positive_descriptions, negative_descriptions):
    """Call Ollama to generate candidate label"""
    try:
        response = ollama.generate(
            model='llama3:8b',
            prompt=PROMPT_TEMPLATE.format(
                positive='\n'.join(positive_descriptions),
                negative='\n'.join(negative_descriptions)
            )
        )
        candidate = response['response'].strip()
        return candidate
    except Exception as e:
        print(f"Ollama unavailable ({e}). Enter label manually.")
        return ""


def prompt_human(component_idx, candidate):
    """Prompt human for label confirmation or override"""
    if candidate:
        print(f"\nCandidate label: {candidate}")
    user_input = input("Accept [Enter], type new label, or type 'skip' to mark uninterpreted: ").strip()

    if user_input == '':
        label = candidate if candidate else f"uninterpreted-{component_idx}"
    elif user_input.lower() == 'skip':
        label = f"uninterpreted-{component_idx}"
    else:
        label = user_input

    return label


def save_labels(labels_json):
    """Save updated labels to output/component_labels.json and log to methodology"""
    labels_path = OUTPUT_DIR / "component_labels.json"

    # Remove automated and warning keys
    labels_json.pop('automated', None)
    labels_json.pop('warning', None)

    # Add review metadata
    labels_json['human_reviewed'] = True
    labels_json['reviewed_at'] = datetime.now().isoformat()

    # Write updated labels
    with open(labels_path, 'w') as f:
        json.dump(labels_json, f, indent=2)

    # Append to methodology log
    log_path = OUTPUT_DIR / "methodology_log.md"
    with open(log_path, 'a') as f:
        f.write("\n## Step 5: Human-in-the-loop Component Labeling\n\n")
        f.write(f"**Reviewed at**: {datetime.now().isoformat()}\n\n")
        f.write("**Confirmed component labels**:\n\n")

        for chamber in ['house', 'senate']:
            if chamber in labels_json and isinstance(labels_json[chamber], dict):
                f.write(f"### {chamber.capitalize()}\n\n")
                for component_idx, label in sorted(labels_json[chamber].items()):
                    # Skip metadata keys
                    if component_idx not in ['human_reviewed', 'reviewed_at']:
                        f.write(f"- Component {component_idx}: {label}\n")
                f.write("\n")


def main():
    print("\n" + "="*60)
    print("STEP 5: HUMAN-IN-THE-LOOP COMPONENT LABELING")
    print("="*60)

    # Load data
    labels_json = load_component_labels()

    # Process each chamber
    for chamber in ['house', 'senate']:
        print(f"\n{'='*60}")
        print(f"CHAMBER: {chamber.upper()}")
        print("="*60)

        if chamber not in labels_json:
            print(f"No components found for {chamber}")
            continue

        loadings_df = load_loadings(chamber)

        # Process each component
        for component_idx_str in sorted(labels_json[chamber].keys()):
            # Skip metadata keys
            if component_idx_str in ['human_reviewed', 'reviewed_at']:
                continue

            try:
                component_idx = int(component_idx_str)
            except ValueError:
                continue

            print(f"\n--- Component {component_idx} ---")

            # Get top positive and negative loading votes
            positive_votes = get_top_votes(loadings_df, component_idx, 'pos', top_n=10)
            negative_votes = get_top_votes(loadings_df, component_idx, 'neg', top_n=10)

            # Print top votes
            print("TOP POSITIVE LOADING VOTES:")
            for n, vote in enumerate(positive_votes, 1):
                print(f"  {n}. {vote}")

            print("\nTOP NEGATIVE LOADING VOTES:")
            for n, vote in enumerate(negative_votes, 1):
                print(f"  {n}. {vote}")

            # Get candidate label from Ollama
            candidate = get_candidate_label(positive_votes, negative_votes)

            # Prompt human for confirmation or override
            label = prompt_human(component_idx, candidate)

            # Store label
            labels_json[chamber][component_idx_str] = label
            print(f"  → Saved as: {label}")

    # Save all labels and append to methodology log
    save_labels(labels_json)

    print("\n" + "="*60)
    print("Step 5 complete. Labels saved to output/component_labels.json")
    print("Re-run steps 6, 8, and 9 to apply the confirmed labels.")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
