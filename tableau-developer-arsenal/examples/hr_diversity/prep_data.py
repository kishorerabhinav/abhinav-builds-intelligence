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

# ---- Monthly bars: each month of the chosen year beside the same month a year earlier ----
by_month = defaultdict(list)
for r in rows:
    by_month[r['hire_date'][:7]].append(r)
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
out = []
for y in YEARS:
    for metric, t in TESTS.items():
        for m, name in enumerate(MONTHS, 1):
            cur, prev = by_month[f'{y}-{m:02d}'], by_month[f'{y - 1}-{m:02d}']
            share = lambda rs: round(sum(map(t, rs)) / len(rs), 6) if rs else ''
            out.append([str(y), metric, m, name, share(cur), share(prev), len(cur), len(prev)])
write('trend.csv', ['sel_year', 'metric', 'month_num', 'month', 'this_year', 'year_before', 'hires', 'hires_year_before'], out)

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

write('views.csv', ['view', 'view_order', 'view_label'], [['Overview', 1, 'Show Overview'], ['Employee list', 2, 'Show Table']])
print('ok')
