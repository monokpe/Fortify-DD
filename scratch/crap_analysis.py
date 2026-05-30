import json
import subprocess
import os
import sys

def main():
    coverage_file = "coverage.json"
    if not os.path.exists(coverage_file):
        print(f"Error: {coverage_file} not found. Please run tests with coverage first.", file=sys.stderr)
        sys.exit(1)

    print("Loading coverage data...")
    with open(coverage_file, "r", encoding="utf-8") as f:
        coverage_data = json.load(f)

    print("Running Radon to analyze cyclomatic complexity...")
    # Invoke Radon to get cyclomatic complexity in JSON format
    result = subprocess.run(
        ["uv", "run", "--with", "radon", "radon", "cc", "app", "-j"],
        capture_output=True,
        text=True,
        shell=True
    )
    if result.returncode != 0:
        print(f"Error running radon: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    radon_data = json.loads(result.stdout)

    # Normalize file keys in coverage data for matching
    # coverage.json file keys might be absolute or relative paths with different separators
    normalized_coverage = {}
    for filepath, file_info in coverage_data.get("files", {}).items():
        norm_path = os.path.normpath(filepath)
        normalized_coverage[norm_path] = file_info

    analyzed_functions = []

    for file_key, blocks in radon_data.items():
        norm_file_key = os.path.normpath(file_key)
        cov_info = normalized_coverage.get(norm_file_key)

        if not cov_info:
            # Maybe the file was not executed at all (0% coverage)
            # We can still find it in our workspace and assume 0% coverage
            # Let's see if we can locate it
            executed_lines = []
            missing_lines = []
            has_coverage_data = False
        else:
            executed_lines = cov_info.get("executed_lines", [])
            missing_lines = cov_info.get("missing_lines", [])
            has_coverage_data = True

        for block in blocks:
            # We only calculate CRAP score for functions and methods, not classes
            if block.get("type") not in ("function", "method"):
                continue

            name = block.get("name")
            classname = block.get("classname")
            lineno = block.get("lineno")
            endline = block.get("endline")
            complexity = block.get("complexity", 1)

            full_name = f"{classname}.{name}" if classname else name

            # Compute coverage for the specific line range of this function
            func_executed = [l for l in executed_lines if lineno <= l <= endline]
            func_missing = [l for l in missing_lines if lineno <= l <= endline]
            total_stmts = len(func_executed) + len(func_missing)

            if total_stmts > 0:
                cov = len(func_executed) / total_stmts
            else:
                # If there are no statements, it's either fully covered (docstring/pass) or not in coverage
                cov = 1.0 if has_coverage_data else 0.0

            # CRAP Formula: C^2 * (1 - cov)^3 + C
            crap_score = (complexity ** 2) * ((1.0 - cov) ** 3) + complexity

            analyzed_functions.append({
                "file": file_key,
                "name": full_name,
                "line_range": f"{lineno}-{endline}",
                "complexity": complexity,
                "coverage": cov,
                "crap": crap_score,
                "statements": total_stmts,
                "covered_statements": len(func_executed)
            })

    # Sort functions by CRAP score descending, then by complexity descending
    analyzed_functions.sort(key=lambda x: (x["crap"], x["complexity"]), reverse=True)

    # 1. Overall Stats
    total_funcs = len(analyzed_functions)
    high_risk_funcs = [f for f in analyzed_functions if f["crap"] >= 30.0]
    medium_risk_funcs = [f for f in analyzed_functions if 10.0 <= f["crap"] < 30.0]
    low_risk_funcs = [f for f in analyzed_functions if f["crap"] < 10.0]

    avg_crap = sum(f["crap"] for f in analyzed_functions) / total_funcs if total_funcs > 0 else 0
    avg_complexity = sum(f["complexity"] for f in analyzed_functions) / total_funcs if total_funcs > 0 else 0
    
    total_stmts = sum(f["statements"] for f in analyzed_functions)
    total_cov_stmts = sum(f["covered_statements"] for f in analyzed_functions)
    overall_cov = total_cov_stmts / total_stmts if total_stmts > 0 else 1.0

    print("\n" + "="*80)
    print("                      FORTIFY DD CODEBASE CRAP ANALYSIS")
    print("="*80)
    print(f"Total Functions Analyzed:   {total_funcs}")
    print(f"Overall Code Coverage:       {overall_cov * 100:.1f}% ({total_cov_stmts}/{total_stmts} statements)")
    print(f"Average Cyclomatic Complexity: {avg_complexity:.2f}")
    print(f"Average CRAP Score:          {avg_crap:.2f}")
    print(f"High Risk Functions (CRAP >= 30):   {len(high_risk_funcs)}")
    print(f"Medium Risk Functions (10 <= CRAP < 30): {len(medium_risk_funcs)}")
    print(f"Low Risk Functions (CRAP < 10):      {len(low_risk_funcs)}")
    print("="*80)

    # Write Markdown Artifact
    artifact_dir = os.path.join("C:\\Users\\USER\\.gemini\\antigravity\\brain\\1d27e572-b1f5-4af6-be99-1edf962588f0")
    os.makedirs(artifact_dir, exist_ok=True)
    report_path = os.path.join(artifact_dir, "crap_analysis_results.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Fortify DD Codebase CRAP Analysis Report\n\n")
        f.write("The Change Risk Anti-Patterns (CRAP) index measures the risk profile of a function. ")
        f.write("It combines cyclomatic complexity and statement-level coverage to identify complex, poorly tested code. ")
        f.write("A CRAP score of **30 or higher** is generally considered highly risky and represents a Change Risk Anti-Pattern.\n\n")
        
        f.write("### CRAP Formula\n")
        f.write("$$\\text{CRAP}(f) = C(f)^2 \\cdot (1 - cov(f))^3 + C(f)$$\n")
        f.write("Where $C(f)$ is the cyclomatic complexity of function $f$, and $cov(f)$ is its statement coverage fraction.\n\n")

        f.write("## Executive Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("| :--- | :--- |\n")
        f.write(f"| **Total Functions Analyzed** | {total_funcs} |\n")
        f.write(f"| **Overall Code Coverage** | {overall_cov * 100:.1f}% ({total_cov_stmts}/{total_stmts} statements) |\n")
        f.write(f"| **Average Cyclomatic Complexity** | {avg_complexity:.2f} |\n")
        f.write(f"| **Average CRAP Score** | {avg_crap:.2f} |\n")
        f.write(f"| **High Risk Functions (CRAP &ge; 30)** | **{len(high_risk_funcs)}** 🔴 |\n")
        f.write(f"| **Medium Risk Functions (10 &le; CRAP < 30)** | {len(medium_risk_funcs)} 🟡 |\n")
        f.write(f"| **Low Risk Functions (CRAP < 10)** | {len(low_risk_funcs)} 🟢 |\n\n")

        # Visual alert based on findings
        if len(high_risk_funcs) > 0:
            f.write("> [!WARNING]\n")
            f.write(f"> Found {len(high_risk_funcs)} function(s) with CRAP score &ge; 30. These functions represent high change risk due to combined complexity and lack of test coverage. Refactoring or adding unit tests is highly recommended.\n\n")
        else:
            f.write("> [!NOTE]\n")
            f.write("> Excellent news! No functions in the codebase exceeded the CRAP risk threshold of 30. The code is well-tested and complexity is kept under control.\n\n")

        f.write("## High & Medium Risk Functions\n\n")
        f.write("| Function / Method | File Path | Line Range | Complexity | Coverage | CRAP Score | Risk Category |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")
        
        for func in high_risk_funcs + medium_risk_funcs:
            cov_str = f"{func['coverage'] * 100:.1f}%"
            crap_str = f"**{func['crap']:.2f}**"
            status = "🔴 High" if func['crap'] >= 30 else "🟡 Medium"
            file_link = f"[{os.path.basename(func['file'])}](file:///{os.path.abspath(func['file']).replace(chr(92), '/')})"
            f.write(f"| `{func['name']}` | {file_link} | {func['line_range']} | {func['complexity']} | {cov_str} | {crap_str} | {status} |\n")

        f.write("\n## File-by-File Summary\n\n")
        f.write("| File Path | Functions | Avg Complexity | Avg Coverage | Avg CRAP Score | Max CRAP Score |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: |\n")
        
        # Group by file
        files_dict = {}
        for func in analyzed_functions:
            file_path = func["file"]
            if file_path not in files_dict:
                files_dict[file_path] = []
            files_dict[file_path].append(func)
            
        for file_path, funcs in sorted(files_dict.items()):
            file_funcs_count = len(funcs)
            file_avg_complexity = sum(fn["complexity"] for fn in funcs) / file_funcs_count
            file_avg_cov = sum(fn["coverage"] for fn in funcs) / file_funcs_count
            file_avg_crap = sum(fn["crap"] for fn in funcs) / file_funcs_count
            file_max_crap = max(fn["crap"] for fn in funcs)
            
            file_basename = os.path.basename(file_path)
            file_link = f"[{file_basename}](file:///{os.path.abspath(file_path).replace(chr(92), '/')})"
            
            f.write(f"| {file_link} | {file_funcs_count} | {file_avg_complexity:.1f} | {file_avg_cov * 100:.1f}% | {file_avg_crap:.2f} | {file_max_crap:.2f} |\n")

        f.write("\n## Complete Codebase Breakdown\n\n")
        f.write("| Function / Method | File Path | Line Range | Complexity | Coverage | CRAP Score |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: |\n")
        for func in analyzed_functions:
            cov_str = f"{func['coverage'] * 100:.1f}%"
            crap_str = f"{func['crap']:.2f}"
            if func['crap'] >= 30:
                crap_str = f"**{crap_str}** 🔴"
            elif func['crap'] >= 10:
                crap_str = f"{crap_str} 🟡"
            else:
                crap_str = f"{crap_str} 🟢"
                
            file_basename = os.path.basename(func['file'])
            file_link = f"[{file_basename}](file:///{os.path.abspath(func['file']).replace(chr(92), '/')})"
            f.write(f"| `{func['name']}` | {file_link} | {func['line_range']} | {func['complexity']} | {cov_str} | {crap_str} |\n")

    print(f"Markdown report generated successfully at: {report_path}")

if __name__ == "__main__":
    main()
