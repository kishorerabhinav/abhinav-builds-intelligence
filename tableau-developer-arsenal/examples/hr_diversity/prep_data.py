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
