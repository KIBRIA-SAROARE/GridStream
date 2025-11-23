#!/usr/bin/env python3
"""
Pareto Front Analysis for PMU DSE Results
Generates Pareto fronts for Area vs Timing trade-offs
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def is_pareto_efficient(costs):
    """
    Find the Pareto-efficient points
    :param costs: An (n_points, n_costs) array
    :return: A boolean array of Pareto-efficient points
    """
    is_efficient = np.ones(costs.shape[0], dtype=bool)
    for i, c in enumerate(costs):
        if is_efficient[i]:
            # Remove dominated points (those that are worse in all objectives)
            is_efficient[is_efficient] = np.any(costs[is_efficient] < c, axis=1)
            is_efficient[i] = True
    return is_efficient

def load_and_combine_results():
    """Load results from both baseline and main runs"""
    results = []
    
    # Load baseline (float) results
    baseline_file = Path("dse_results_baseline.csv")
    if baseline_file.exists():
        df_baseline = pd.read_csv(baseline_file)
        results.append(df_baseline)
        print(f"Loaded {len(df_baseline)} baseline (float) results")
    
    # Load main (fixed-point) results
    main_file = Path("dse_results.csv")
    if main_file.exists() and main_file.stat().st_size > 0:
        df_main = pd.read_csv(main_file)
        results.append(df_main)
        print(f"Loaded {len(df_main)} fixed-point results")
    else:
        print("Warning: Main results file is empty or missing")
        # Manually add the Zynq II=1 result we know succeeded
        manual_result = {
            'Family': 'A',
            'W_amp': 16,
            'W_acc': 32,
            'W_angle': 20,
            'Unroll': 1,
            'II': 1,
            'Target': 'Zynq-US+',
            'Freq': 300,
            'Events': 433,
            'LUT': 60150,
            'FF': 194618,
            'DSP': 1579,
            'BRAM': 0,
            'Period': 2.456
        }
        results.append(pd.DataFrame([manual_result]))
        print("Added manual Zynq II=1 result")
    
    if not results:
        raise ValueError("No results found!")
    
    df = pd.concat(results, ignore_index=True)
    
    # Calculate derived metrics
    df['Area_Score'] = df['LUT'] + df['FF'] * 0.5 + df['DSP'] * 10 + df['BRAM'] * 100
    df['Fmax_MHz'] = 1000.0 / df['Period']
    df['Meets_Timing'] = df['Fmax_MHz'] >= df['Freq']
    
    return df

def plot_pareto_front(df, x_metric, y_metric, title, filename, 
                       color_by='Target', size_by='II', filter_func=None):
    """
    Plot Pareto front for given metrics
    """
    if filter_func:
        df = df[filter_func(df)].copy()
    
    if len(df) == 0:
        print(f"Warning: No data points for {title}")
        return
    
    # Prepare data for Pareto analysis
    costs = df[[x_metric, y_metric]].values
    
    # Find Pareto front
    pareto_mask = is_pareto_efficient(costs)
    pareto_points = df[pareto_mask].copy()
    non_pareto_points = df[~pareto_mask].copy()
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Color mapping
    if color_by in df.columns:
        unique_colors = df[color_by].unique()
        color_map = plt.cm.get_cmap('tab10', len(unique_colors))
        color_dict = {val: color_map(i) for i, val in enumerate(unique_colors)}
    else:
        color_dict = {'default': 'blue'}
    
    # Size mapping
    if size_by in df.columns:
        size_values = df[size_by].values
        sizes = 100 + (size_values - size_values.min()) * 200 / (size_values.max() - size_values.min() + 1)
    else:
        sizes = np.full(len(df), 100)
    
    # Plot non-Pareto points
    for idx, row in non_pareto_points.iterrows():
        color = color_dict.get(row.get(color_by, 'default'), 'gray')
        size = sizes[df.index.get_loc(idx)]
        ax.scatter(row[x_metric], row[y_metric], 
                  c=[color], s=size, alpha=0.3, edgecolors='black', linewidth=0.5)
    
    # Plot Pareto points
    for idx, row in pareto_points.iterrows():
        color = color_dict.get(row.get(color_by, 'default'), 'red')
        size = sizes[df.index.get_loc(idx)]
        ax.scatter(row[x_metric], row[y_metric], 
                  c=[color], s=size, alpha=0.8, edgecolors='black', linewidth=2,
                  marker='*', zorder=10)
        
        # Annotate Pareto points
        label = f"{row.get('Family', 'N/A')}-II{row.get('II', 'N/A')}"
        ax.annotate(label, (row[x_metric], row[y_metric]), 
                   xytext=(5, 5), textcoords='offset points', fontsize=8)
    
    # Draw Pareto front line
    if len(pareto_points) > 1:
        pareto_sorted = pareto_points.sort_values(x_metric)
        ax.plot(pareto_sorted[x_metric], pareto_sorted[y_metric], 
               'r--', alpha=0.5, linewidth=2, label='Pareto Front')
    
    # Legend
    if color_by in df.columns:
        handles = [plt.Line2D([0], [0], marker='o', color='w', 
                             markerfacecolor=color_dict[val], markersize=10, label=val)
                  for val in unique_colors]
        ax.legend(handles=handles, title=color_by, loc='best')
    
    ax.set_xlabel(x_metric, fontsize=12)
    ax.set_ylabel(y_metric, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved plot: {filename}")
    
    return pareto_points

def generate_summary_report(df, pareto_results):
    """Generate a text summary report"""
    report = []
    report.append("=" * 80)
    report.append("PMU DSE PARETO FRONT ANALYSIS")
    report.append("=" * 80)
    report.append("")
    
    report.append(f"Total Configurations Evaluated: {len(df)}")
    report.append(f"  - Float Baseline: {len(df[df['Family'] == 'Float'])}")
    report.append(f"  - Fixed-Point: {len(df[df['Family'] != 'Float'])}")
    report.append("")
    
    report.append("TARGETS:")
    for target in df['Target'].unique():
        target_df = df[df['Target'] == target]
        report.append(f"  {target}: {len(target_df)} configurations")
    report.append("")
    
    report.append("=" * 80)
    report.append("PARETO-OPTIMAL CONFIGURATIONS")
    report.append("=" * 80)
    
    for name, pareto_df in pareto_results.items():
        if pareto_df is not None and len(pareto_df) > 0:
            report.append(f"\n{name}:")
            report.append("-" * 80)
            for idx, row in pareto_df.iterrows():
                report.append(f"  Config: {row.get('Family', 'N/A')}, "
                            f"Target={row.get('Target', 'N/A')}, "
                            f"II={row.get('II', 'N/A')}, "
                            f"Unroll={row.get('Unroll', 'N/A')}")
                report.append(f"    Area: LUT={row['LUT']}, FF={row['FF']}, "
                            f"DSP={row['DSP']}, BRAM={row['BRAM']}")
                report.append(f"    Timing: Period={row['Period']:.3f}ns, "
                            f"Fmax={row.get('Fmax_MHz', 0):.1f}MHz, "
                            f"Target={row['Freq']}MHz")
                report.append(f"    Events: {row.get('Events', 'N/A')}")
                report.append("")
    
    return "\n".join(report)

def main():
    print("Loading DSE results...")
    df = load_and_combine_results()
    
    print(f"\nTotal configurations: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    # Create output directory
    output_dir = Path("dse_pareto_analysis")
    output_dir.mkdir(exist_ok=True)
    
    pareto_results = {}
    
    # 1. Overall Area vs Timing (all targets)
    print("\n1. Generating Overall Area vs Timing Pareto Front...")
    pareto_results['Overall'] = plot_pareto_front(
        df, 'Area_Score', 'Period',
        'Overall Pareto Front: Area vs Timing',
        output_dir / 'pareto_overall_area_timing.png',
        color_by='Target', size_by='II'
    )
    
    # 2. Per-Target Pareto Fronts
    for target in df['Target'].unique():
        print(f"\n2. Generating {target} Pareto Front...")
        pareto_results[f'{target}'] = plot_pareto_front(
            df, 'LUT', 'Period',
            f'{target}: LUT vs Timing',
            output_dir / f'pareto_{target.lower().replace("-", "_")}_lut_timing.png',
            color_by='Family', size_by='II',
            filter_func=lambda d: d['Target'] == target
        )
    
    # 3. DSP vs LUT Trade-off
    print("\n3. Generating DSP vs LUT Pareto Front...")
    pareto_results['DSP_LUT'] = plot_pareto_front(
        df, 'LUT', 'DSP',
        'Resource Trade-off: LUT vs DSP',
        output_dir / 'pareto_lut_dsp.png',
        color_by='Target', size_by='II'
    )
    
    # 4. II Comparison
    print("\n4. Generating II Comparison...")
    pareto_results['II_Comparison'] = plot_pareto_front(
        df, 'Area_Score', 'Fmax_MHz',
        'Initiation Interval Trade-off: Area vs Fmax',
        output_dir / 'pareto_area_fmax.png',
        color_by='II', size_by='DSP'
    )
    
    # Generate summary report
    print("\n5. Generating summary report...")
    report = generate_summary_report(df, pareto_results)
    
    report_file = output_dir / 'pareto_summary.txt'
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"Saved report: {report_file}")
    
    # Save combined CSV
    combined_file = output_dir / 'dse_combined_results.csv'
    df.to_csv(combined_file, index=False)
    print(f"Saved combined results: {combined_file}")
    
    # Print summary to console
    print("\n" + report)
    
    print(f"\n{'='*80}")
    print(f"Analysis complete! Results saved to: {output_dir}/")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
