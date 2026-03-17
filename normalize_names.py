"""
Normalize Employee and Commission names in sales data.
- Employee: consistent format (trim spaces, fix known variants like Bir_ra -> Bir-ra)
- Commission: replace shorthand (adam, AlexS, DuaaZ) with full Employee names
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Employee name variants to canonical form (applies to Employee column)
# Keep in sync with dashboard.py EMPLOYEE_NAME_MAPPING
EMPLOYEE_NORMALIZATIONS = {
    "Bir_ra Thanvi": "Bir-ra Thanvi",
    "Bir-ra B": "Bir-ra Thanvi",
    "Bir-ra1": "Bir-ra",
    "Molly ": "Molly Tasheva",
    "Leonard Masie": "Leonard Maisie",
    "Nicorescu Codruta": "Codruta Nicorescu",
    "Edmond1": "Edmond",
    "Eddie1": "Eddie",
    "AishaM": "Aisha",
    "Michiele": "Michela",
    "Roim A": "Roim",
    "Ruby1": "Ruby",
    "Ayihab1": "Ayihab",
    "AyshaK": "Aysha",
    "Codruta": "Codruta Nicorescu",
    "ErinA": "Erin",
    "Iqra2": "Iqra",
    "Tuba": "Raja Tuba",
    "T Temitope": "Temitope",
    "T.Molly": "Molly Tasheva",
    "molly1": "Molly Tasheva",
    "adam": "Adam Lee",
}


def extract_commission_parts(comm_str):
    """Parse 'name1: amt1, name2: amt2' into list of (name, amount_str)."""
    if not comm_str or not str(comm_str).strip():
        return []
    parts = []
    for segment in str(comm_str).split(","):
        segment = segment.strip()
        if ":" in segment:
            name = segment.split(":")[0].strip()
            rest = segment.split(":", 1)[1].strip()
            parts.append((name, rest))
    return parts


def _get_col(row, *names):
    """Get column value case-insensitively (handles CSV header variations)."""
    key_map = {str(k).strip().lower(): k for k in row.keys()}
    for name in names:
        n = name.strip().lower()
        if n in key_map:
            return row.get(key_map[n], "")
    return ""


def build_commission_mapping(csv_path):
    """Infer commission shorthand -> full employee name from co-occurrence."""
    comm_to_emp = defaultdict(Counter)
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            emp = _get_col(row, "Employee", "employee").strip()
            if not emp:
                continue
            emp_canonical = EMPLOYEE_NORMALIZATIONS.get(emp, emp)
            emp_canonical = " ".join(emp_canonical.split())  # collapse spaces
            for comm_name, _ in extract_commission_parts(_get_col(row, "Commissions", "Commission", "commissions", "commission")):
                comm_to_emp[comm_name][emp_canonical] += 1

    mapping = {}
    for comm_name, emp_counts in comm_to_emp.items():
        if emp_counts:
            best_emp = emp_counts.most_common(1)[0][0]
            mapping[comm_name] = best_emp
    return mapping


def normalize_employee(emp, normalizations=None):
    """Normalize employee name: trim, apply known variants."""
    if not emp or (isinstance(emp, float) and emp != emp):
        return emp
    s = str(emp).strip()
    s = " ".join(s.split())  # collapse multiple spaces
    if normalizations and s in normalizations:
        return normalizations[s]
    return s


def normalize_commissions(comm_str, commission_mapping, employee_normalizations=None):
    """Replace commission shorthand with full employee names."""
    if not comm_str or not str(comm_str).strip():
        return comm_str
    parts = extract_commission_parts(comm_str)
    if not parts:
        return comm_str
    norms = employee_normalizations or {}
    result = []
    for name, amount in parts:
        full_name = commission_mapping.get(name, name)
        full_name = norms.get(full_name, full_name)  # apply employee normalizations
        result.append(f"{full_name}: {amount}")
    return ", ".join(result)


def normalize_csv(input_path, output_path=None):
    """Normalize Employee and Commission columns in a CSV file."""
    input_path = Path(input_path)
    if output_path is None:
        # Default: write to separate _normalized file to avoid overwriting input
        output_path = input_path.parent / f"{input_path.stem}_normalized{input_path.suffix}"
    output_path = Path(output_path)

    commission_mapping = build_commission_mapping(input_path)
    all_normalizations = {**EMPLOYEE_NORMALIZATIONS}

    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        emp_key = next((c for c in fieldnames or [] if str(c).strip().lower() == "employee"), "Employee")
        comm_key = next((c for c in fieldnames or [] if str(c).strip().lower() in ("commissions", "commission")), "Commissions")
        for row in reader:
            emp = _get_col(row, "Employee", "employee")
            comm = _get_col(row, "Commissions", "Commission", "commissions", "commission")
            row[emp_key] = normalize_employee(emp, all_normalizations)
            row[comm_key] = normalize_commissions(
                comm, commission_mapping, all_normalizations
            )
            rows.append(row)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return commission_mapping


def main():
    base = Path(__file__).parent
    files = [
        ("PYT Sales Data_rows.csv", "PYT Sales Data_rows_normalized.csv"),
        ("Opatra Sales Data_rows.csv", "Opatra Sales Data_rows_normalized.csv"),
    ]
    for inp, out in files:
        path = base / inp
        if not path.exists():
            print(f"Skipping {inp} (not found)")
            continue
        print(f"Normalizing {inp} -> {out}")
        mapping = normalize_csv(path, base / out)
        print(f"  Commission mappings: {len(mapping)}")


if __name__ == "__main__":
    main()
