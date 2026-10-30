"""Precompute the helper tables the Tableau rebuild draws from (mirrors the Claude dashboard's calcs)."""
import csv, datetime, os, sys
from collections import defaultdict

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(SRC)))

TESTS = {
    'Diversity': lambda r: r['diverse'] == 'Diverse',
    'Persons of color': lambda r: r['poc'] == 'POC',
    'Female': lambda r: r['gender'] == 'Female',
    'Male & NA': lambda r: r['gender'] == 'Male & NA',
}
YEARS = range(2018, 2023)
SAT = {'1': 'Very unsatisfied', '2': 'Unsatisfied', '3': 'Neutral', '4': 'Satisfied', '5': 'Very satisfied'}
ORDERS = {
    'Position': ['Vice President', 'Director', 'Manager', 'Senior Professional', 'Mid-level Professional', 'Entry Level Professional'],
    'Education': ['Doctoral Degree', "Master's Degree", "Bachelor's Degree", 'Associates Degree', 'High School', 'Not recorded'],
    'Performance rating': ['Exceeds', 'Fully Meets', 'Needs Improvement', 'PIP'],
    'Employee satisfaction': ['Very satisfied', 'Satisfied', 'Neutral', 'Unsatisfied', 'Very unsatisfied'],
}
DIMS = [  # card, picker value, row -> category
    ('Role', 'Position', lambda r: r['position']),
    ('Role', 'Department', lambda r: r['department']),
    ('Role', 'Job role', lambda r: r['job_role']),
    ('Background', 'Education', lambda r: r['education']),
    ('Background', 'Education field', lambda r: r['education_field']),
    ('Background', 'Race', lambda r: r['race']),
    ('Background', 'Marital status', lambda r: r['marital_status']),
    ('Performance', 'Performance rating', lambda r: r['performance']),
    ('Performance', 'Employee satisfaction', lambda r: SAT.get(r['satisfaction'], 'Very satisfied')),
]
year_of = lambda r: int(r['hire_date'][:4])
by_year = defaultdict(list)
for r in rows:
    by_year[year_of(r)].append(r)
pct = lambda v: f'{v * 100:.1f}%'

def write(name, header, data):
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)

# ---- Breakdown bars: one row per drawn layer (track, this year, year-before tick, value label) ----
out = []
for y in YEARS:
    for card, key, fn in DIMS:
        cur, prev = defaultdict(list), defaultdict(list)
        for r in by_year[y]:
            cur[fn(r)].append(r)
        for r in by_year[y - 1]:
            prev[fn(r)].append(r)
        for metric, t in TESTS.items():
            stats = []
            for cat, rs in cur.items():
                n = sum(map(t, rs))
                ps = sum(map(t, prev[cat])) / len(prev[cat]) if prev.get(cat) else None
                stats.append((cat, n / len(rs), ps, n, len(rs)))
            ordl = ORDERS.get(key)
            if ordl:
                stats.sort(key=lambda s: ordl.index(s[0]) if s[0] in ordl else 98)
            else:
                stats.sort(key=lambda s: (s[0] == 'Not recorded', -s[1]))
            for order, (cat, share, ps, n, hc) in enumerate(stats, 1):
                base = [str(y), card, key, metric, cat, f'{cat} ({hc})', order, round(share, 6),
                        '' if ps is None else round(ps, 6), n, hc]
                out.append(base + ['1 Track', 0, 1, ''])
                out.append(base + ['2 This year', 0, round(share, 6), ''])
                if ps is not None:
                    out.append(base + ['3 Year before', round(ps - 0.004, 6), 0.008, ''])
                out.append(base + ['4 Value', 1.0, 0.0001, pct(share)])
write('breakdown.csv', ['sel_year', 'card', 'group_by', 'metric', 'category', 'row_label', 'row_order', 'share', 'prev_share',
                        'n_in_group', 'headcount', 'layer', 'bar_start', 'bar_length', 'value_text'], out)

# ---- Monthly trend: the line, its area, a dashed new-year rule, a 50% guide, end dot and year labels ----
by_month = defaultdict(list)
for r in rows:
    by_month[r['hire_date'][:7]].append(r)
out = []
for y in YEARS:
    months = [f'{yy}-{m:02d}' for yy in (y - 1, y) for m in range(1, 13)]
    d = lambda mo: f'{mo}-01'
    for metric, t in TESTS.items():
        pts = [(mo, sum(map(t, by_month[mo])) / len(by_month[mo]), len(by_month[mo])) for mo in months if by_month[mo]]
        for mo, s, n in pts:
            out.append([str(y), metric, 'Share', 's', d(mo), round(s, 6), round(s, 6), '', n])
        for k in range(7):  # dashes of the new-year rule
            lo = k * 0.15
            out.append([str(y), metric, 'Boundary', f'b{k}', d(f'{y}-01'), round(lo, 3), '', '', ''])
            out.append([str(y), metric, 'Boundary', f'b{k}', d(f'{y}-01'), round(lo + 0.08, 3), '', '', ''])
        out.append([str(y), metric, 'Guide', 'g', d(months[0]), 0.5, '', '', ''])
        out.append([str(y), metric, 'Guide', 'g', d(months[-1]), 0.5, '', '50%', ''])
        mo, s, n = pts[-1]
        out.append([str(y), metric, 'End', 'e', d(mo), round(s, 6), '', '', n])
        out.append([str(y), metric, 'Label', 'l1', d(months[0]), -0.12, '', str(y - 1), ''])
        out.append([str(y), metric, 'Label', 'l2', d(f'{y}-01'), -0.12, '', str(y), ''])
seen = defaultdict(int)  # point number within each line, so points that share a month stay separate marks
for r in out:
    k = tuple(r[:4])
    r.append(f'p{seen[k]:02d}')
    seen[k] += 1
write('trend.csv', ['sel_year', 'metric', 'layer', 'seg', 'month', 'value', 'area', 'label', 'hires', 'pt'], out)

# ---- Employee table in long form so headers can be clicked to sort ----
COLS = [('Employee ID', 'employee_id'), ('Hire date', 'hire_date'), ('Gender', 'gender'), ('Race', 'race'),
        ('Position', 'position'), ('Department', 'department'), ('Job role', 'job_role'),
        ('Performance', 'performance'), ('Satisfaction (1–5)', 'satisfaction')]
out = []
for i, (label, col) in enumerate(COLS, 1):
    vals = sorted({r[col] for r in rows})
    rank = {v: k for k, v in enumerate(vals, 1)}
    for r in rows:
        out.append([r['employee_id'], year_of(r), label, i, r[col], rank[r[col]]])
write('employee_table.csv', ['employee_id', 'hire_year', 'column_name', 'col_order', 'value', 'value_rank'], out)

write('views.csv', ['view', 'view_order'], [['Overview', 1], ['Employee list', 2]])
print('ok')
