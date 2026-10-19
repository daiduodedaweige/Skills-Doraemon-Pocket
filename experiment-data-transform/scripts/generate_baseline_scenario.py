"""Reproduce the explicitly approved 83-instance hypothetical scenario (stdlib only)."""
import argparse
import hashlib
import json
import math
import random
import re
from pathlib import Path


def generate(root):
    rng = random.Random(42)
    env_path = root / '实验环境.md'
    source = root / '论文/实验/input_doc/baseline_ex.tex'
    output = source.with_name('baseline_ex_generated.tex')
    env = env_path.read_text()
    categories = []
    for line in env.splitlines():
        if not re.match(r'^\| \d+ \|', line):
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        modules = [(m, int(n)) for m, n in re.findall(r'`([^`]+)`×(\d+)', cells[2])]
        assert len(modules) == int(cells[3])
        assert sum(n for _, n in modules) == int(cells[4])
        categories.append((int(cells[0]), cells[1], modules))
    assert len(categories) == 13
    methods = ['HiC-Verify', 'Direct LLM', 'Verilog-only LLM', 'Spec-only LLM']
    ranges = [
        [(97, 100), (96, 100), (90, 100), (0, 3), (0, 2)],
        [(92, 100), (90, 100), (65, 90), (0, 6), (0, 4)],
        [(90, 100), (88, 100), (60, 88), (3, 14), (2, 10)],
        [(88, 100), (85, 100), (55, 85), (4, 16), (3, 12)],
    ]
    ratios = [(1, 1), (.45, .75), (.65, .95), (.65, 1)]
    # Explicit scenario assumptions, not measured module complexity.
    complexity = {1: .25, 2: .70, 3: .90, 4: .45, 5: .40, 6: .50,
                  7: .60, 8: .60, 9: .75, 10: .80, 11: .85, 12: .90, 13: .65}
    instances, records = [], []
    for category, name, modules in categories:
        for module, count in modules:
            module_difficulty = .65 * complexity[category] + .35 * rng.random()
            module_scale = rng.randint(20, 120)
            for config in range(1, count + 1):
                iid = f'C{category:02d}-{module}-cfg{config:02d}'
                # These are ordinal scenario IDs, not verified RTL parameter values.
                difficulty = .8 * module_difficulty + .2 * rng.random()
                n_hic = max(20, min(120, round(.8 * module_scale + .2 * rng.randint(20, 120))))
                instances.append(dict(instance_id=iid, category_id=category, category=name,
                                      module=module, configuration_id=f'cfg{config:02d}',
                                      rtl_parameters=None, configuration_status='planned-placeholder',
                                      scenario_difficulty=difficulty))
                for method_idx, method in enumerate(methods):
                    lo, hi = ratios[method_idx]
                    n = n_hic if method_idx == 0 else rng.randint(
                        max(1, math.ceil(n_hic * lo)),
                        math.floor(n_hic * hi))
                    targets = []
                    for metric_idx, (low, high) in enumerate(ranges[method_idx]):
                        q = .65 * difficulty + .35 * rng.random()
                        targets.append((low + (high-low) * (1-q if metric_idx < 3 else q)) / 100)
                    cp = round(n * targets[0])
                    sp = round(n * targets[1])
                    fpv = round(n * targets[2])
                    assert fpv <= min(cp, sp)
                    vac, tri = round(n * targets[3]), round(n * targets[4])
                    assert max(vac, tri) <= fpv
                    records.append(dict(instance_id=iid, method=method, generated=n,
                                        CP=cp, SP=sp, FPV=fpv, Vac=vac, Tri=tri,
                                        target_rates=dict(zip(['CP', 'SP', 'FPV', 'Vac', 'Tri'], targets))))
    assert len(instances) == 83 and len(records) == 332
    assert len({i['module'] for i in instances}) == 58
    def escape(s):
        return s.replace('_', r'\_')
    lines = [
        '% HYPOTHETICAL SYNTHETIC DATA -- NOT MEASURED EXPERIMENTAL RESULTS.',
        '% seed: 42; no GPR fitted; environment effects are not learned or validated.',
        '% Source: baseline_ex.tex (format only); environment: 实验环境.md (planned instance roster).',
        '% All metrics use generated properties as denominator; Vac/Tri may overlap.',
        '% cfgNN are ordinal planned configuration IDs, not verified RTL parameter assignments.',
        '% HiC: Sonnet 4.6 generation/syntax + Opus 4.6 feedback; baselines: Sonnet 4.6.',
        '% Scenario: HiC retrieval top-k=5, feedback iteration cap=5.',
        '% Full assumptions, roster and counts: baseline_ex_generated.meta.json',
        r'\begin{landscape}',
    ]
    for category, name, modules in categories:
        group = [i for i in instances if i['category_id'] == category]
        k = len(group)
        lines += [f'% Category {category}: {name}', r'\begin{table*}[p]', r'\centering',
                  r'\caption{Hypothetical synthetic per-DUT baseline scenario: category '
                  + str(category) + r'. Not measured results.}',
                  r'\sourcefile{input_doc/baseline_ex_generated.tex}',
                  rf'\label{{tab:synthetic-baseline-{category:02d}}}',
                  r'\vspace{1em}', r'\resizebox{\textwidth}{!}{', r'\footnotesize',
                  r'\begin{tabular}{l|' + '|'.join(['ccccc'] * k) + '}', r'\hline',
                  r'\multirow{2}{*}{Method}']
        for j, instance in enumerate(group):
            ending = r' \\' if j == k-1 else ''
            border = 'c' if j == k-1 else 'c|'
            label = escape(instance['module']) + ' (' + instance['configuration_id'] + ')'
            lines.append(rf'  & \multicolumn{{5}}{{{border}}}{{{label}}}' + ending)
        lines += [rf'\cline{{2-{1+5*k}}}', '  ' + ' & CP & SP & FPV & Vac & Tri' * k + r' \\', r'\hline']
        for method in methods:
            label = (method + ' (Sonnet/Opus 4.6)') if method == 'HiC-Verify' else method + ' (Sonnet 4.6)'
            lines.append(label)
            for j, instance in enumerate(group):
                row = next(r for r in records if r['instance_id'] == instance['instance_id'] and r['method'] == method)
                values = [f"{row[key]}/{row['generated']}" for key in ['CP', 'SP', 'FPV', 'Vac', 'Tri']]
                lines.append('  & ' + ' & '.join(values) + (r' \\' if j == k-1 else ''))
        lines += [r'\hline', r'\end{tabular}', '}', r'\end{table*}']
    lines.append(r'\end{landscape}')
    text = '\n'.join(lines) + '\n'
    # Validate serialized rows, not only the in-memory records.
    fractions = re.findall(r'(?<!\d)(\d+)/(\d+)(?!\d)', text)
    assert len(fractions) == 83*4*5
    assert all(0 <= int(a) <= int(b) and int(b) > 0 for a, b in fractions)
    assert text.count(r'\begin{table*}') == text.count(r'\end{table*}') == 13
    assert text.count(r'\begin{tabular}') == text.count(r'\end{tabular}') == 13
    summary = {}
    for method in methods:
        rows = [r for r in records if r['method'] == method]
        total = sum(r['generated'] for r in rows)
        summary[method] = dict(generated=total, counts={key: sum(r[key] for r in rows) for key in ['CP', 'SP', 'FPV', 'Vac', 'Tri']},
                              micro_percent={key: 100*sum(r[key] for r in rows)/total for key in ['CP', 'SP', 'FPV', 'Vac', 'Tri']})
    meta = dict(data_kind='hypothetical-synthetic', seed=42, model_fitted=False,
                predictive_validation=None, uncertainty_intervals=None,
                support_status='assumption-only; new designs and mixed-model workflow unsupported by observed outcomes',
                sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [source, env_path]},
                original_data_usage='table format only; original counts are not training observations for this scenario',
                generator=str(Path(__file__).resolve().relative_to(root)),
                rng='Python stdlib random.Random, seed 42',
                assumptions=dict(metrics=['CP','SP','FPV','Vac','Tri'], rate_ranges_percent=dict(zip(methods,ranges)),
                                 property_count_ratios=dict(zip(methods,ratios)), hic_count_range=[20,120],
                                 rates='q=.65*instance_difficulty+.35*U; success=low+(high-low)*(1-q); Vac/Tri=low+(high-low)*q',
                                 difficulty='module=.65*category_complexity+.35*U; instance=.8*module+.2*U',
                                 category_complexity=complexity,
                                 counts='round(N*target_rate); deterministic integer scenario, not binomial experimental sampling',
                                 count_scale='HiC N=round(.8*module_scale+.2*U_integer[20,120]); module_scale=U_integer[20,120]; baseline N uniform integer in approved ratio bounds',
                                 rounding='Python round (ties to even); displayed rates can slightly exceed target ranges',
                                 containment='FPV subset of both CP and SP; Vac/Tri subsets of FPV, overlapping allowed; no CP/SP nesting assumed',
                                 models={'HiC-Verify':'Sonnet 4.6 generation/syntax; Opus 4.6 feedback','baselines':'Sonnet 4.6'},
                                 retrieval_top_k=5, feedback_iteration_cap=5,
                                 resource_effects='No CPU, memory, timeout, or model-change performance effect inferred from environment snapshot'),
                validation={'instances':83,'modules':58,'categories':13,'method_instance_rows':332,'metric_cells':1660,
                            'integer_bounds_and_containment':'passed','latex_structure':'passed'},
                instances=instances, records=records, summary=summary)
    output.write_text(text)
    output.with_suffix('.meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output':str(output),'summary':summary},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    generate(parser.parse_args().root.resolve())
